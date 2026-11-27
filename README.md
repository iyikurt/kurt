<p align="center"><img src="kurt.svg" alt="Kurt" width="160"></p>

# Kurt

Kurt is an MVC web framework for [iyi](https://iyi.dev). It builds on two
libraries:
- [iyi-web](https://github.com/sdogruyol/iyi-web): HTTP, routing,
  templates, sessions and CSRF.
- [db](https://github.com/iyilang/db): SQL, connection pools and
  transactions.

Kurt adds the conventions on top: models, controllers, migrations,
generators and a CLI. An application compiles ahead of time to one native
binary.

```sh
kurt new blog
cd blog
kurt generate scaffold Post title:string body:text published:bool
kurt db:migrate
kurt dev            # http://localhost:3000/posts
```

Requirements:
- iyi 0.21.0 or later (tested with 0.22.0).
- A C compiler (`cc`); on Windows, the Visual C++ build tools iyi links with.
- SQLite (macOS ships it; on Windows `make install` fetches it).
- PostgreSQL is optional.

## Install

```sh
git clone https://github.com/iyikurt/kurt.git ~/src/kurt
cd ~/src/kurt
make install           # builds bin/kurt and links it to ~/.local/bin/kurt
export PATH="$HOME/.local/bin:$PATH"
kurt version
```

On Windows, `make install` (GNU make, from PowerShell, cmd or Git Bash) puts
`bin\` on your user `PATH` instead; open a new terminal for `kurt`. It also
downloads SQLite's x64 DLL from sqlite.org and makes its import library with
MSVC's `lib.exe`, and puts `sqlite3.dll` and `sqlite3.lib` in iyi's library
directory (the first entry of `iyi env IYI_LIBRARY_PATH`). Kurt and the
applications it creates both link against them.

Kurt is an iyi package, `github.com/iyikurt/kurt`, versioned by git tags
(`v0.1.0`):
- `kurt new` writes its own version into the application's `iyi.mod`.
- iyi downloads the package on the first build.
- The application's files import it as `kurt/...`:

```
require github.com/iyikurt/kurt v0.1.0 as kurt
```

When working on Kurt itself, `KURT_PATH=~/src/kurt kurt new app` adds a
`replace` line, so the application uses your checkout instead of the
published version.

## Commands

| Command | What it does |
|---|---|
| `kurt new NAME [--css none]` | A new application in `./NAME`, with Tailwind CSS and daisyUI; `--css none` leaves them out |
| `kurt generate scaffold NAME FIELD...` | Model, migration, controller, five views, routes and a test |
| `kurt generate model NAME FIELD...` | Model and migration |
| `kurt generate controller NAME ACTION...` | Controller, views and routes |
| `kurt generate migration NAME` | An empty migration |
| `kurt generate attachments` | The migration of `kurt_attachments`, the table `has_one_attached` keeps files in |
| `kurt generate job NAME` | A background job, its test, and the queue's migration (`kurt_jobs`) when there is none |
| `kurt generate mailer NAME METHOD...` | A mailer, a text and an HTML view per method, the mail layouts and a test |
| `kurt generate authentication [MODULE...]` | users: sign-in, sign-up, password reset, remember me; `confirmation`, `lock`, `tracking`, `timeout` on request |
| `kurt generate authentication:views` / `authentication:controllers` | Copies Kurt's authentication pages, mails and controllers into the application, to change them |
| `kurt db:migrate` / `db:rollback [N]` / `db:status` / `db:reset` | Manage the schema (`db:reset` also runs the seeds) |
| `kurt db:seed` | Runs `db/seeds.iyi` |
| `kurt routes` | Lists every route with its path and `Controller#action` |
| `kurt jobs` | Runs the background jobs worker on its own |
| `kurt dev [-p PORT]` | Runs the server; on a change it rebuilds, restarts and reloads the page |
| `kurt test` | Migrates a fresh test database and runs each `test/*_test.iyi` with fixtures |
| `kurt build` | A release binary in `bin/NAME`, with minified CSS and the migrations inside |
| `kurt export [-o DIR] [PATH...]` | The application as static files in `dist/` (or `DIR`), for hosting with no server |
| `kurt css:build [--minify]` | Compiles `app/assets/tailwind/app.css` to `public/assets/app.css` |
| `kurt css:install` | Downloads the Tailwind CLI and daisyUI, for an application created offline |

Field types:
- `string`, `text`, `int`, `float`, `bool`, `time`;
- `references`: `user:references` gives a `user_id` column and `belongs_to user`;
- `attachment`: `avatar:attachment` gives no column but `has_one_attached :avatar`
  and a file field (see File uploads).

The database is `DATABASE_URL`, or `sqlite3:./db/<env>.sqlite3` when that
is not set. The environment is `KURT_ENV` (default `development`). The same
application runs on PostgreSQL with a `postgres://` URL, and the generators
then write migrations in PostgreSQL's dialect.

## Application layout

An application's `.iyi` files have no module header and no imports:

```
config/application.iyi     runs at start: middleware, settings
config/routes.iyi          the routes
app/models/post.iyi        class Post < ApplicationRecord
app/controllers/posts_controller.iyi
app/views/posts/index.eiy
app/mailers/user_mailer.iyi        class UserMailer < ApplicationMailer
app/jobs/welcome_job.iyi           class WelcomeJob < ApplicationJob
db/migrations/20261123153000_create_posts.sql
db/seeds.iyi               the first records of a new database
test/posts_test.iyi
test/fixtures/users.yml    the records each test file starts with
AGENTS.md                  the conventions, for coding agents
CLAUDE.md                  points Claude Code at AGENTS.md
```

`AGENTS.md` describes the layout, the commands and the conventions. Coding
agents (Codex, Cursor, Copilot, Gemini CLI and others) read it from the
project root on their own. Claude Code reads `CLAUDE.md`, which imports it.

`kurt dev`, `kurt test` and `kurt build` turn these files into real iyi
modules under `.kurt/build/` ([autoload.iyi](autoload.iyi)). That
directory is generated; never edit it.

- **Models:** all of them go into one `app/models` module. Each gets
  `pub`, a `property` for every column of its table (from
  `db/schema.json`) and `derive model`. iyi forbids import cycles, so this
  is how `User` and `Post` can refer to each other: within one module there
  is no cycle.
- **Controllers:** all of them go into one `app/controllers` module,
  `ApplicationController` first. Model variables (`@post`, `@posts`) are
  declared by convention.
- **Routes:** `config/routes.iyi` becomes the body of `def routes : Router`.
- **Imports:** each kind of file gets the imports it needs. A file that
  needs another module writes its own `import` line at the top, and that
  line moves to the module header.

Every piece carries a location pragma. A compile error points at the line
in the file you wrote (`In app/models/post.iyi:13:25`), not at the
generated one, and `render` finds views relative to that file. The cost:
iyi's language server in your editor cannot check a headerless file on its
own.

## Models

A model's fields come from its table; the model file writes only behavior:

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

### Querying and saving

```iyi
Post.all!                                      # Array(Post) | DBError
Post.find(id)!                                 # Post | NotFound | DBError; id is a number or params[:id]
Post.find?(id)!                                # Post? | DBError
Post.feed.paginate(page, per: 20).all!
Post.title("Hello").first?!                    # a typed finder per field; a wrong field is a compile error
Post.where(user_id: 5).count!
post.save!                                     # Bool | DBError; when false, the reasons are in post.errors
post.update(title: "New")!                     # sets the fields and saves; Bool like save
post.update(post_params)!                      # from a form: permitted fields, converted to their types
post = Post.create(title: "Hello", body: "...", user_id: 1)!   # hands Invalid up when invalid (422)
post.user!.name                                # belongs_to: one query
post.comments.order(:id).limit(5).all!         # has_many: a lazy query
post.increment(:comments_count)!
post.destroy!
```

Every call answers either a value or an error, and `!` hands the error up.
iyi has no exceptions: `raise` is a panic that cannot be caught.

An `Int64` field also takes an `Int32` (`Post.create(user_id: 1)`).
`created_at` and `updated_at`, when present, are filled by `save`.

The autoloader appends `derive model` to the end of the class. It generates:
- the table name (change it with `@[Table("people")]`);
- the row mapping;
- a `new(**)` where every field is optional;
- the class and instance methods;
- one finder per field.

### The schema

`kurt db:migrate` (and `db:rollback`) reads the tables from the database and
writes them to `db/schema.json`. It also refreshes the column comment at
the top of each model; the compiler does not read that comment. The build
reads this file, not the database, and adds a `property` for each column.
Commit `db/schema.json` to git.

| SQL | iyi |
|---|---|
| `TEXT`, `VARCHAR` | `String` |
| `INTEGER`, `BIGINT` | `Int64` (PostgreSQL's 4-byte `integer` is `Int32`) |
| `REAL`, `DOUBLE PRECISION` | `Float64` |
| `BOOLEAN` | `Bool` |
| `DATETIME`, `TIMESTAMPTZ` | `Time` |
| a column that allows `NULL` | nilable (`String?`) |

SQLite has no real boolean or date type, but it keeps the declared type
name. That is why the generators write `BOOLEAN` and `DATETIME` in SQLite
migrations too.

A `property` the model writes itself, with another type or a default
value, wins over the schema's:

```iyi
class Post < ApplicationRecord
  property published : Bool = true
end
```

For a new column, write a migration and run `kurt db:migrate`; the model
does not change. The build warns about a model whose table has not been
migrated yet.

### Validations and callbacks

They go in the class body, and each line adds to the ones before it:

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

  # Your own rules: runs after the validates lines.
  def validate(errors : Errors) : Nil
    errors.add("name", "can't be root") if name == "root"
  end
end
```

| Rule | Message |
|---|---|
| `presence: true` | `can't be blank` (empty text, nil, or an `*_id` still 0) |
| `length: {minimum: 2}` / `{maximum: 60}` / `{is: 5}` / `{in: 2..60}` | `is too short (minimum is 2 characters)` and so on |
| `format: /regex/` | `is invalid` |
| `inclusion: {in: [...]}` | `is not included in the list` |
| `uniqueness: true` | `has already been taken` (asks the database; the record itself does not count) |

- `message:` replaces every message on its line.
- `uniqueness` is a query. To be safe against race conditions, the
  database also needs a `UNIQUE` index.
- A `NULL` field passes `length` and `format`.
- Scaffolded models come with `validates ..., presence: true` for their
  text fields and references.

Callbacks run in this order:
1. `before_validation`
2. validation
3. `before_save`
4. `before_create` or `before_update`
5. the write
6. `after_create` or `after_update`
7. `after_save`

Destroying runs `before_destroy` and `after_destroy`.

A callback that answers a `DBError` stops the save, and the error is handed
up (with `!`: `Profile.create(user_id: id)!`). Any other return value is
ignored.

### Destroying associated records

```iyi
class User < ApplicationRecord
  has_many posts : Post, dependent: :destroy        # each post is destroyed with its own
end                                                 # callbacks and its own dependents

class Post < ApplicationRecord
  has_many comments : Comment, dependent: :delete_all   # one DELETE, nothing loaded
end
```

`has_one` takes `dependent:` too. A model with dependents is destroyed in
its own transaction: either everything goes or nothing does.

### Transactions

```iyi
Order.transaction do |tx|
  order.save(on: tx)!
  item.update(on: tx, quantity: 2)!
  Stock.where(product_id: item.product_id).on(tx).delete_all!
end
```

An error the block answers (`Invalid`, `NotFound`, `DBError`, ...) rolls
everything back and is returned. Leaving the block early with `!` also
rolls back. Otherwise the transaction commits and the block's value is
returned.

`Order.transaction(on: tx) do |inner| ... end` opens a nested transaction
(a savepoint); its error rolls back only itself.

The transaction is passed explicitly: `on: tx`, `Post.on(tx).find(id)`,
`query.on(tx)`. A server runs many requests at once, and a query that found
"the current transaction" by itself could land in another request's.

A callback gets the transaction of the save it runs in from
`current_transaction`:

```iyi
after_create :open_profile

def open_profile
  Profile.create(user_id: id, on: current_transaction)!
end
```

`save` does not open a transaction by itself. If a record and its
callbacks must be written together, save it in a `transaction` block.

### Joins, calculations and other queries

```iyi
Post.joins(:user).where("users.name", "Ada").all!        # INNER JOIN users ON users.id = posts.user_id
Post.joins(:comments).distinct.count!                    # posts with a comment, each once
User.left_joins(:posts).where_sql("posts.id IS NULL").all!   # users without posts
Post.joins("INNER JOIN tags ON tags.id = posts.tag_id")  # a join written out

Post.pluck(:title, String)!                   # Array(String)
Post.pluck(:id, :title)!                      # Array(Array(DBValue))
Post.where(published: true).ids!              # Array(Int64)
Post.select(:user_id).distinct.count!
Post.select("posts.*, users.name AS author").joins(:user).all!

Order.sum(:total)!                            # Float64; 0.0 when no row matches
Order.sum(:quantity, Int64)!
Order.average(:total)!                        # Float64?, nil when no row matches
Order.minimum(:created_at, Time)!             # Time?
Order.maximum(:total)!                        # DBValue

Post.group_by(:user_id).counts!               # {1 => 3, 2 => 1}: Hash(DBValue, Int64)
Post.group_by(:user_id).having("COUNT(*) > ?", [1]).counts!
Order.group_by(:status).sums(:total)!         # also averages, minimums, maximums

Post.where(published: true).or_where(Post.where(user_id: 5)).all!
```

- `joins(:name)` and `left_joins(:name)` follow the model's `belongs_to`,
  `has_many` and `has_one` lines. An unknown name answers a `DBError` when
  the query runs.
- Once a query joins, a column of the model's own (`where(id: 5)`,
  `order(:title)`) is written with its table's name, so it is not
  ambiguous. Columns of other tables are written with theirs:
  `where("users.name", "Ada")`.
- A `has_many` join returns a row once per associated row; `distinct`
  returns each once.
- `select` changes the columns read. `all` still makes models, so a
  selection has to give every field the model has (`posts.*, ...`). For
  other values use `pluck`.
- Two Rails names are reserved words in iyi: `group` (the task group) is
  `group_by`, and `.or` (error recovery) is `or_where`.
- Grouped `counts`, `sums`, `averages`, `minimums` and `maximums` answer a
  hash keyed by the group's value. `group_by(:user_id).count` counts the
  groups.

### Bulk writes

```iyi
Post.insert_all([{title: "A", user_id: 1}, {title: "B", user_id: 1}])!     # Array(Int64): the new ids
User.upsert_all([{email: "ada@example.com", name: "Ada"},
                 {email: "bob@example.com", name: "Bob"}], unique_by: :email)!
```

- Each is one `INSERT ... VALUES (...), (...) RETURNING id`, on SQLite
  and PostgreSQL alike. No model is made, and no validation or callback
  runs.
- `insert_all` skips a row that would break a unique index
  (`ON CONFLICT DO NOTHING`). With `skip_duplicates: false`, such a row
  makes the statement fail.
- `upsert_all` inserts the rows, and updates every other column of a row
  whose `unique_by` columns (`:email`, or `[:account_id, :email]`) match
  one there already (`ON CONFLICT (...) DO UPDATE`). The row keeps its id
  and `created_at`. `unique_by` needs a unique index on those columns.
- The rows are named tuples of one shape, or hashes with the same keys
  (`Hash(String, DBValue)`). `created_at` and `updated_at` are filled when
  the table has them and the rows do not.
- Both take `on: tx`.
- The answer has the ids of the rows written. A row skipped, or left alone
  because only its key was given, is not among them.
- The databases limit how many values one statement binds (SQLite 32,766;
  PostgreSQL 65,535). Split a larger batch.

### has_many :through

```iyi
class Post < ApplicationRecord
  has_many taggings : Tagging
  has_many tags : Tag, through: :taggings          # taggings.post_id and taggings.tag_id
end

class User < ApplicationRecord
  has_many posts : Post
  has_many comments : Comment, through: :posts     # posts.user_id and comments.post_id
end

post.tags.order(:name).all!
user.comments.count!
Post.joins(:tags).where("tags.name", "iyi").distinct.all!
```

The through table is the one its name says. Kurt reads from the target's
columns which side holds the key: a `Comment` with `post_id` belongs to the
through table, and a `Tag` without `tagging_id` is pointed at by
`taggings.tag_id`. `source_key: :label_id` names that key when it is not
`<target>_id`. `includes` does not preload a through association.

### Preloading (`includes`)

A list that asks for each row's association separately makes 26 queries
for 25 posts (N+1). `includes` loads the associations with the rows, one
query per association (`WHERE user_id IN (...)`). After that, `post.user!`
and `post.comments` do not go back to the database:

```iyi
posts = Post.includes(:user, :comments).order_desc(:id).paginate(page).all!
posts.each do |post|
  post.user!.name                    # loaded, no query
  post.comments.count!               # loaded, no query
  post.comments.where(approved: true).all!   # narrowing asks again
end
```

- It works for `belongs_to`, `has_many` and `has_one`.
- Inside a transaction (`Post.on(tx).includes(:user)`), the preload queries
  run in that transaction too.
- An unknown association name answers a `DBError`.
- A scaffold's index page preloads, on its own, the references it shows by
  name.

## Controllers and routes

```iyi
# app/controllers/posts_controller.iyi
class PostsController < ApplicationController
  before_action :require_login, except: [:index, :show]

  def index
    posts = Post.feed.all!
    render "posts/index"                   # app/views/posts/index.eiy, inside layouts/application.eiy
  end

  def show
    post = Post.find(params[:id])!         # 404 when there is no such record, with no code
    render "posts/show"
  end
end
```

```iyi
# config/routes.iyi
root HomeController, :index
resources "posts", PostsController       # REST routes for the actions the controller defines
get "/about", PagesController, :about    # post, put, patch and delete too

resources "posts", PostsController do    # nested: /posts/:post_id/comments
  resources "comments", CommentsController
end

namespace "admin" do                     # /admin/users, /admin/users/:id, ...
  resources "users", AdminUsersController
end
```

A nested resource's controller finds the parent record with
`params[:post_id]`; `param: "article_id"` changes the name. `kurt routes`
prints every route of the application:

```
$ kurt routes
  Verb    Path                       Controller#Action
  GET     /posts                     PostsController#index
  GET     /posts/:post_id/comments   CommentsController#index
  ...
```

The controller a scaffold writes:

```iyi
class PostsController < ApplicationController
  before_action :set_post, only: [:show, :edit, :update, :destroy]

  def index
    @posts = Post.order_desc(:id).all!
    render "posts/index"
  end

  def show
    render "posts/show"                    # the view sees @post
  end

  def create
    @post = Post.new(post_params)
    if @post.save!
      redirect_to path_to(@post), notice: "Post was created."
    else
      render "posts/new", status: 422      # the form is drawn again with the reasons in @post.errors
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
    @post = Post.find(params[:id])!        # 404 when missing; the action never runs
  end

  private def post_params : Hash(String, String)
    params.require(:post).permit(:title, :body, :published)
  end
end
```

### Instance variables

`@post` and `@posts` need no declaration. iyi cannot infer an instance
variable's type, so the autoloader declares them by convention:
- A variable named after a model (`@post`) holds that model and starts as
  a blank record.
- Its plural (`@posts`) holds an array of that model and starts empty.

Neither is ever `nil`, so actions and views use them without checking.
Any other variable is declared with its type
(`@featured : Array(Post) = [] of Post`). An explicit declaration always
wins.

### Filters

A filter needs no return type and no `nil` at the end. If it answers
`Unauthorized`, `Forbidden`, `NotFound`, `TooManyRequests` or `DBError` (directly, or handed
up with `!`), the action stops. Any other value (an assigned record, a
list, `nil`) lets the action run:

```iyi
Unauthorized.new unless session["user_id"]?
```

### Parameters

- `params[:id]` is `""` when missing.
- `params[:q]?` is `nil` when missing.
- `Post.find(params[:id])` and `paginate(params[:page]?)` take the text as
  it is. An id that is not a number is a 404 before any query runs, and an
  invalid page is page 1.

### Strong parameters

Forms send fields as `post[title]`. `params.require(:post)` collects them,
and `permit` keeps only the ones named.

A model accepts only the `Hash(String, String)` that `permit` answers
(`Post.new(h)`, `post.update(h)`, `Post.create(h)`). Passing unfiltered
parameters to a model is a compile error, not a runtime error.

Values are converted to the field's type. A value that does not convert
("abc" for a number) does not silently become 0: it is a validation error,
and the form comes back with 422. `id` is never assigned.

`save` answers `false` when validation fails and keeps the reasons in the
record's `errors`; its `!` hands only a database error (DBError → 503) up.

### Rendering

- `render "posts/show", layout: "admin"` uses another layout.
- `layout: false` renders without one.
- A template renders a partial with `<%= render "_form.eiy" %>`.

### Errors

Actions hand errors up with `!`. They are turned into responses in one
place, `install_error_pages`:

| Error | Response |
|---|---|
| `NotFound` | 404 |
| `Invalid` | 422 with the list of errors (from `Post.create(...)!`; a scaffold form draws its own with `if post.save!`) |
| `Unauthorized` | A redirect to the sign-in page (`/users/sign_in` from `authenticate_user!`, else `/login`); 401 for JSON |
| `TooManyRequests` | 429, with `Retry-After` |
| `Forbidden` | 403 |
| `DBError` | 503; the details go only to the log |
| `DeliveryError` | 503; mail could not be sent (the reason goes to the log) |

An application registers its own page with
`router.error NotFound do |env, err| ... end`, before `install_error_pages`.

### Other helpers

- `redirect_to path, notice: "..."` (or `alert:`)
- `status`, `flash` / `flash?`, `session`, `csrf_field`
- `path_to(record)`
- `json(data)`, `wants_json?`

## Views

Templates are `.eiy` files: `<%= expr %>` escapes its output, and `raw(x)`
does not. The helpers that write HTML escape it themselves, so they need no
`raw`:

```erb
<%= link_to "Edit", path_to(post) + "/edit", class: "btn" %>
<%= button_to "Delete", path_to(post), method: :delete, confirm: "Delete this post?" %>
<%= render "_form.eiy", post: @post %>             <%# `post` in the partial %>
<%= render "_post.eiy", collection: @posts %>      <%# once per post, as `post` %>
<%= truncate(post.body, length: 80) %>
<%= pluralize(comments.size, "comment") %>         <%# "1 comment", "3 comments" %>
<%= time_ago_in_words(post.created_at) %> ago      <%# "about 2 hours ago" %>
<%= number_with_delimiter(12345) %>                <%# "12,345" %>
<%= simple_format(post.body) %>                    <%# paragraphs and line breaks %>
<div id="<%= dom_id(post) %>">                     <%# "post_7" %>
<% if current_page?("/posts") %>...<% end %>
```

- `button_to` writes its own form, with the CSRF field and, for
  `PATCH`/`DELETE`, a `_method` field.
- `confirm:` asks before submitting.
- `link_to` takes other attributes too (`target: "_blank"`,
  `data_turbo: false`).
- Scaffolds use `link_to` for links and `button_to` for deleting. The
  detail page has a delete button too.

Templates have no `!` and no `.or`. An association is narrowed with
`is_a?` instead:

```erb
<% if (user = @post.user?).is_a?(User) %><%= user.name %><% end %>
```

### Forms

`form_with` builds a form from a record, as in Rails. It is a `<% %>` tag,
not `<%= %>`: the form is written as the template runs.

```erb
<% form_with model: @post, class: "card" do |f| %>
  <%= f.label :title %>
  <%= f.text_field :title, placeholder: "A title" %>
  <%= f.text_area :body, rows: 8 %>
  <label><%= f.check_box :published %> Published</label>
  <%= f.select :user_id, @users.map { |u| {u.name, u.id} }, prompt: "Select a user" %>
  <%= f.submit %>                                  <%# "Create Post", or "Update Post" %>
<% end %>
```

- The fields are named in the model's scope (`post[title]`, id
  `post_title`), which is what `params.require(:post)` reads. Each shows
  the record's value.
- A new record posts to `/posts`. A saved one posts to `/posts/7` with
  `_method=patch`. `url:` and `method:` say otherwise.
- The CSRF field is always in the form.
- A field that did not validate (`@post.errors.on("title")`) gets
  `aria-invalid="true"`. With `form_style :daisyui` it also gets daisyUI's
  `input-error` (`select-error`, `textarea-error`...).
- Without a model, `url:` is the path and the fields are bare, or in
  `scope:`: `form_with url: "/search", method: :get do |f|`.
- `multipart: true` lets a form send files. Other attributes go on the
  `<form>` tag (`data_turbo: false`).

| Builder method | Writes |
|---|---|
| `label :title, "Text"` | `<label for="post_title">`; the text defaults to the humanized field (`user_id` is "User") |
| `text_field`, `email_field`, `password_field`, `number_field`, `url_field`, `search_field`, `telephone_field`, `date_field`, `datetime_field`, `hidden_field` | an `<input>` of that type; `password_field` never shows the value |
| `text_area :body, rows: 8` | a `<textarea>` |
| `check_box :published` | a hidden `0` and a checkbox `1`, as Rails does |
| `select :role, ["admin", "member"]` or `select :user_id, [{"Ada", 1}]` | a `<select>`; `prompt:` or `include_blank: true` adds an empty first option |
| `file_field :avatar` | a file input |
| `submit "Save"` | a submit button |

Every method takes other attributes too (`required: true`,
`autocomplete: "email"`). `class:` replaces the style's class.

`form_style :daisyui` in `ApplicationController` gives the fields daisyUI's
classes (`input`, `select`, `textarea`, `checkbox`, `btn btn-primary`,
labels `fieldset-legend`). `kurt new` writes it into Tailwind applications,
and `app/assets/tailwind/app.css` names these classes with
`@source inline(...)`, since no view contains them. Without `form_style`,
the builder adds no classes.

Scaffolds and `kurt generate authentication` write their forms with
`form_with`.

### Associated records in forms

In a scaffold, a field like `user:references` becomes a select box
(`f.select :user_id, @users.map { |option| {option.name, option.id} }`) when
a `User` model exists. The options show that table's first text column:
`name`, or `title` for posts. If the schema does not have the table yet,
the column is read from its `create_` migration. The controller loads the
list in a filter:

```iyi
before_action :set_users, only: [:new, :create, :edit, :update]

private def set_users
  @users = User.order(:name).all!
end
```

The show and index pages print the name instead of the number. A form
submitted without a choice comes back with 422 and
`user_id can't be blank`.

## File uploads

```iyi
class User < ApplicationRecord
  has_one_attached :avatar, content_types: ["image/png", "image/jpeg"], max_size: 5_000_000
  has_many_attached :documents
end
```

```erb
<% form_with model: @user, multipart: true do |f| %>
  <%= f.file_field :avatar %>
  <%= f.file_field :documents, multiple: true %>
  <%= f.submit %>
<% end %>

<% if (file = @user.avatar.attachment).is_a?(Attachment) %>
  <img src="<%= file.url %>" alt="<%= file.filename %>">
<% end %>
<% @user.documents.all?.each do |doc| %><a href="<%= doc.url %>"><%= doc.filename %></a><% end %>
```

```iyi
def update
  @user.avatar = uploaded_file(:user, :avatar)          # nil when no file was chosen: the old one stays
  @user.documents = uploaded_files(:user, :documents)   # added to the ones there
  if @user.update(user_params)!
    ...
```

- iyi-web reads `multipart/form-data` bodies. It streams each file to a
  temporary file, which it deletes once the response is written.
  `uploaded_file(:user, :avatar)` is the `user[avatar]` field's file.
- `user.avatar = upload` keeps the file until the record saves. It is
  checked with the record's validations (`content_types:`, `max_size:` in
  bytes), and attached once the record has saved. A record that does not
  validate keeps nothing.
- `user.avatar` answers what is attached: `attachment` (an `Attachment` or
  nil), `attached?`, `url?` (for a view), `attach(upload)` or
  `attach(data, "name.pdf")` at once, and `purge`. A new one replaces the
  old one, and its file is deleted. `user.documents` has `all`, `all?`,
  `count`, `attach` and `purge`.
- An `Attachment` has `url`, `filename`, `content_type`, `byte_size`,
  `image?`, `path` (on disk) and `read`.
- Destroying the record deletes its attachments and their files.

Storage:
- Each attachment is a row of `kurt_attachments` and a file under
  `storage/` (or `KURT_STORAGE`), named by a random key: 24 bytes in hex.
  `kurt generate attachments` writes the table's migration and keeps
  `storage/` out of git; a scaffold with an `attachment` field does it on
  its own.
- The browser's file name is kept without its path or control
  characters. The type is the browser's, or the extension's when it sent
  none.
- `GET /files/<key>/<filename>` serves the files once a migration makes
  the table.
  - Images, PDF, audio, video and plain text are shown in the browser.
  - Anything else, HTML and SVG included, is sent as a download, so an
    upload cannot run script on the application's origin.
  - The key cannot be guessed, but anyone with the URL can fetch the file.
    Serve a private file from an action of your own (`env.send_file(attachment.path)`).
- On a server, keep `storage/` on a disk that outlives deploys.

Not yet: storage in S3 or another service, image variants (thumbnails),
direct uploads from the browser, and signed or expiring URLs.

## Mailers

```sh
kurt generate mailer User welcome
```

```iyi
# app/mailers/user_mailer.iyi
class UserMailer < ApplicationMailer
  def welcome(user : User)
    @user = user
    mail to: user.email, subject: "Welcome to the blog"
  end
end
```

```erb
<%# app/views/user_mailer/welcome.text.eiy %>
Hello <%= @user.name %>, welcome!

<%# app/views/user_mailer/welcome.html.eiy %>
<p>Hello <%= @user.name %>, <a href="https://blog.example/posts">welcome</a>!</p>
```

```iyi
UserMailer.welcome(user).deliver_now!      # in an action: Message | DeliveryError
```

- `mail` renders `app/views/<mailer>/<method>.text.eiy` and `.html.eiy`.
  Both are optional, but one must exist; with both, the mail is
  `multipart/alternative`.
- When `app/views/layouts/mailer.text.eiy` or `mailer.html.eiy` exists,
  each part is rendered inside it (`<%= content %>`). `layout: false`
  leaves them out, and `template: "other"` renders another view.
- The HTML part is escaped as a page is. The text part is not escaped,
  since it is not HTML.
- `mail` also takes `cc:`, `bcc:`, `reply_to:` and `from:`. An address is
  `"ada@example.com"` or `"Ada <ada@example.com>"`, and `to:` takes one or
  an array.
- `default from: "Blog <noreply@blog.example>"` in a mailer sets its
  sender. Without one, it is `MAIL_FROM`.
- Each public method of a mailer is also a class method:
  `UserMailer.welcome(user)` is `UserMailer.new.welcome(user)`.
- Model variables (`@user`) need no declaration, as in controllers. Any
  other is declared: `@greeting : String = ""`.
- `message.attach("report.pdf", data)` answers the mail with a file
  attached.

Where `deliver_now` sends mail:

| Setting | Where mail goes |
|---|---|
| `SMTP_URL` set | To that server: `smtp://user:password@host:587` (STARTTLS), `smtps://user:password@host:465` (TLS), or `smtp://localhost:1025?security=none` (a local catcher) |
| `KURT_ENV=test` | Into `deliveries`, for tests to read |
| `KURT_ENV=development` | Into the log, and into `deliveries` |
| `KURT_ENV=production` | Nowhere: `deliver_now` answers a `DeliveryError`, which an action's `!` turns into a 503 |

A test reads what was sent:

```iyi
clear_deliveries
res = dispatch(app, form_request("POST", "/posts", "post%5Btitle%5D=Hi"))
assert deliveries.last.subject == "Welcome to the blog"
assert deliveries.last.body.includes?("Hello")
```

`message.deliver_later` sends it from a background job instead (see
Background jobs): the mail is rendered at once and waits in the queue. It
answers the job's id, or a `DBError`; `deliver_later(wait: 600)` sends it
in ten minutes. In a test, `perform_enqueued_jobs` sends what is waiting.

Sending uses iyi's `std/smtp` and `std/mail`.

## Background jobs

```sh
kurt generate job Notify     # app/jobs/notify_job.iyi, test/notify_job_test.iyi, and the queue's table
kurt db:migrate
```

```iyi
# app/jobs/notify_job.iyi
class NotifyJob < ApplicationJob
  queue_as :default
  retry_attempts 5

  def perform(post : Post, user : User)
    PostMailer.created(post, user).deliver_now!
  end
end
```

```iyi
NotifyJob.perform_later(@post, current_user.as(User))!   # the job's id | DBError
NotifyJob.perform_later(@post, user, wait: 300)!         # in five minutes
NotifyJob.perform_later(@post, user, on: tx)!            # only if the transaction commits
NotifyJob.perform_now(@post, user)                       # here, without the queue
```

- Jobs wait in the `kurt_jobs` table, on SQLite and PostgreSQL alike.
  `kurt generate job` writes its migration once.
- `perform`'s arguments are kept as JSON: `String`, `Int32`, `Int64`,
  `Float64`, `Bool`, `Time`, nil (for a `String?` argument), arrays of
  these, and models. A model is kept as its id and found again when the
  job runs, as Rails' GlobalID does. A record deleted in between fails the
  job.
- Each public `perform` gets `perform_later` and `perform_now` as class
  methods.

The worker runs inside the server, on a thread of its own, when the
application has a queue. `KURT_JOBS_IN_SERVER=0` turns that off; then
`kurt jobs` (or `./bin/blog jobs` on a server) runs it alone. Any number of
workers can share the queue: on PostgreSQL a worker takes a job with
`FOR UPDATE SKIP LOCKED`, and on SQLite the database takes one writer at a
time.

- A job fails when `perform` answers an error (hand it up with `!`). It
  runs again after attempts⁴ + 2 seconds (3, 18, 83, 258...), until its
  attempts are spent (5, or `retry_attempts 3`). Then it stays in the table
  with `failed_at` and `last_error`.
- A job that panics (`raise`) is caught in its own task. The panic is its
  error, and the worker goes on.
- A job a worker took and never finished (the process was killed) is taken
  again after 15 minutes.
- A finished job is deleted.
- Workers poll the table every second when it is empty.

Tests (`kurt test`) do not run a worker:

```iyi
clear_jobs.as(Nil)
res = dispatch(app, form_request("POST", "/posts", "post%5Btitle%5D=Hi")).response
assert enqueued_jobs.as(Array).size == 1      # the jobs waiting: job_class, arguments, attempts...
assert perform_enqueued_jobs == 1             # runs the jobs that are due, and those they enqueue
assert deliveries.last.subject == "Your post is up: Hi"
```

`failed_jobs` lists the ones whose attempts are spent, and `make_jobs_due`
makes waiting jobs due now.

## Authentication

The model names the modules it uses, one routes line draws their pages,
and Kurt ships the controllers, views and mails.

```sh
kurt generate authentication                       # the default modules
kurt generate authentication confirmation lock    # and others
kurt db:migrate
```

```iyi
# app/models/user.iyi
class User < ApplicationRecord
  authentication :password, :registration, :recovery, :remember_me, :validation
end

# config/routes.iyi
authentication_for "users"

# app/controllers/application_controller.iyi
class ApplicationController < Controller
  authentication_helpers User
end

# a controller whose pages need a signed-in user
class PostsController < ApplicationController
  before_action :authenticate_user!, except: [:index, :show]
end
```

| Module | What it does | Columns |
|---|---|---|
| `password` | Signs in with an address and a bcrypt password; `password=`, `valid_password?`, `User.authenticate(email, password)` | `email`, `encrypted_password` |
| `registration` | Sign-up, the account page (changes need the current password), deleting the account | |
| `recovery` | "Forgot your password?": a mail with a link good for 6 hours and until the password changes | |
| `remember_me` | "Remember me": a cookie that signs the user in again for two weeks, void after signing out | `remember_created_at` |
| `validation` | Address present, well formed and unique; password 8 to 72 bytes and confirmed | |
| `confirmation` | No sign-in until the link in the confirmation mail is followed (3 days) | `confirmed_at`, `confirmation_sent_at` |
| `lock` | 5 wrong passwords lock the account for an hour, or until the unlock mail's link | `failed_attempts`, `locked_at` |
| `tracking` | Counts sign-ins, with their times and addresses | `sign_in_count`, `current_sign_in_at`, `last_sign_in_at`, `current_sign_in_ip`, `last_sign_in_ip` |
| `timeout` | A session idle for 30 minutes ends (not one remembered by the cookie) | |

`kurt generate authentication` writes the model (or adds `authentication` to a
`User` that exists), a migration with every module's columns (turning a
module on later needs no migration), `authentication_for "users"`,
`authentication_helpers User`, the layout's links, `ApplicationMailer` and the mail
layouts, and `test/authentication_test.iyi`. A `User` scaffold already has
`POST /users`, so then the scope's pages go under `/auth`
(`authentication_for "users", path: "auth"`).

