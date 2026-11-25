#!/usr/bin/env python3
"""Kurt vs Rails: the same application, the same database, the same load.

    python3 bench/bench.py setup      build both apps, create and migrate the databases
    python3 bench/bench.py check      start both, compare every endpoint's answer, stop
    python3 bench/bench.py run        the benchmark; results under bench/results/<time>/
    python3 bench/bench.py report DIR rebuild DIR/summary.md from its JSON files

`run` takes:
    --frameworks kurt,rails,kemal   which to measure (default all three)
    --scenarios a,b           a subset of SCENARIOS (default all)
    --workers N               Kurt threads = Puma processes (default 4)
    --threads N               Puma threads per process (default 3, Rails 8's default)
    --connections N           oha's concurrent connections (default 64)
    --duration S --warmup S   seconds measured / thrown away per scenario (15 / 5)
    --runs N                  repeats; the summary takes the median (default 3)
    --rate N                  fixed rate (req/s) instead of as-fast-as-possible;
                              latency is then corrected for coordinated omission

Needs: oha, psql/createdb, a running PostgreSQL, iyi + bin/kurt (make in the
repo root), Ruby with Bundler for apps/rails (.tool-versions names it), Crystal
with shards for apps/kemal.
Only the standard library: the system python3 runs it.
"""

import argparse
import json
import os
import secrets
import shutil
import signal
import statistics
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

BENCH = Path(__file__).resolve().parent
REPO = BENCH.parent
APPS = BENCH / "apps"
RESULTS = BENCH / "results"
SEED = BENCH / "db" / "seed.sql"
PG_HOST = os.environ.get("BENCH_PG", "postgres://localhost")

# name, method, path (a rand_regex for oha when `regex`), what it measures
SCENARIOS = [
    ("plaintext", "GET", "/bench/plaintext", False, "router, middleware, a text body"),
    ("json", "GET", "/bench/json", False, "the same plus JSON encoding"),
    ("show", "GET", "/bench/posts/[1-9][0-9]{0,3}", True, "one SELECT by primary key, a model to JSON"),
    ("feed", "GET", "/bench/feed", False, "20 posts + includes(:comments): two queries, 120 rows to JSON"),
    ("page", "GET", "/bench/posts/[1-9][0-9]{0,3}/page", True, "two queries, layout, view, 5 partials, HTML escaping"),
    ("create", "POST", "/bench/posts", False, "session, CSRF, strong params, validation, a transaction of two INSERTs"),
]
CREATE_BODY = "post%5Btitle%5D=Bench+post&post%5Bbody%5D=Written+by+oha&post%5Buser_id%5D=7"


class App:
    """One framework's server: how to build it, start it and where it listens."""

    def __init__(self, name, port, db):
        self.name = name
        self.port = port
        self.db = db
        self.dir = APPS / name
        self.proc = None
        self.log = None

    def url(self, path=""):
        return f"http://127.0.0.1:{self.port}{path}"

    def database_url(self, pool=None):
        return f"{PG_HOST}/{self.db}"

    def env(self, opts):
        raise NotImplementedError

    def command(self, opts):
        raise NotImplementedError

    def start(self, opts, log_path):
        self.log = open(log_path, "w")
        began = time.monotonic()
        self.proc = subprocess.Popen(
            self.command(opts), cwd=self.dir, env=self.env(opts),
            stdout=self.log, stderr=subprocess.STDOUT, start_new_session=True,
        )
        deadline = began + 60
        while time.monotonic() < deadline:
            if self.proc.poll() is not None:
                raise SystemExit(f"{self.name} exited at start; see {log_path}")
            try:
                with urllib.request.urlopen(self.url("/up"), timeout=1) as r:
                    if r.status == 200:
                        return time.monotonic() - began
            except (urllib.error.URLError, ConnectionError, OSError):
                pass
            time.sleep(0.05)
        self.stop()
        raise SystemExit(f"{self.name} did not answer /up in 60 s; see {log_path}")

    def stop(self):
        if self.proc and self.proc.poll() is None:
            os.killpg(self.proc.pid, signal.SIGTERM)
            try:
                self.proc.wait(timeout=20)
            except subprocess.TimeoutExpired:
                os.killpg(self.proc.pid, signal.SIGKILL)
                self.proc.wait()
        self.proc = None
        if self.log:
            self.log.close()
            self.log = None

    def rss_kb(self):
        """Resident memory of the server and every process under it (Puma's workers)."""
        if not self.proc:
            return 0
        out = subprocess.run(["ps", "-A", "-o", "pid=,ppid=,rss="], capture_output=True, text=True).stdout
        children, rss = {}, {}
        for line in out.split("\n"):
            parts = line.split()
            if len(parts) == 3:
                pid, ppid, kb = map(int, parts)
                children.setdefault(ppid, []).append(pid)
                rss[pid] = kb
        total, stack = 0, [self.proc.pid]
        while stack:
            pid = stack.pop()
            total += rss.get(pid, 0)
            stack.extend(children.get(pid, []))
        return total


