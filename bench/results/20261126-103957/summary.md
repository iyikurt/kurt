# Kurt vs Rails — 20261126-103957

Makine: Apple M2 Pro, 12 çekirdek, 16 GB, darwin  
Commit: `98a5b4f+değişiklik`  
Ayar: 4 worker (Puma'da × 3 thread), 64 bağlantı, 10 s × 3 koşu (medyan), 5 s ısınma, en yüksek hız

| | kurt | rails |
|---|---|---|
| Sürüm | Kurt (checkout), iyi 0.22.0 | Rails 8.1.4.1, Ruby 4.0.7 + YJIT |
| Açılış | 0.07 s | 1.31 s |
| Boşta bellek | 11 MB | 214 MB |
| Dağıtılan | bin/kurt 5.3 MB (tek dosya) | uygulama + Ruby + gem'ler |

req/s: medyan (en düşük–en yüksek koşu). Gecikme ve bellek: koşuların medyanı / en yükseği.

| Senaryo | kurt req/s | rails req/s | Kurt/Rails | kurt p50 / p99 ms | rails p50 / p99 ms | kurt tepe bellek | rails tepe bellek |
|---|---|---|---|---|---|---|---|
| plaintext | 86,982 (85,113–87,496) | 9,319 (9,044–9,344) | 9.3× | 0.67 / 2.38 | 6.67 / 11.61 | 176 MB | 538 MB |
| json | 86,091 (84,068–86,501) | 9,755 (9,646–9,866) | 8.8× | 0.67 / 2.46 | 6.43 / 10.19 | 219 MB | 458 MB |
| show | 36,926 (36,451–39,465) | 7,757 (7,625–7,805) | 4.8× | 0.31 / 2.86 | 8.16 / 11.45 | 236 MB | 357 MB |
| feed | 12,582 (12,077–12,602) | 2,297 (2,276–2,320) | 5.5× | 0.68 / 201.38 | 27.49 / 43.49 | 188 MB | 406 MB |
| page | 25,583 (25,574–25,808) | 4,520 (4,356–4,721) | 5.7× | 0.40 / 4.29 | 13.91 / 18.71 | 151 MB | 414 MB |
| create | 15,288 (15,121–15,593) | 3,183 (3,162–3,213) | 4.8× | 3.70 / 8.42 | 19.90 / 24.14 | 112 MB | 487 MB |

Senaryolar:

- **plaintext** `GET /bench/plaintext`: router, middleware, a text body
- **json** `GET /bench/json`: the same plus JSON encoding
- **show** `GET /bench/posts/[1-9][0-9]{0,3}`: one SELECT by primary key, a model to JSON
- **feed** `GET /bench/feed`: 20 posts + includes(:comments): two queries, 120 rows to JSON
- **page** `GET /bench/posts/[1-9][0-9]{0,3}/page`: two queries, layout, view, 5 partials, HTML escaping
- **create** `POST /bench/posts`: session, CSRF, strong params, validation, a transaction of two INSERTs