The pages:

| Path | |
|---|---|
| `GET/POST /users/sign_in`, `DELETE /users/sign_out` | signing in and out |
| `GET /users/sign_up`, `POST /users` | signing up |
| `GET /users/edit`, `PATCH /users`, `DELETE /users` | the account |
| `/users/password/new`, `/users/password/edit` | a forgotten password |
| `/users/confirmation/new`, `/users/confirmation?confirmation_token=` | confirming the address |
| `/users/unlock/new`, `/users/unlock?unlock_token=` | unlocking |

Options go on the `authentication` line: `authentication_key: :username`,
`password_length: 12`, `maximum_attempts: 3`, `unlock_in: 7200`,
`remember_for: 2592000`, `timeout_in: 900`, `reset_password_within:`,
`confirm_within:` (times in seconds).

In controllers and views (from `authentication_helpers User`):

- `current_user` (a `User?`) and `user_signed_in?`.
- `before_action :authenticate_user!`: a visitor who is not signed in goes
  to `/users/sign_in` and, after signing in, back to the page they asked
  for. JSON gets 401. iyi has no `!` in names: `authenticate_user` answers
  `Unauthorized` or nil, and iyi's `!` hands it up, which stops the action.
- `sign_in(user, remember: true)` and `sign_out(user)`.
- `after_sign_in_path_for(user)` and `after_sign_out_path_for(user)`,
  which a controller may override.

