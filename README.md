<p align="center"><img src="kurt.svg" alt="Kurt" width="160"></p>

# Kurt

iyi için Rails benzeri bir web framework'ü. HTTP, router, şablon, oturum ve
CSRF [iyi-web](https://github.com/sdogruyol/iyi-web)'den; SQL, havuz ve
transaction [db](https://github.com/iyilang/db)'den gelir. Kurt bunların
üstüne konvansiyon katmanını koyar: model, controller, migration ve CLI.

```sh
kurt new blog
cd blog
kurt generate scaffold Post title:string body:text published:bool
kurt db:migrate
kurt dev            # http://localhost:3000/posts
```

Gereken: iyi 0.21.0 veya üstü (0.22.0 ile denendi), bir C derleyicisi (`cc`),
SQLite (macOS'ta sistemde var). PostgreSQL isteğe bağlı.

## Kurulum

```sh
git clone https://github.com/iyikurt/kurt.git ~/src/kurt
cd ~/src/kurt
make install           # bin/kurt, ~/.local/bin/kurt'e bağlanır
export PATH="$HOME/.local/bin:$PATH"
kurt version
```

Kurt bir iyi paketidir: `github.com/iyikurt/kurt`, sürümleri git etiketleri
(`v0.1.0`). `kurt new` uygulamanın `iyi.mod` dosyasına komutun kendi
sürümünü yazar; iyi paketi ilk derlemede indirir. Uygulamaların dosyaları
onu `kurt/...` diye import eder:

```
require github.com/iyikurt/kurt v0.1.0 as kurt
```

Kurt'un kendisi üzerinde çalışırken `KURT_PATH=~/src/kurt kurt new app`
yayınlanan sürüm yerine checkout'u kullanan bir `replace` satırı ekler.

## Komutlar

| Komut | Ne yapar |
|---|---|
| `kurt new NAME [--css none]` | `./NAME` altında yeni uygulama; Tailwind CSS ve daisyUI ile, `--css none` ile onlarsız |
| `kurt generate scaffold NAME FIELD...` | model, migration, controller, beş view, route, test |
| `kurt generate model NAME FIELD...` | model ve migration |
| `kurt generate controller NAME ACTION...` | controller, view'lar, route'lar |
| `kurt generate migration NAME` | boş migration |
| `kurt generate authentication` | kullanıcılar, giriş, kayıt; her sayfa giriş ister |
| `kurt db:migrate` / `db:rollback [N]` / `db:status` / `db:reset` | şema (`db:reset` sonra seed'ler de) |
| `kurt db:seed` | `db/seeds.iyi`'yi çalıştırır |
| `kurt routes` | bütün route'ları yol ve `Controller#action` ile listeler |
| `kurt dev [-p PORT]` | sunucu; değişiklikte yeniden derler, yeniden başlatır, sayfayı yeniler |
| `kurt test` | taze bir test veritabanını migrate eder, her `test/*_test.iyi`'yi fixture'larla çalıştırır |
| `kurt build` | `bin/NAME` altında release binary (CSS'i de küçültülmüş derler, migration'lar içinde) |
| `kurt css:build [--minify]` | `app/assets/tailwind/app.css`'i `public/assets/app.css`'e derler |
| `kurt css:install` | Tailwind CLI'ı ve daisyUI'yi indirir (çevrimdışı kurulduysa) |

Alan tipleri: `string`, `text`, `int`, `float`, `bool`, `time`,
`references` (`user:references` → `user_id` sütunu ve `belongs_to user`).

Veritabanı `DATABASE_URL`, yoksa `sqlite3:./db/<env>.sqlite3`; ortam
`KURT_ENV` (varsayılan `development`). `postgres://` bir URL ile aynı
uygulama PostgreSQL'de çalışır, generator'lar da migration'ları o lehçede yazar.

## Uygulama düzeni

Bir uygulamanın `.iyi` dosyalarında modül başlığı ve import yok:

```
config/application.iyi     açılışta çalışır: ara katmanlar, ayarlar
config/routes.iyi          route'lar
app/models/post.iyi        class Post < ApplicationRecord
app/controllers/posts_controller.iyi
app/views/posts/index.eiy
db/migrations/20261123153000_create_posts.sql
db/seeds.iyi               yeni bir veritabanının ilk kayıtları
test/posts_test.iyi
test/fixtures/users.yml    testlerin başladığı kayıtlar
```

`kurt dev`, `kurt test` ve `kurt build` bu dosyalardan
`.kurt/build/` altında gerçek iyi modülleri üretir (Rails'teki autoloader'ın
karşılığı, [autoload.iyi](autoload.iyi)):

- bütün modeller tek bir `app/models` modülüne gider; `pub`, tablonun her
  sütunu için bir `property` (`db/schema.json`'dan) ve `derive model`
  eklenir. Böylece User ile Post birbirini serbestçe gösterir; iyi'de import
  döngüsü yasak (R-1), ama tek modül içinde döngü yok;
- bütün controller'lar tek bir `app/controllers` modülüne gider,
  ApplicationController önce; model değişkenleri (`@post`, `@posts`)
  konvansiyonla tanımlanır;
- `config/routes.iyi`, `def routes : Router`'ın gövdesi olur;
- her türe gereken import'lar eklenir. Başka bir modüle ihtiyaç duyan dosya,
  kendi `import` satırını en üste yazar; o satır modül başlığına taşınır.

Her parça bir konum pragma'sı taşır: derleme hatası üretilen dosyayı değil,
yazdığın dosyanın satırını gösterir (`In app/models/post.iyi:13:25`), `render`
da view'ı o dosyaya göre bulur. Bedeli: editördeki iyi LSP'si başlıksız bir
dosyayı tek başına denetleyemez.

## İlişkili kayıtlar formda

`user:references` gibi bir alan, scaffold'da `User` modeli varsa bir açılır
liste olur: seçenekler o tablonun ilk metin sütunuyla gösterilir (`name`,
yazılar için `title`; şemada yoksa `create_` migration'ından okunur). Listeyi
controller bir filtreyle yükler:

```iyi
before_action :set_users, only: [:new, :create, :edit, :update]

private def set_users
  @users = User.order(:name).all!
end
```

Göster ve liste sayfaları numara yerine adı basar. Seçilmeden gönderilen
form `user_id can't be blank` ile 422 döner. Şablonlar Crystal olarak
derlendiği için orada `!` ve `.or` yok; ilişki `is_a?` ile daraltılır:
`<% if (user = @post.user?).is_a?(User) %><%= user.name %><% end %>`.

## Kimlik doğrulama

```sh
kurt generate authentication
kurt db:migrate
```

Rails 8'deki `rails generate authentication` gibi; ayrıca kayıt olma da gelir:

| Yer | Ne |
|---|---|
| `app/models/user.iyi` | `has_secure_password`, e-posta (küçük harfe çevrilir, benzersiz), parola en az 8 karakter. `User` varsa ona eklenir. |
| migration | yeni tablo, ya da var olan `users`'a `password_digest` (ve e-posta sütunu yoksa o) |
| `SessionsController` | `GET/POST /login`, `DELETE /logout` |
| `RegistrationsController` | `GET/POST /signup` |
| `ApplicationController` | `before_action :require_authentication`, `current_user?` |
| view'lar, layout | giriş ve kayıt formları; navbar'da giriş/kayıt ya da çıkış |
| `test/sessions_test.iyi` | kayıt, giriş ve çıkış, gerçek oturum çereziyle |

Artık her sayfa giriş ister; giriş yapmamış biri `/login`'e gider ve girişten sonra
istediği sayfaya döner. Herkese açık sayfalar controller'da söylenir:

```iyi
class PostsController < ApplicationController
  allow_unauthenticated_access only: [:index, :show]
end
```

`allow_unauthenticated_access`, `skip_before_action :require_authentication`'ın
kısaltmasıdır; `skip_before_action` başka filtreler için de var. Bir view
`<% if user = current_user? %>` ile kimin giriş yaptığını sorar.

Parolalar bcrypt ile saklanır (`std/password`; testlerde en düşük maliyetle).
`has_secure_password` Rails'teki gibi davranır: kayıt yokken parola zorunludur,
en fazla 72 bayttır, `password_confirmation` verilmişse aynı olmalıdır; düzenleme
formunda boş bırakılan parola eskisini korur. `User.authenticate_by("email_address",
adres, parola)!` kullanıcıyı ya da nil döndürür; kullanıcı yoksa da bir parola
kontrol eder, böylece hangi adreslerin kayıtlı olduğu süreden anlaşılmaz.
Oturum açılırken oturum kimliği yenilenir.

Testlerde `sign_in_as(user)` sonraki istekleri o kullanıcıyla yapar (yalnız
`KURT_ENV=test`'te, `kurt test` onu ayarlar). Generator var olan testlere bir
`sign_in_as(...)` satırı ekler; sonradan üretilen scaffold testleri de onunla gelir.

Henüz yok: parola sıfırlama (e-posta gerektirir), giriş denemelerine hız sınırı,
"beni hatırla", oturumları veritabanında tutup uzaktan sonlandırma.

## Seed'ler ve test fixture'ları

`db/seeds.iyi` yeni bir veritabanının ilk kayıtlarını modellerle yazar.
`kurt db:seed` onu çalıştırır, `kurt db:reset` de migrate'ten sonra.
`find_or_create_by` var olanı bulur, yoksa oluşturur; dosya istendiği kadar
çalıştırılabilir. `!` burada da çalışır, hata olursa komut nedenini yazar:

```iyi
# db/seeds.iyi
ada = User.find_or_create_by(email: "ada@example.com") do |user|
  user.name = "Ada"                    # blok yalnız yeni kayıt için
  user.password = "password123"
end!
Post.find_or_create_by(title: "Hoş geldiniz", user_id: ada.id)!
```

Testler Rails'teki gibi `test/fixtures/<tablo>.yml` dosyalarındaki
kayıtlarla başlar. Her test dosyası fixture'ları baştan yükler; önceki bir
dosyanın sildiği ya da değiştirdiği kayıt geri gelir. Bir test kaydı
etiketiyle alır: `users(:ada)`.

```yaml
# test/fixtures/users.yml
ada:
  name: Ada
  email: ada@example.com
  password: password123      # password_digest'li tabloda bcrypt özeti olur

# test/fixtures/posts.yml
welcome:
  title: Hoş geldiniz
  user: ada                  # user_id: users.yml'deki ada'nın id'si
```

```iyi
# test/posts_test.iyi
sign_in_as(users(:ada))
assert posts(:welcome).user.as(User).name == "Ada"
```

Bir etiketin id'si her çalıştırmada aynıdır, fixture'lar birbirini böyle
gösterir. `created_at` / `updated_at` varsa doldurulur. Olmayan bir sütun ya
da tipine uymayan bir değer, testler başlamadan dosya ve etiketle söylenir.
Testlerin en üst düzeyinde `!` çalışmaz (iyi'de modül başlatılırken hata
iletilemez); orada `.as(User)` kullanılır.

## Tailwind CSS ve daisyUI

`kurt new` uygulamayı varsayılan olarak [Tailwind CSS](https://tailwindcss.com)
ve [daisyUI](https://daisyui.com) ile kurar; Node gerekmez. Tailwind'in tek
dosyalık CLI'ı (v4.3.5) ilk kurulumda `~/.cache/kurt/` altına bir kez indirilir
ve sürümün `sha256sums.txt`'iyle doğrulanır; daisyUI'nin iki dosyası (v5.8.2)
uygulamanın içine konur:

```
app/assets/tailwind/app.css            girdi: @import "tailwindcss", @plugin "./daisyui.mjs"
app/assets/tailwind/daisyui.mjs        daisyUI
app/assets/tailwind/daisyui-theme.mjs  kendi temanı yazmak için
public/assets/app.css                  çıktı (derlenir, git'e girmez)
```

`kurt dev` her derlemeden önce, `kurt build` küçültülmüş olarak CSS'i de
derler; bir view'a yeni bir sınıf yazıp kaydetmek yeter. Sınıflar
`app/views/**/*.eiy`'den okunur. Tema `app.css`'teki `@plugin` satırından
seçilir: iki tema kurulur, açık tema `light` ve koyu tema `dracula`. Sistem
karanlık moddaysa Dracula açılır; `<html data-theme="dracula">` ya da
`data-theme="light"` birini sabitler. Layout'taki navbar'da bir tema düğmesi var: iki tema
arasında geçiş yapar ve seçimi tarayıcıda (`localStorage`) hatırlar; seçim yoksa
sistem teması geçerlidir.

Scaffold'lar böyle bir uygulamada daisyUI bileşenleriyle gelir: `navbar`,
`btn`, `table`, `card`, `fieldset`, `input`/`select`/`textarea` (doğrulanmayan
alan `input-error` ile kırmızı), `alert`. `kurt new blog --css none` bunların
hiçbirini kurmaz; uygulama düz bir `public/assets/app.css` ve sade sınıflarla
gelir. İnternet yokken kurulan bir uygulama için sonradan `kurt css:install`.

## Yayına alma

`kurt build` uygulamayı tek bir çalıştırılabilir dosyaya derler; sunucuda iyi
ya da kaynak kod gerekmez. Migration'lar binary'nin içindedir:

```sh
kurt build                                   # bin/blog
scp -r bin/blog public sunucu:/srv/blog/     # public/ binary'nin yanında durur

# sunucuda
export KURT_ENV=production
export DATABASE_URL=postgres://app@db.local/blog
export SESSION_SECRET=$(openssl rand -hex 32)   # bir kez üretilir, saklanır
./bin/blog db:migrate                        # bekleyen migration'lar; db:status da var
./bin/blog -b 0.0.0.0 -p 8080
```

Production'da:

- `SESSION_SECRET` yoksa ya da 32 byte'tan kısaysa uygulama açılmaz.
  Geliştirme secret'ı repoda durduğu için onunla açılmak oturumları taklit
  edilebilir kılardı.
- Session cookie'si `Secure`'dur, yalnız HTTPS'te gider. Uygulama HTTPS'i
  sonlandıran bir proxy'nin (nginx, Caddy, yük dengeleyici) arkasında durur.
- `GET /up` uygulama ve veritabanı ayaktaysa 200 `OK`, değilse 503 döner;
  yük dengeleyicinin sağlık kontrolü içindir.
- Her yanıt `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`
  başlıklarını, HTTPS'te `Strict-Transport-Security`'yi taşır. Her istek bir
  `X-Request-Id` alır ve log satırına yazılır.
- `TERM` sinyali gelince sunucu yeni bağlantı almaz, süren istekleri
  bitirip kapanır.

Bunlar `config/application.iyi`'de birer satırdır, uygulama değiştirebilir.

## Hot reload

`kurt dev` `app/`, `config/`, `db/schema.json` ve `iyi.mod`'u izler. Bir
dosya değişince uygulamayı yan tarafta derler (birkaç saniye); derlenirse eski
sunucuyu kapatıp yenisini başlatır, açık sayfalar da kendiliğinden yenilenir
(layout'taki `<%= raw(live_reload_tag) %>`, yalnız `kurt dev` altında bir
script basar). Derlenmeyen bir değişiklik iyi'nin hatasını, yazdığın dosyanın
satırıyla gösterir ve son derlenen sunucu çalışmaya devam eder. `public/`
diskten sunulur, yeniden başlatma gerektirmez. `kurt dev --no-reload`
izlemeden çalıştırır.

## Model

Bir modelin alanları tablosundan gelir; model dosyası yalnızca davranışı
yazar:

```iyi
# app/models/post.iyi
# Columns of posts (db/schema.json, kept up to date by `kurt db:migrate`):
#   id          Int64
#   title       String
#   body        String
#   published   Bool
#   user_id     Int64
#   created_at  Time
#   updated_at  Time
class Post < ApplicationRecord
  belongs_to user : User
  has_many comments : Comment

  validates :title, :user_id, presence: true
  validates :title, length: {maximum: 120}

  def self.feed : Query(Post)
    query.where(published: true).order_desc(:created_at)
  end
end
```

### Doğrulamalar ve callback'ler

Rails'teki gibi sınıf gövdesine yazılır; her satır öncekilere eklenir:

```iyi
class User < ApplicationRecord
  validates :name, :email, presence: true
  validates :name, length: {maximum: 60}                 # minimum:, maximum:, is:, in: 2..60
  validates :email, format: /\A[^@\s]+@[^@\s]+\z/, uniqueness: true
  validates :role, inclusion: {in: ["admin", "member"]}, message: "must be admin or member"

  before_validation :normalize_email
  after_create :send_welcome

  def normalize_email
    @email = email.strip.downcase
  end

  # Kendi kuralların için: validates satırlarından sonra çalışır.
  def validate(errors : Errors) : Nil
    errors.add("name", "can't be root") if name == "root"
  end
end
```

| Kural | Mesaj |
|---|---|
| `presence: true` | `can't be blank` (boş metin, nil ya da hâlâ 0 olan bir `*_id`) |
| `length: {minimum: 2}` / `{maximum: 60}` / `{is: 5}` / `{in: 2..60}` | `is too short (minimum is 2 characters)` vb. |
| `format: /regex/` | `is invalid` |
| `inclusion: {in: [...]}` | `is not included in the list` |
| `uniqueness: true` | `has already been taken` (veritabanına sorar; kaydın kendisi sayılmaz) |

`message:` satırdaki bütün mesajların yerine geçer. `uniqueness` bir sorgudur:
yarış durumlarına karşı veritabanında bir `UNIQUE` index de olmalı. NULL olan bir
alan `length` ve `format`'tan geçer.

Callback'ler Rails'in sırasıyla çalışır: `before_validation`, (doğrulama),
`before_save`, `before_create` ya da `before_update`, (yazma), `after_create` ya
da `after_update`, `after_save`; silmede `before_destroy` ve `after_destroy`. Bir
callback `DBError` dönerse kayıt durur ve hata yukarı iletilir (`!` ile:
`Profile.create(user_id: id)!`); başka bir dönüş değeri yok sayılır. Scaffold
modelleri metin alanları ve bağlantılar için `validates ..., presence: true` ile
gelir.

### İlişkili kayıtları silmek

```iyi
class User < ApplicationRecord
  has_many posts : Post, dependent: :destroy        # her yazı kendi callback'leri ve
end                                                 # kendi dependent'larıyla silinir

class Post < ApplicationRecord
  has_many comments : Comment, dependent: :delete_all   # tek bir DELETE, yüklemeden
end
```

`has_one` de `dependent:` alır. Bağlı kayıtları olan bir model kendi
transaction'ında silinir: ya hepsi gider ya hiçbiri.

### Transaction

```iyi
Order.transaction do |tx|
  order.save(on: tx)!
  item.update(on: tx, quantity: 2)!
  Stock.where(product_id: item.product_id).on(tx).delete_all!
end
```

Bloğun döndürdüğü bir hata (`Invalid`, `NotFound`, `DBError`...) her şeyi geri
alır ve döner; bloktan `!` ile erken çıkmak da geri alır. Aksi halde commit
edilir ve bloğun değeri döner. `Order.transaction(on: tx) do |inner| ... end`
iç içe bir transaction (savepoint) açar; onun hatası yalnızca kendisini geri
alır.

Rails'ten farkı: transaction açıkça geçirilir (`on: tx`, `Post.on(tx).find(id)`,
`query.on(tx)`). Bir sunucu aynı anda birçok isteği çalıştırır; "şu anki
transaction"ı kendisi bulan bir sorgu başka bir isteğinkine düşebilirdi. Bir
callback, içinde çalıştığı kaydetmenin transaction'ını `current_transaction` ile
alır:

```iyi
after_create :open_profile

def open_profile
  Profile.create(user_id: id, on: current_transaction)!
end
```

`save` kendiliğinden bir transaction açmaz; kayıt ve callback'lerinin birlikte
yazılması gerekiyorsa onu bir `transaction` bloğunda kaydet.

Rails'teki `db/schema.rb` gibi: `kurt db:migrate` (ve `db:rollback`),
tabloları veritabanından okuyup `db/schema.json`'a yazar ve her modelin
başındaki sütun yorumunu yeniler (Rails'teki annotate gem'i gibi; derleyici o
yorumu okumaz). Derleme veritabanına değil bu dosyaya bakar ve her sütun için
bir `property` ekler. `db/schema.json` git'e girer.

| SQL | iyi |
|---|---|
| `TEXT`, `VARCHAR` | `String` |
| `INTEGER`, `BIGINT` | `Int64` (PostgreSQL'in 4 baytlık `integer`'ı `Int32`) |
| `REAL`, `DOUBLE PRECISION` | `Float64` |
| `BOOLEAN` | `Bool` |
| `DATETIME`, `TIMESTAMPTZ` | `Time` |
| `NULL` olabilen sütun | nilable (`String?`) |

SQLite'ın gerçek bir boolean ya da tarih tipi yok, ama sütunun bildirilen tip
adını saklıyor; generator'lar bu yüzden SQLite migration'larında da `BOOLEAN`
ve `DATETIME` yazar. Modelin kendi yazdığı bir `property` (başka bir tip, bir
varsayılan değer) şemanınkinin önüne geçer:

```iyi
class Post < ApplicationRecord
  property published : Bool = true
end
```

Yeni bir sütun için migration yazıp `kurt db:migrate` demek yeter; modele
dokunulmaz. Tablosu henüz migrate edilmemiş bir model için derleme uyarır.

```iyi
Post.all!                                      # Array(Post) | DBError
Post.find(id)!                                 # Post | NotFound | DBError; id bir sayı ya da params[:id]
Post.find?(id)!                                # Post? | DBError
Post.feed.paginate(page, per: 20).all!
Post.title("Merhaba").first?!                  # alan başına tipli sorgu; yanlış alan derleme hatası
Post.where(user_id: 5).count!
post.save!                                     # Bool | DBError: false ise nedenleri post.errors'ta
post.update(title: "Yeni")!                    # alanları atar ve kaydeder; save gibi Bool
post.update(post_params)!                      # formdan: izin verilmiş alanlar, tiplerine çevrilerek
post = Post.create(title: "Merhaba", body: "...", user_id: 1)!   # geçersizse Invalid'i iletir (422)
post.user!.name                                # belongs_to: tek sorgu
post.comments.order(:id).limit(5).all!         # has_many: tembel sorgu
post.increment(:comments_count)!
post.destroy!
```

### Önceden yükleme (`includes`)

Bir liste her satırın ilişkisine ayrı ayrı sorarsa 25 yazı 26 sorgu olur
(N+1). `includes` ilişkileri satırlarla birlikte, ilişki başına tek sorguyla
(`WHERE user_id IN (...)`) yükler; sonra `post.user!` ve `post.comments`
veritabanına bir daha gitmez:

```iyi
posts = Post.includes(:user, :comments).order_desc(:id).paginate(page).all!
posts.each do |post|
  post.user!.name                    # yüklendi, sorgu yok
  post.comments.count!               # yüklendi, sorgu yok
  post.comments.where(approved: true).all!   # daraltmak yeniden sorar
end
```

`belongs_to`, `has_many` ve `has_one` için çalışır; transaction içinde
(`Post.on(tx).includes(:user)`) ön yükleme sorguları da o transaction'da
koşar. Olmayan bir ilişki adı `DBError` döner. Scaffold'un liste sayfası,
adıyla gösterdiği referansları kendiliğinden `includes` ile yükler.

`Int64` bir alana `Int32` de verilebilir (`Post.create(user_id: 1)`).
`derive model` (autoload sınıfın sonuna ekler); tablo adını
(`@[Table("people")]` ile değiştirilir), satır eşlemeyi, her alanı isteğe
bağlı bir `new(**)`'u, sınıf ve örnek metotlarını ve alan başına bir sorgu
metodunu üretir. `created_at` / `updated_at` varsa `save` doldurur.

## Controller

```iyi
# app/controllers/posts_controller.iyi
class PostsController < ApplicationController
  before_action :require_login, except: [:index, :show]

  def index
    posts = Post.feed.all!
    render "posts/index"                   # app/views/posts/index.eiy, layouts/application.eiy içinde
  end

  def show
    post = Post.find(params[:id])!         # kayıt yoksa 404, kod yazmadan
    render "posts/show"
  end
end
```

```iyi
# config/routes.iyi
root HomeController, :index
resources "posts", PostsController       # controller'da olan action'lar için REST route'ları
get "/about", PagesController, :about    # post, put, patch, delete de var

resources "posts", PostsController do    # iç içe: /posts/:post_id/comments
  resources "comments", CommentsController
end

namespace "admin" do                     # /admin/users, /admin/users/:id ...
  resources "users", AdminUsersController
end
```

İç içe bir kaynağın controller'ı üst kaydı `params[:post_id]` ile bulur;
`param: "article_id"` adı değiştirir. `kurt routes` uygulamanın bütün
route'larını yazar:

```
$ kurt routes
  Verb    Path                       Controller#Action
  GET     /posts                     PostsController#index
  GET     /posts/:post_id/comments   CommentsController#index
  ...
```

Scaffold'un yazdığı controller Rails'tekiyle aynı biçimde:

```iyi
class PostsController < ApplicationController
  before_action :set_post, only: [:show, :edit, :update, :destroy]

  def index
    @posts = Post.order_desc(:id).all!
    render "posts/index"
  end

  def show
    render "posts/show"                    # view @post'u görür
  end

  def create
    @post = Post.new(post_params)
    if @post.save!
      redirect_to path_to(@post), notice: "Post was created."
    else
      render "posts/new", status: 422      # form, @post.errors'taki nedenlerle yeniden çizilir
    end
  end

  def update
    if @post.update(post_params)!
      redirect_to path_to(@post), notice: "Post was updated."
    else
      render "posts/edit", status: 422
    end
  end

  def destroy
    @post.destroy!
    redirect_to "/posts", notice: "Post was deleted."
  end

  private def set_post
    @post = Post.find(params[:id])!        # kayıt yoksa 404, action hiç çalışmaz
  end

  private def post_params : Hash(String, String)
    params.require(:post).permit(:title, :body, :published)
  end
end
```

`@post` ve `@posts` için tanım yazılmaz. iyi bir instance değişkeninin
tipini kendisi çıkaramaz, bu yüzden autoload konvansiyonla ekler: bir
controller'da bir modelin adını taşıyan değişken (`@post`) o modeli tutar ve
boş bir kayıtla başlar, çoğulu (`@posts`) o modelin dizisini tutar ve boş
başlar. İkisi de hiçbir zaman `nil` olmaz; action'lar ve view'lar onları
kontrol etmeden kullanır. Konvansiyona uymayan bir değişken tipiyle yazılır
(`@featured : Array(Post) = [] of Post`); açıkça yazılan tanım her zaman
önce gelir.
Filtreye dönüş tipi ya da sonda `nil` yazılmaz. `!` ile yukarı verdiği
`NotFound` (404) ya da `DBError` (503) action'ı durdurur; başka her dönüş
değeri (atanan kayıt, liste, `nil`) action'ı çalıştırır.

Formlar alanları `post[title]` diye gönderir; `params.require(:post)` onları
toplar, `permit` yalnız adı verilenleri bırakır. Model yalnız `permit`'in
döndürdüğü `Hash(String, String)`'i kabul eder (`Post.new(h)`,
`post.update(h)`, `Post.create(h)`): süzülmemiş parametreleri modele vermek,
Rails'teki gibi çalışma anında bir `ForbiddenAttributesError` değil, derleme
hatasıdır. Değerler alanın tipine çevrilir; çevrilemeyen bir değer ("abc"
bir sayı için) sessizce 0 olmaz, doğrulama hatası olur ve form 422 ile geri
gelir. `id` hiçbir zaman atanmaz.

`save` doğrulama geçmezse `false` döner ve nedenleri kaydın `errors`'ında
tutar; `!` yalnız veritabanı hatasını (DBError → 503) yukarı iletir. iyi'de
istisna yok: `raise` yakalanamayan bir paniktir, hatayı yukarı vermenin yolu
`!`.

`render "posts/show", layout: "admin"` başka bir layout, `layout: false`
layout'suz çizer; bir şablon parçayı `<%= render "_form.eiy" %>` ile çizer.

### View yardımcıları

Rails'teki isimleriyle; HTML basanlar kaçışı kendileri yapar, `raw` gerekmez:

```erb
<%= link_to "Edit", path_to(post) + "/edit", class: "btn" %>
<%= button_to "Delete", path_to(post), method: :delete, confirm: "Delete this post?" %>
<%= render "_form.eiy", post: @post %>             <%# partial'da `post` %>
<%= render "_post.eiy", collection: @posts %>      <%# her yazı için bir kez, `post` olarak %>
<%= truncate(post.body, length: 80) %>
<%= pluralize(comments.size, "comment") %>         <%# "1 comment", "3 comments" %>
<%= time_ago_in_words(post.created_at) %> ago      <%# "about 2 hours ago" %>
<%= number_with_delimiter(12345) %>                <%# "12,345" %>
<%= simple_format(post.body) %>                    <%# paragraflar ve satır sonları %>
<div id="<%= dom_id(post) %>">                     <%# "post_7" %>
<% if current_page?("/posts") %>...<% end %>
```

`button_to` kendi formunu CSRF alanıyla ve `PATCH`/`DELETE` için `_method` ile
basar; `confirm:` silmeden önce sorar. `link_to`'ya başka nitelikler de verilir
(`target: "_blank"`, `data_turbo: false`). Scaffold'lar bağlantılar için
`link_to`, silme için `button_to` kullanır; detay sayfasında da bir silme düğmesi
vardır.

Action'lar hatayı `!` ile yukarı verir; çevirme tek yerde,
`install_error_pages`'te yapılır:

| Hata | Yanıt |
|---|---|
| `NotFound` | 404 |
| `Invalid` | 422 ve hata listesi (`Post.create(...)!`'den; scaffold formu `if post.save!` ile kendisi çizer) |
| `Unauthorized` | `/login`'e yönlendirme, JSON'da 401 |
| `Forbidden` | 403 |
| `DBError` | 503; ayrıntı yalnız loga |

Bir uygulamanın kendi sayfası, `install_error_pages`'ten önce
`router.error NotFound do |env, err| ... end` ile kaydedilir.

Parametreler Rails'teki gibi `params`'tan okunur: `params[:id]` (yoksa
`""`), `params[:q]?` (yoksa `nil`), `params.require(:post).permit(...)`.
`Post.find(params[:id])` ve `paginate(params[:page]?)` metni olduğu gibi
alır: sayı olmayan bir id sorgu çalışmadan 404'tür, geçersiz sayfa 1. sayfa.

Diğer yardımcılar: `redirect_to path, notice: "..."` (ya da `alert:`), `status`, `flash`/`flash?`, `session`, `csrf_field`,
`path_to(record)`, `json(data)`, `wants_json?`. Bir filtre bir
`Unauthorized`/`Forbidden`/`NotFound`/`DBError` dönerse action durur, başka
bir şey dönerse çalışır: `Unauthorized.new unless session["user_id"]?`.

## Planla karşılaştırma

[Plan](plan.pdf) Faz 0 ile başlıyor; sonuçlar:

- **Kapı 1, derive ilişkileri kurabiliyor mu: hayır.** Bir derive'a tipin
  adı ve alanlarının ad/tip bilgisi verilir, annotation verilmez
  (`@[BelongsTo(User)]` görünmez). Plandaki geri dönüş yolu seçildi:
  ilişkiler, kendi argümanlarını okuyan sınıf gövdesi makrolarıyla
  yazılır (`belongs_to user : User`). `derive model`'i autoload sınıfın
  sonuna eklediği için sıra kuralı kullanıcıya görünmez.
- **Kapı 2, CRUD iki sürücüde: geçti.** `test/model_test.iyi` SQLite'ta
  ve PostgreSQL 16'da aynen geçiyor (`make test`, `make test-pg`).
- **Kapı 3, boş dizinden new ve migrate: geçti.**
- **Kapı 4, scaffold'la blog (kullanıcı, yazı, yorum): geçti.**
  [`examples/blog`](examples/blog) üç scaffold komutuyla üretildi; testleri
  geçiyor ve tarayıcıda oluştur, düzenle, sil, 422, 404 ve CSRF
  denendi.

Plandan farklar ve henüz yapılmayanlar:

- `with(:user)` yerine Rails'teki gibi `includes(:user)` var; `with_count` yok.
- `Wings.transaction` yerine `Post.transaction do |tx| ... end` var; transaction
  `on: tx` ile açıkça geçirilir.
- `handle_error` aşırı yüklemesi yerine iyi-web'in tipe göre hata sayfaları
  kullanılır (aynı iş, iyi-web zaten yapıyor).
- `respond_to` bloğu yok; `wants_json?` ve `json(data)` var.
- `Kurt::Test.app.login_as` yerine `sign_in_as(users(:ada))` var; testler
  iyi-web'in harness'ıyla route'lara istek gönderir (ara katmanlar, yani
  oturum ve CSRF, atlanır). Fixture'lar Rails'teki gibi YAML'dır; her test
  değil her test dosyası onlarla başlar.
- Faz 5'in Tailwind standalone kısmı yapıldı (daisyUI ile, varsayılan); `kurt ui add` ve `/styleguide` yapılmadı;
  `--css none` ile scaffold sade bir CSS dosyasıyla gelir. `llms.txt` yazılıyor.
- Paket yayını (Faz 4): Kurt `github.com/iyikurt/kurt` olarak bir iyi paketi;
  sürümler git etiketleri. CLI için ikili dağıtım yok, kaynaktan `make install`.

## Geliştirme

```sh
make            # bin/kurt
make test       # SQLite (9 test)
make test-pg PG_URL=postgres://user@127.0.0.1:5432/kurt_test
```

| Dosya | |
|---|---|
| `model.iyi` | `Query(T)`, `derive model`, ilişki makroları, `NotFound`/`Invalid`/`Errors` |
| `controllers.iyi` | `Controller`, `render`, route makroları, `before_action`, hata sayfaları |
| `strong_parameters.iyi` | `params.require(...).permit(...)` |
| `migrator.iyi` | zaman damgalı SQL migration'ları |
| `release.iyi` | release binary'nin `db:migrate` / `db:status` komutları |
| `fixtures.iyi` | `test/fixtures/*.yml`'yi okur ve test veritabanına yükler |
| `datasource.iyi` | bağlantı havuzu, placeholder lehçesi |
| `environment.iyi` | `KURT_ENV`, `DATABASE_URL` |
| `inflector.iyi` | çoğul/tekil, `underscore`, `camelize` |
| `generators.iyi` | `new` ve `generate`'in yazdığı dosyalar |
| `autoload.iyi` | başlıksız uygulama dosyalarından modül üretimi |
| `schema.iyi` | `db/schema.json`: tabloları okuma, SQL → iyi tip eşlemesi |
| `cmd/kurt.iyi` | CLI |

## Lisans

[MIT](LICENSE).