class Kurt(App):
    def build(self):
        kurt = REPO / "bin" / "kurt"
        run(["make", "-s", "bin/kurt"], cwd=REPO)
        run([str(kurt), "build"], cwd=self.dir, env={**os.environ, "DATABASE_URL": self.database_url()})

    def migrate(self):
        run(["bin/kurt", "db:migrate"], cwd=self.dir, env={**os.environ, "KURT_ENV": "production",
            "DATABASE_URL": self.database_url(), "SESSION_SECRET": secrets.token_hex(32)})

    def database_url(self, pool=None):
        url = f"{PG_HOST}/{self.db}"
        if pool:
            # The db shard's default keeps one idle connection: under load
            # every other one would be closed and opened again. Rails keeps
            # its whole pool, so Kurt is given the same.
            url += f"?initial_pool_size={pool}&max_pool_size={pool}&max_idle_pool_size={pool}"
        return url

    def env(self, opts):
        # IYI_WORKERS as well as -w: something parallel starts iyi's pool at
        # its default size (one per core) before the server asks for -w, and
        # `-w N` alone then panics ("its size does not change once it has").
        return {**os.environ, "KURT_ENV": "production", "SESSION_SECRET": secrets.token_hex(32),
                "IYI_WORKERS": str(opts.workers),
                "DATABASE_URL": self.database_url(opts.workers * opts.threads)}

    def command(self, opts):
        return ["bin/kurt", "-b", "127.0.0.1", "-p", str(self.port), "-w", str(opts.workers)]

    def artifact(self):
        binary = self.dir / "bin" / "kurt"
        return f"bin/kurt {binary.stat().st_size / 1e6:.1f} MB (tek dosya)" if binary.exists() else "-"


class Rails(App):
    def ruby_env(self):
        # libpq's GSS probe after Puma's fork crashes on macOS (objc fork
        # safety); Linux does not need it, and it changes nothing else.
        return {**os.environ, "PGGSSENCMODE": "disable", "RAILS_ENV": "production",
                "DATABASE_URL": self.database_url(), "SECRET_KEY_BASE": secrets.token_hex(64)}

    def build(self):
        run(["bundle", "install", "--quiet"], cwd=self.dir, env=self.ruby_env())

    def migrate(self):
        run(["bin/rails", "db:migrate"], cwd=self.dir, env=self.ruby_env())

    def env(self, opts):
        return {**self.ruby_env(), "WEB_CONCURRENCY": str(opts.workers),
                "RAILS_MAX_THREADS": str(opts.threads), "PORT": str(self.port)}

    def command(self, opts):
        return ["bundle", "exec", "puma", "-C", "config/puma.rb"]   # PORT from env

    def artifact(self):
        return "uygulama + Ruby + gem'ler"