Security:
- Passwords are stored with bcrypt (`std/password`; tests use the lowest
  cost).
- `User.authenticate` checks a password even when no user has the
  address, so the response time does not tell which addresses are
  registered. A wrong password and an unknown address get the same message.
- Signing in renews the session id.
- Reset, confirmation, unlock and remember tokens are not stored. Each is
  HMAC-SHA256-signed with `SESSION_SECRET` and carries the record's id and
  an expiry. What it depends on is signed, not sent: a reset token stops
  working once the password changes, a remember token once the user signs
  out.
- The forms for signing in, resetting a password and resending
  instructions are rate limited: ten requests a minute from one address,
  then 429. `lock` limits one account; this limits one client across
  accounts. The limit is off under `KURT_ENV=test`.
- "Forgot your password?" answers the same whether or not the address has
  an account.

Mail goes through the mailer (see Mailers): `UserAuthenticationMailer` sends the
reset, confirmation and unlock instructions. Links start with `APP_URL`
(`kurt dev` sets it to its own address; production sets it).

To change the pages, copy them into the application:

```sh
kurt generate authentication:views        # app/views/authentication/: the pages and the mails
kurt generate authentication:controllers  # app/controllers/user_sessions_controller.iyi and the rest,
                                          # app/mailers/user_authentication_mailer.iyi, and the views
```

