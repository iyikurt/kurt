# Kurt, Rails ve Kemal karşılaştırması

Aynı uygulama üç kez yazıldı: Kurt, Rails ve Kemal (Crystal) ile. Üçü de aynı
PostgreSQL'e (ayrı veritabanlarına) ve aynı satırlara bağlanır, aynı
istekleri aynı yük aracıyla karşılar.

```sh
make -C ..                         # bin/kurt
brew install oha crystal           # yük aracı; Kemal için Crystal ve shards
python3 bench.py setup             # uygulamaları derler, veritabanlarını kurar
python3 bench.py check             # her endpoint her uygulamada aynı yanıtı veriyor mu
python3 bench.py run               # ölçüm: results/<zaman>/summary.md
```

`run` seçenekleri: `--workers 4` (Kurt'un ve Kemal'in thread'leri, Puma'nın süreçleri),
`--threads 3` (Puma'da süreç başına thread), `--connections 64`,
`--duration 15`, `--warmup 5`, `--runs 3`, `--scenarios feed,page`,
`--frameworks kurt,kemal` ve `--rate 2000`. Sonuncusu sabit hızda ölçer; o zaman
gecikme coordinated omission için düzeltilir. `python3 bench.py report
results/<zaman>` özeti JSON dosyalarından yeniden yazar.

## Senaryolar

| Ad | İstek | Ölçtüğü |
|---|---|---|
| plaintext | `GET /bench/plaintext` | router, ara katmanlar, düz metin |
| json | `GET /bench/json` | üstüne JSON yazımı |
| show | `GET /bench/posts/:id` (rastgele 1–9999) | birincil anahtarla tek SELECT, modelden JSON |
| feed | `GET /bench/feed` | 20 yazı + `includes(:comments)`: iki sorgu, 120 satır JSON'a |
| page | `GET /bench/posts/:id/page` | iki sorgu, layout, view, 5 partial, HTML kaçışı |
| create | `POST /bench/posts` | oturum, CSRF, strong params, doğrulama, iki INSERT'lük transaction |

Kodlar: [apps/kurt/app/controllers/bench_controller.iyi](apps/kurt/app/controllers/bench_controller.iyi),
[apps/rails/app/controllers/bench_controller.rb](apps/rails/app/controllers/bench_controller.rb) ve
[apps/kemal/src/bench.cr](apps/kemal/src/bench.cr).
Veri: [db/seed.sql](db/seed.sql). İçinde 100 kullanıcı, 10.000 yazı (yarısı
yayında) ve yazı başına 5 yorum var. Gövdeler `<`, `&` ve `"` içerir, böylece
kaçış da ölçülür.

## Eşit şartlar

- `check`, ölçümden önce her yanıtı karşılaştırır: status, içerik tipi ve
  gövde (JSON ayrıştırılarak, HTML'de yalnız marka adı farklı). Biri farklıysa
  sonuçlar geçersizdir.
- İki taraf da production modunda çalışır. Kurt `kurt build` ile derlenmiş
  binary olarak koşar; Rails Ruby 4.0 ve YJIT ile (production'da açık).
  İkisinde de istek logu açıktır (Rails `info`).
- Eşzamanlılık: Kurt'ta `-w N` thread ve her bağlantı bir task. Kemal'de
  Crystal 1.22'nin varsayılan paralel execution context'i `CRYSTAL_WORKERS=N`
  thread'e büyütülür (her bağlantı bir fiber). Rails'te Puma N süreç × 3
  thread. Veritabanı havuzu üç tarafta da N×3 bağlantıdır. Kurt'ta
  bu havuz tamamen açık tutulur (`max_idle_pool_size`); db paketinin varsayılanı
  yalnız 1 boşta bağlantı tutar, bu da yük altında sürekli bağlan-kapat demektir.
  crystal-db'nin varsayılanı da aynı, Kemal'e de aynı ayar verilir.
- Rails'ten `rails new`'in iki varsayılanı çıkarıldı: `allow_browser` (her
  isteğin User-Agent'ını ayrıştırır, Kurt'ta karşılığı yok) ve `force_ssl`
  (Kurt da yönlendirmez). Tablolarda yabancı anahtar kısıtı yok, çünkü Kurt'un
  generator'ı da yazmıyor. Her `*_id` sütununda bir index var.
- İki sunucu bütün koşu boyunca açık kalır ve sırayla ölçülür (kurt, rails,
  rails, kurt...). Böylece makinenin yavaşlaması (ısı, başka programlar) ikisine
  eşit düşer. Her ölçümden önce satırlar yeniden yüklenir, `VACUUM ANALYZE`
  ve `CHECKPOINT` çalışır. Böylece önceki senaryonun INSERT'leri ölçüme
  karışmaz.
- Ölçümden önce bütün senaryolar bir kez ısınma için koşulur, her senaryodan
  önce de bir kez daha (YJIT derler, havuzlar dolar). İlk ölçülen senaryo
  bunsuz 3–4 kat yavaş çıkıyordu.

## Kemal'in farkları

Kemal bir mikro-framework: ORM, doğrulama, strong params, oturum ve CSRF
çekirdeğinde yok. Uygulama bunları Kemal'de yazılacağı gibi yazar: SQL
crystal-db ile elle (`DB::Serializable`), doğrulama elle, şablonlar ECR ile.
ECR kaçış yapmadığı için her çıktı `HTML.escape`'ten geçer. Bu yüzden Kemal'in
sayıları "ORM'siz bir uygulama" ölçüsüdür. Kurt ile arasındaki fark kabaca
Kurt'un model ve view katmanının maliyetini gösterir.

Oturum ve CSRF için `kemal-session` ve `kemal-csrf` kullanılmadı:

- `kemal-csrf` her başarılı POST'tan sonra token'ı değiştirir. Sabit bir
  token'la yük testi yapılamaz (ve aynı formu açık iki sekme bozulur).
- `kemal-session`'ın bellek motoru kilitsiz bir `Hash`, yani birden çok
  thread'de güvenli değil.

Yerine uygulamada ~50 satırlık bir katman var: oturum HMAC ile imzalı bir
cookie'de durur, CSRF token'ı oturum boyunca aynı kalır (Rails ve Kurt gibi).
Oturum yalnız kullanıldığında okunur ve yeni olduğunda yazılır. Rails ve Kurt
ise cookie'yi şifreler (AES-GCM); imzalamak biraz daha ucuzdur.

## Sınırlar

- Yük aracı, veritabanı ve sunucu aynı makinede çalışıyor ve aynı çekirdekleri
  paylaşıyor. Mutlak sayılar makineye ve o anki yüke bağlı; iki çerçeve
  arasındaki oran daha anlamlıdır. Koşudan koşuya ±%30 oynama görüldü, özette
  en düşük–en yüksek aralığı bu yüzden yazılıyor. Sağlam sayılar için ayrı bir
  Linux makine ya da en azından sunucuyu ve oha'yı ayrı çekirdeklere bağlamak
  (`taskset`) gerekir.
- macOS'ta Puma'nın fork'undan sonra libpq çöküyor (objc fork güvenliği).
  `PGGSSENCMODE=disable` bunu önler, başka bir şeyi değiştirmez.
- Kurt'ta `feed`'de, Kemal'de `feed` ve `page`'de p99 her koşuda tam ~200 ms
  çıkıyor (p50 1 ms'nin altında). Rails'te bu yok. İki sorgulu senaryolarda
  görülüp tek sorgulu `show`'da görülmemesi ve 200 ms'nin macOS'taki
  gecikmeli ACK süresi olması, Crystal tabanlı Postgres sürücülerinde (crystal-pg
  ve onun iyi'deki karşılığı) Nagle ile gecikmeli ACK etkileşimine
  (`TCP_NODELAY` yok) işaret ediyor. Rails libpq kullanıyor. Bu henüz
  doğrulanmadı.
- Kemal'in 404 sayfası 25 KB'lık bir HTML. Ölçülen senaryolarda 404 yok.
- Kurt'ta `-w N` tek başına çöküyor: iyi'nin worker havuzu sunucu boyutu
  ayarlamadan önce varsayılan boyutla başlıyor. `bench.py` `IYI_WORKERS=N`'i de
  veriyor.
- Giriş (bcrypt) ölçülmüyor, çünkü bilerek yavaş ve iki tarafta aynı
  maliyetle çalışıyor.