class Kemal(App):
    """Crystal's micro-framework: SQL by hand, see apps/kemal/src/bench.cr."""

    def build(self):
        run(["shards", "install", "--frozen"], cwd=self.dir)
        (self.dir / "bin").mkdir(exist_ok=True)
        run(["crystal", "build", "--release", "src/bench.cr", "-o", "bin/bench"], cwd=self.dir)

    def migrate(self):
        # No migrations in Kemal: Kurt's tables, dumped once.
        have = subprocess.run(["psql", "-tAc", "SELECT to_regclass('posts') IS NOT NULL", f"{PG_HOST}/{self.db}"],
                              capture_output=True, text=True).stdout.strip()
        if have != "t":
            run(["psql", "-q", "-v", "ON_ERROR_STOP=1", f"{PG_HOST}/{self.db}", "-f", "db/schema.sql"], cwd=self.dir)

    def database_url(self, pool=None):
        url = f"{PG_HOST}/{self.db}"
        if pool:   # crystal-db's pool has the same defaults as iyi's db
            url += f"?initial_pool_size={pool}&max_pool_size={pool}&max_idle_pool_size={pool}"
        return url

    def env(self, opts):
        return {**os.environ, "CRYSTAL_WORKERS": str(opts.workers), "SESSION_SECRET": secrets.token_hex(32),
                "DATABASE_URL": self.database_url(opts.workers * opts.threads)}

    def command(self, opts):
        return ["bin/bench", "-b", "127.0.0.1", "-p", str(self.port)]

    def artifact(self):
        binary = self.dir / "bin" / "bench"
        return f"bin/bench {binary.stat().st_size / 1e6:.1f} MB (tek dosya)" if binary.exists() else "-"


APPS_BY_NAME = {"kurt": Kurt("kurt", 4101, "bench_kurt"), "rails": Rails("rails", 4102, "bench_rails"),
                "kemal": Kemal("kemal", 4103, "bench_kemal")}


def run(cmd, **kw):
    print("  $", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True, **kw)


def reseed(app, quiet=False):
    """The seed rows again, then a database with nothing left to do: the
    autovacuum and checkpoint the INSERTs would start run now, not during
    the next measurement."""
    url = f"{PG_HOST}/{app.db}"
    cmd = ["psql", "-q", "-v", "ON_ERROR_STOP=1", url, "-f", str(SEED), "-c", "VACUUM ANALYZE", "-c", "CHECKPOINT"]
    if not quiet:
        print("  $", " ".join(cmd[:6]), "+ VACUUM ANALYZE, CHECKPOINT", flush=True)
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL)


def csrf_headers(app):
    """A session cookie and its CSRF token, for the POST scenario."""
    with urllib.request.urlopen(app.url("/bench/csrf"), timeout=5) as r:
        token = r.read().decode()
        cookies = [h.split(";", 1)[0] for k, h in r.headers.items() if k.lower() == "set-cookie"]
    return ["-H", f"Cookie: {'; '.join(cookies)}", "-H", f"X-CSRF-Token: {token}"]