A copy in the application is used instead of Kurt's; delete it to go back.
Kurt's own are written into `.kurt/build/authentication/` at every build.

In tests, `sign_in(users(:ada))` (or `sign_in_as`) makes the following
requests as that user, and `sign_out` undoes it. It works only with
`KURT_ENV=test`, which `kurt test` sets. A fixture's `password:` becomes
its `encrypted_password`.

Not yet: signing in with another service (OAuth), confirming a changed address,
more than one model signing in from the same session at once, and sessions
stored in the database so they can be ended remotely.

Applications made with Kurt's earlier generator keep working:
`has_secure_password`, `authenticate_by`, `sign_in_as` and
`allow_unauthenticated_access` are still there. `kurt generate
authentication` refuses to run over them.

## Seeds and test fixtures

`db/seeds.iyi` writes a new database's first records with the models.
`kurt db:seed` runs it, and `kurt db:reset` runs it after migrating.

`find_or_create_by` finds an existing record or creates it, so the file can
be run any number of times. `!` works here too; on an error the command
prints the reason:

```iyi
# db/seeds.iyi
ada = User.find_or_create_by(email: "ada@example.com") do |user|
  user.name = "Ada"                    # the block runs only for a new record
  user.password = "password123"
end!
Post.find_or_create_by(title: "Welcome", user_id: ada.id)!
```

