# Kurt vs Rails vs Kemal — 20261126-111555

Makine: Apple M2 Pro, 12 çekirdek, 16 GB, darwin  
Commit: `98a5b4f+değişiklik`  
Ayar: 4 worker (Kurt, Kemal: thread; Rails: Puma süreci × 3 thread), 64 bağlantı, 10 s × 3 koşu (medyan), 5 s ısınma, en yüksek hız

| | kurt | rails | kemal |
|---|---|---|---|
| Sürüm | Kurt (checkout), iyi 0.22.0 | Rails 8.1.4.1, Ruby 4.0.7 + YJIT | Kemal 1.15.0, Crystal 1.22.3 |
| Açılış | 0.07 s | 0.93 s | 0.06 s |
| Boşta bellek | 11 MB | 218 MB | 7 MB |
| Dağıtılan | bin/kurt 5.3 MB (tek dosya) | uygulama + Ruby + gem'ler | bin/bench 2.4 MB (tek dosya) |

req/s: medyan (en düşük–en yüksek koşu). Gecikme ve bellek: koşuların medyanı / en yükseği.

| Senaryo | kurt req/s | rails req/s | kemal req/s | Kurt/Rails | Kurt/Kemal | kurt p50 / p99 ms | rails p50 / p99 ms | kemal p50 / p99 ms | kurt tepe bellek | rails tepe bellek | kemal tepe bellek |
|---|---|---|---|---|---|---|---|---|---|---|---|
| plaintext | 86,924 (85,503–87,004) | 9,276 (9,211–9,373) | 68,336 (66,435–68,421) | 9.37× | 1.27× | 0.68 / 2.27 | 6.68 / 11.48 | 0.95 / 1.77 | 152 MB | 529 MB | 28 MB |
| json | 86,267 (85,671–86,350) | 9,835 (9,655–9,941) | 66,275 (65,730–67,000) | 8.77× | 1.30× | 0.67 / 2.45 | 6.36 / 10.88 | 0.97 / 1.81 | 160 MB | 530 MB | 27 MB |
| show | 37,932 (35,189–38,187) | 7,199 (6,891–7,399) | 33,796 (32,732–34,371) | 5.27× | 1.12× | 0.30 / 2.84 | 8.46 / 17.08 | 0.41 / 1.38 | 131 MB | 284 MB | 26 MB |
| feed | 12,247 (12,164–12,364) | 2,344 (2,326–2,348) | 10,967 (10,733–11,058) | 5.23× | 1.12× | 0.69 / 201.25 | 27.02 / 34.72 | 1.16 / 201.96 | 97 MB | 420 MB | 38 MB |
| page | 26,265 (26,124–26,397) | 4,681 (4,666–4,692) | 20,648 (20,641–20,714) | 5.61× | 1.27× | 0.40 / 3.75 | 13.45 / 17.55 | 0.58 / 200.76 | 102 MB | 353 MB | 30 MB |
| create | 15,007 (14,089–15,040) | 2,852 (2,851–3,045) | 13,900 (13,879–14,604) | 5.26× | 1.08× | 3.75 / 8.60 | 21.70 / 43.89 | 4.24 / 17.42 | 95 MB | 397 MB | 33 MB |

Senaryolar:

- **plaintext** `GET /bench/plaintext`: router, middleware, a text body
- **json** `GET /bench/json`: the same plus JSON encoding
- **show** `GET /bench/posts/[1-9][0-9]{0,3}`: one SELECT by primary key, a model to JSON
- **feed** `GET /bench/feed`: 20 posts + includes(:comments): two queries, 120 rows to JSON
- **page** `GET /bench/posts/[1-9][0-9]{0,3}/page`: two queries, layout, view, 5 partials, HTML escaping
- **create** `POST /bench/posts`: session, CSRF, strong params, validation, a transaction of two INSERTs