def oha(app, scenario, seconds, opts, out=None):
    name, method, path, regex, _ = scenario
    cmd = ["oha", "--no-tui", "-z", f"{seconds}s", "-c", str(opts.connections), "--output-format", "json"]
    if opts.rate:
        cmd += ["-q", str(opts.rate), "--latency-correction"]
    if method == "POST":
        cmd += ["-m", "POST", "-T", "application/x-www-form-urlencoded", "-d", CREATE_BODY] + csrf_headers(app)
    cmd += (["--rand-regex-url"] if regex else []) + [app.url(path)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise SystemExit(f"oha failed for {app.name}/{name}: {result.stderr}")
    if out:
        out.write_text(result.stdout)
    return json.loads(result.stdout)


class RssSampler(threading.Thread):
    """The server's peak memory while a scenario runs."""

    def __init__(self, app):
        super().__init__(daemon=True)
        self.app, self.peak, self.done = app, 0, threading.Event()

    def run(self):
        while not self.done.wait(0.5):
            self.peak = max(self.peak, self.app.rss_kb())


# ---------------------------------------------------------------- commands

def cmd_setup(opts):
    for app in APPS_BY_NAME.values():
        print(f"== {app.name}")
        subprocess.run(["createdb", app.db], capture_output=True)  # already there is fine
        app.build()
        app.migrate()
        reseed(app)


def normalise_html(text):
    # The layouts differ only in the brand; whitespace between tags is the
    # templates', not the frameworks'.
    for brand in ("Kurt", "Rails", "Kemal"):
        text = text.replace(brand, "APP")
    return "".join(line.strip() for line in text.split("\n"))


def fetch(app, path, method="GET", headers=None, body=None):
    req = urllib.request.Request(app.url(path), method=method, data=body, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, r.headers.get("Content-Type", ""), r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("Content-Type", ""), e.read().decode()


def compare(apps):
    """Every endpoint answers the same status, type and body as the first app."""
    probes = [("plaintext", "/bench/plaintext"), ("json", "/bench/json"), ("show", "/bench/posts/42"),
              ("show 404", "/bench/posts/999999"), ("feed", "/bench/feed"), ("page", "/bench/posts/42/page")]
    failures = 0
    for label, path in probes:
        answers = [fetch(app, path) for app in apps]
        failures += report_probe(label, answers)
    # POST: a valid post, then one validation refuses
    answers_ok, answers_bad = [], []
    for app in apps:
        hs = csrf_headers(app)
        headers = {hs[1].split(": ", 1)[0]: hs[1].split(": ", 1)[1], hs[3].split(": ", 1)[0]: hs[3].split(": ", 1)[1],
                   "Content-Type": "application/x-www-form-urlencoded"}
        answers_ok.append(fetch(app, "/bench/posts", "POST", headers, CREATE_BODY.encode()))
        answers_bad.append(fetch(app, "/bench/posts", "POST", headers, b"post%5Btitle%5D=&post%5Buser_id%5D=7"))
    failures += report_probe("create", answers_ok)
    failures += report_probe("create 422", answers_bad, status_only=True)
    return failures


def report_probe(label, answers, status_only=False, names=None):
    names = names or [a.name for a in CHECKED]
    failures = 0
    for name, other in zip(names[1:], answers[1:]):
        failures += report_pair(f"{label} ({names[0]}/{name})", answers[0], other, names[0], name, status_only)
    return failures


def report_pair(label, first, second, name1, name2, status_only):
    (s1, t1, b1), (s2, t2, b2) = first, second
    problems = []
    if s1 != s2:
        problems.append(f"status {s1} != {s2}")
    if not status_only and s1 < 400:
        if t1.split(";")[0] != t2.split(";")[0]:
            problems.append(f"type {t1} != {t2}")
        elif "json" in t1:
            if json.loads(b1) != json.loads(b2):
                problems.append("JSON bodies differ")
        elif "html" in t1:
            if normalise_html(b1) != normalise_html(b2):
                problems.append("HTML bodies differ")
        elif b1 != b2:
            problems.append("bodies differ")
    print(f"  {'ok  ' if not problems else 'FAIL'} {label:<24} {s1} {len(b1):>6}B {len(b2):>6}B  {'; '.join(problems)}")
    if problems and "differ" in " ".join(problems):
        print(f"    {name1}:", b1[:300].replace("\n", " "))
        print(f"    {name2}:", b2[:300].replace("\n", " "))
    return 1 if problems else 0


CHECKED = []


def cmd_check(opts):
    apps = [APPS_BY_NAME[n] for n in opts.frameworks.split(",")]
    CHECKED[:] = apps
    logs = Path(os.environ.get("TMPDIR", "/tmp"))
    try:
        for app in apps:
            reseed(app)
            app.start(opts, logs / f"bench-{app.name}.log")
        failures = compare(apps)
    finally:
        for app in apps:
            app.stop()
    print("all endpoints agree" if failures == 0 else f"{failures} endpoint(s) disagree")
    return 1 if failures else 0


def cmd_run(opts):
    names = opts.frameworks.split(",")
    wanted = opts.scenarios.split(",") if opts.scenarios else [s[0] for s in SCENARIOS]
    scenarios = [s for s in SCENARIOS if s[0] in wanted]
    for tool in ("oha", "psql"):
        if not shutil.which(tool):
            raise SystemExit(f"{tool} is not on PATH")
    out_dir = RESULTS / datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir.mkdir(parents=True)
    meta = {"options": vars(opts), "machine": machine(), "git": git_rev(), "frameworks": {}}
    apps = [APPS_BY_NAME[n] for n in names]

    # Both servers stay up for the whole run and take turns: kurt, rails,
    # rails, kurt, ... A laptop's speed drifts (heat, other programs); in
    # turns, both see the same drift. An idle server costs the other nothing.
    try:
        for app in apps:
            reseed(app)
            startup = app.start(opts, out_dir / f"{app.name}.log")
            idle = app.rss_kb()
            print(f"== {app.name}: up in {startup:.2f}s, {idle / 1024:.0f} MB idle", flush=True)
            meta["frameworks"][app.name] = {"startup_s": startup, "idle_rss_kb": idle,
                                            "artifact": app.artifact(), "version": version(app.name)}
        # One warm-up over every scenario before any is measured: the first
        # scenario measured was otherwise 3-4x slower than its later runs on
        # both servers (CPU clocks, the scheduler, a cold JIT and allocator).
        print("== warm-up", flush=True)
        for scenario in SCENARIOS:
            for app in apps:
                oha(app, scenario, opts.warmup, opts)
        for scenario in scenarios:
            sname = scenario[0]
            print(f"== {sname}", flush=True)
            for app in apps:
                # A warm-up the results never see: YJIT compiles, pools fill.
                oha(app, scenario, opts.warmup, opts)
            for i in range(1, opts.runs + 1):
                for app in (apps if i % 2 else list(reversed(apps))):
                    # Every run starts from the same rows (`create` adds some).
                    reseed(app, quiet=True)
                    measure(app, scenario, i, opts, out_dir)
    finally:
        for app in apps:
            app.stop()
    (out_dir / "meta.json").write_text(json.dumps(meta, indent=2))
    write_summary(out_dir)
    print(f"\n{out_dir / 'summary.md'}")


def measure(app, scenario, i, opts, out_dir):
    sname = scenario[0]
    path = out_dir / f"{app.name}-{sname}-{i}.json"
    sampler = RssSampler(app)
    sampler.start()
    data = oha(app, scenario, opts.duration, opts)
    sampler.done.set()
    sampler.join()
    data["peak_rss_kb"] = sampler.peak
    path.write_text(json.dumps(data))
    s = data["summary"]
    print(f"  {app.name:<6} run {i}: {s['requestsPerSec']:>9.0f} req/s  "
          f"p50 {data['latencyPercentiles']['p50'] * 1000:7.2f} ms  "
          f"p99 {data['latencyPercentiles']['p99'] * 1000:8.2f} ms  "
          f"ok {s['successRate'] * 100:5.1f}%  {sampler.peak / 1024:5.0f} MB", flush=True)


def write_summary(out_dir):
    meta = json.loads((out_dir / "meta.json").read_text())
    opts = meta["options"]
    names = list(meta["frameworks"])
    # Kurt against each of the others, when Kurt was measured.
    ratios = [n for n in names if n != "kurt"] if "kurt" in names else []
    lines = [f"# {' vs '.join(n.capitalize() for n in names)} — {out_dir.name}", "",
             f"Makine: {meta['machine']}  ",
             f"Commit: `{meta['git']}`  ",
             f"Ayar: {opts['workers']} worker (Kurt, Kemal: thread; Rails: Puma süreci × {opts['threads']} thread), "
             f"{opts['connections']} bağlantı, "
             f"{opts['duration']} s × {opts['runs']} koşu (medyan), {opts['warmup']} s ısınma"
             + (f", sabit hız {opts['rate']} req/s" if opts.get("rate") else ", en yüksek hız"), "",
             "| | " + " | ".join(names) + " |", "|---|" + "---|" * len(names)]
    for key, label, fmt in [("version", "Sürüm", str), ("startup_s", "Açılış", lambda v: f"{v:.2f} s"),
                            ("idle_rss_kb", "Boşta bellek", lambda v: f"{v / 1024:.0f} MB"),
                            ("artifact", "Dağıtılan", str)]:
        lines.append(f"| {label} | " + " | ".join(fmt(meta["frameworks"][n][key]) for n in names) + " |")
    lines += ["", "req/s: medyan (en düşük–en yüksek koşu). Gecikme ve bellek: koşuların medyanı / en yükseği.", "",
              "| Senaryo | " + " | ".join(f"{n} req/s" for n in names)
              + "".join(f" | Kurt/{n.capitalize()}" for n in ratios)
              + " | " + " | ".join(f"{n} p50 / p99 ms" for n in names)
              + " | " + " | ".join(f"{n} tepe bellek" for n in names) + " |"]
    lines.append("|---" * (1 + len(names) * 3 + len(ratios)) + "|")
    for sname, *_ in SCENARIOS:
        per = {}
        for n in names:
            runs = [json.loads(p.read_text()) for p in sorted(out_dir.glob(f"{n}-{sname}-*.json"))]
            if runs:
                per[n] = {
                    "rps": statistics.median(r["summary"]["requestsPerSec"] for r in runs),
                    "lo": min(r["summary"]["requestsPerSec"] for r in runs),
                    "hi": max(r["summary"]["requestsPerSec"] for r in runs),
                    "p50": statistics.median(r["latencyPercentiles"]["p50"] for r in runs) * 1000,
                    "p99": statistics.median(r["latencyPercentiles"]["p99"] for r in runs) * 1000,
                    "rss": max(r.get("peak_rss_kb", 0) for r in runs) / 1024,
                    "ok": min(r["summary"]["successRate"] for r in runs),
                }
        if len(per) != len(names):
            continue
        row = [sname] + [f"{per[n]['rps']:,.0f} ({per[n]['lo']:,.0f}–{per[n]['hi']:,.0f})"
                         + ("" if per[n]["ok"] == 1 else f" ⚠ {per[n]['ok'] * 100:.1f}% ok")
                         for n in names]
        row += [f"{per['kurt']['rps'] / per[n]['rps']:.2f}×" for n in ratios]
        row += [f"{per[n]['p50']:.2f} / {per[n]['p99']:.2f}" for n in names]
        row += [f"{per[n]['rss']:.0f} MB" for n in names]
        lines.append("| " + " | ".join(row) + " |")
    lines += ["", "Senaryolar:", ""] + [f"- **{s[0]}** `{s[1]} {s[2]}`: {s[4]}" for s in SCENARIOS]
    (out_dir / "summary.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


def machine():
    try:
        cpu = subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"], capture_output=True, text=True).stdout.strip()
        mem = int(subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True).stdout) // 2**30
        return f"{cpu}, {os.cpu_count()} çekirdek, {mem} GB, {sys.platform}"
    except Exception:
        return f"{os.cpu_count()} çekirdek, {sys.platform}"


def git_rev():
    r = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=REPO, capture_output=True, text=True)
    dirty = subprocess.run(["git", "status", "--porcelain"], cwd=REPO, capture_output=True, text=True).stdout
    return r.stdout.strip() + ("+değişiklik" if dirty.strip() else "")


def version(name):
    if name == "kurt":
        iyi = subprocess.run(["iyi", "version"], capture_output=True, text=True).stdout.split("(")[0].strip()
        return f"Kurt (checkout), {iyi}"
    if name == "kemal":
        lock = (APPS / "kemal" / "shard.lock").read_text()
        kemal = lock.split("kemal:\n", 1)[1].split("version: ", 1)[1].split("\n", 1)[0]
        crystal = subprocess.run(["crystal", "--version"], capture_output=True, text=True).stdout.split("(")[0].strip()
        return f"Kemal {kemal}, {crystal}"
    app = APPS_BY_NAME["rails"]
    out = subprocess.run(["bundle", "exec", "ruby", "--yjit", "-e",
                          "require 'rails'; print \"Rails #{Rails.version}, Ruby #{RUBY_VERSION}\""],
                         cwd=app.dir, env=app.ruby_env(), capture_output=True, text=True).stdout
    return out.strip() + " + YJIT"


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("command", choices=["setup", "check", "run", "report"])
    p.add_argument("dir", nargs="?")
    p.add_argument("--frameworks", default="kurt,rails,kemal")
    p.add_argument("--scenarios", default="")
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--threads", type=int, default=3)
    p.add_argument("--connections", type=int, default=64)
    p.add_argument("--duration", type=int, default=15)
    p.add_argument("--warmup", type=int, default=5)
    p.add_argument("--runs", type=int, default=3)
    p.add_argument("--rate", type=int, default=0)
    opts = p.parse_args()
    if opts.command == "report":
        write_summary(Path(opts.dir))
        return 0
    return {"setup": cmd_setup, "check": cmd_check, "run": cmd_run}[opts.command](opts) or 0


if __name__ == "__main__":
    sys.exit(main())