Tests start with the records in `test/fixtures/<table>.yml`. Each test file
loads the fixtures afresh, so a record a previous file deleted or changed
comes back. A test reads a record by its label: `users(:ada)`.

```yaml
# test/fixtures/users.yml
ada:
  name: Ada
  email: ada@example.com
  password: password123      # becomes encrypted_password (or password_digest): a bcrypt digest

# test/fixtures/posts.yml
welcome:
  title: Welcome
  user: ada                  # user_id: the id of ada in users.yml
```

```iyi
# test/posts_test.iyi
sign_in(users(:ada))
assert posts(:welcome).user.as(User).name == "Ada"
```

- A label's id is the same on every run; that is how fixtures refer to
  each other.
- `created_at` and `updated_at` are filled when present.
- A column that does not exist, or a value that does not fit its type, is
  reported with its file and label before the tests start.

`!` does not work at a test's top level, because iyi cannot hand an error
up while it initializes a module. Use `.as(User)` there.

## Tailwind CSS and daisyUI

By default `kurt new` sets the application up with
[Tailwind CSS](https://tailwindcss.com) and [daisyUI](https://daisyui.com);
no Node is needed.
- Tailwind's single-file CLI (v4.3.5) is downloaded once into
  `~/.cache/kurt/` and checked against the release's `sha256sums.txt`.
- daisyUI's two files (v5.8.2) go into the application:

```
app/assets/tailwind/app.css            input: @import "tailwindcss", @plugin "./daisyui.mjs"
app/assets/tailwind/daisyui.mjs        daisyUI
app/assets/tailwind/daisyui-theme.mjs  for writing your own theme
public/assets/app.css                  output (compiled, not in git)
```

`kurt dev` compiles the CSS before every build, and `kurt build` compiles
it minified. Classes are read from `app/views/**/*.eiy`, so writing a new
class in a view and saving is enough.

Themes:
- The theme is chosen in `app.css`'s `@plugin` line. Two are installed:
  `light`, and `dracula` for dark.
- Dracula is used when the system is in dark mode.
  `<html data-theme="dracula">` or `data-theme="light"` fixes one.
- The layout's navbar has a theme button. It switches between the two
  themes and remembers the choice in the browser (`localStorage`); with no
  choice, the system theme applies.

In such an application, scaffolds use daisyUI components:
- `navbar`, `btn`, `table`, `card`, `fieldset`, `alert`;
- `input`, `select` and `textarea`, through `form_with` and
  `form_style :daisyui` (a field that fails validation turns red with
  `input-error`).

`kurt new blog --css none` installs none of this: the application comes
with a plain `public/assets/app.css` and simple classes. For an application
created offline, run `kurt css:install` later.

## Hot reload

`kurt dev` watches `app/`, `config/`, `db/schema.json` and `iyi.mod`. When
a file changes:
1. It builds the application beside the running one (a few seconds).
2. If the build succeeds, it stops the old server and starts the new one.
3. Open pages reload themselves: the layout's
   `<%= raw(live_reload_tag) %>` prints a script, only under `kurt dev`.

A change that does not build shows iyi's error, with the line of the file
you wrote, and the last good server keeps running.

`public/` is served from disk, so changes there need no restart.
`kurt dev --no-reload` runs without watching.

## Deployment

`kurt build` compiles the application into one executable. The server
needs neither iyi nor the source code, and the migrations are inside the
binary:

```sh
kurt build                                   # bin/blog
scp -r bin/blog public server:/srv/blog/     # public/ sits next to the binary

# on the server
export KURT_ENV=production
export DATABASE_URL=postgres://app@db.local/blog
export SESSION_SECRET=$(openssl rand -hex 32)   # generate once and keep it
./bin/blog db:migrate                        # pending migrations; db:status too
./bin/blog -b 0.0.0.0 -p 8080
```

In production:

- The application refuses to start without a `SESSION_SECRET` of at least
  32 bytes. The development secret is in the repository, so starting with
  it would let anyone forge sessions.
- The session cookie is `Secure`, sent only over HTTPS. Run the application
  behind a proxy that terminates HTTPS (nginx, Caddy, a load balancer).
- `GET /up` answers 200 `OK` when the application and the database are up,
  and 503 otherwise. It is the load balancer's health check.
- Every response carries `X-Content-Type-Options`, `X-Frame-Options` and
  `Referrer-Policy`, and over HTTPS `Strict-Transport-Security`.
- Every request gets an `X-Request-Id`, written to its log line.
- On `TERM` the server stops accepting connections, finishes the requests
  in progress and exits.

Each of these is one line in `config/application.iyi`, which the
application can change.

## Static export

A site with no database writes, such as documentation or a landing page,
can be hosted without a server. `kurt export` writes the application as
static files:

```sh
kurt export                      # dist/
kurt export -o public_html /posts/1 /posts/2
```

1. It builds the application and runs it on a local port.
2. It fetches every GET route that has no parameter (`/`, `/guide`, not
   `/posts/:id`).
3. It follows the local links (`href`, `src`) on each HTML page it fetches.
4. It fetches each `PATH` given, for pages with parameters that no page
   links to.
5. It copies `public/` as it is.

Each page goes where static hosts serve it at the same URL: `/` is
`dist/index.html`, `/guide` is `dist/guide/index.html`, `/llms.txt` is
`dist/llms.txt`. A page that does not answer 200 is skipped and named.
Upload `dist/` to GitHub Pages, Netlify, S3 or any web server.

- The pages are what the application answers when it starts, from the
  development database unless `DATABASE_URL` says otherwise.
- Forms, sessions and anything else that needs a server do not work in the
  exported site.
- The site must be served from the domain's root, since links start with
  `/`.
- `kurt export` empties a directory it wrote before, and refuses any other
  directory that is not empty.

## Not yet

- `with_count` for counting associations.
- A `respond_to` block; there are `wants_json?` and `json(data)`.
- `kurt ui add` and a `/styleguide` page.
- A binary release of the CLI; install it from source with `make install`.

Tests send requests to the routes through iyi-web's harness, so middleware
(sessions, CSRF) is skipped. Fixtures are loaded once per test file, not
per test.

## Development

```sh
make            # bin/kurt
make test       # the tests, on SQLite in memory
make test-pg PG_URL=postgres://user@127.0.0.1:5432/kurt_test
```

The model, fixture, authentication, jobs and storage tests pass on both SQLite and PostgreSQL 16.

| File | |
|---|---|
| `model.iyi` | `Query(T)` (joins, pluck, calculations, group_by), `derive model`, association macros (through), `NotFound` / `Invalid` / `Errors` |
| `controllers.iyi` | `Controller`, `render`, route macros, `before_action`, error pages |
| `strong_parameters.iyi` | `params.require(...).permit(...)` |
| `helpers.iyi` | view helpers |
| `forms.iyi` | `form_with`'s form builder |
| `authentication.iyi` | `authentication :...` in a model: passwords, signed tokens, lock, tracking; the sign-in rate limit |
| `authentication_generators.iyi` | `kurt generate authentication`, and the controllers, views, mails and routes Kurt ships |
| `storage.iyi` | `has_one_attached`, `has_many_attached`, disk storage, `/files/...` |
| `jobs.iyi` | `Job`, `perform_later`, the `kurt_jobs` queue, the worker loop |
| `mailers.iyi`, `mail_views.iyi` | mailers, `deliveries`, SMTP; the program that finds a mail's views at compile time |
| `json_writer.iyi` | the JSON that `json(data)` writes |
| `exporter.iyi` | `kurt export`'s routes, output files and links |
| `migrator.iyi` | timestamped SQL migrations |
| `release.iyi` | the release binary's `db:migrate` / `db:status` commands |
| `fixtures.iyi` | reads `test/fixtures/*.yml` and loads them into the test database |
| `datasource.iyi` | connection pool, placeholder dialect |
| `environment.iyi` | `KURT_ENV`, `DATABASE_URL` |
| `inflector.iyi` | plural/singular, `underscore`, `camelize` |
| `generators.iyi` | the files `new` and `generate` write |
| `autoload.iyi` | modules from the headerless application files |
| `schema.iyi` | `db/schema.json`: reading tables, SQL → iyi type mapping |
| `cmd/kurt.iyi` | the CLI |

## License

[MIT](LICENSE).
