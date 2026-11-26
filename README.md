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
- A C compiler (`cc`).
- SQLite (macOS ships it).
- PostgreSQL is optional.

## Install

```sh
git clone https://github.com/iyikurt/kurt.git ~/src/kurt
cd ~/src/kurt
make install           # builds bin/kurt and links it to ~/.local/bin/kurt
export PATH="$HOME/.local/bin:$PATH"
kurt version
```

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
| `kurt generate authentication` | Users, sign-in and sign-up; every page then requires sign-in |
| `kurt db:migrate` / `db:rollback [N]` / `db:status` / `db:reset` | Manage the schema (`db:reset` also runs the seeds) |
| `kurt db:seed` | Runs `db/seeds.iyi` |
| `kurt routes` | Lists every route with its path and `Controller#action` |
| `kurt dev [-p PORT]` | Runs the server; on a change it rebuilds, restarts and reloads the page |
| `kurt test` | Migrates a fresh test database and runs each `test/*_test.iyi` with fixtures |
| `kurt build` | A release binary in `bin/NAME`, with minified CSS and the migrations inside |
| `kurt export [-o DIR] [PATH...]` | The application as static files in `dist/` (or `DIR`), for hosting with no server |
| `kurt css:build [--minify]` | Compiles `app/assets/tailwind/app.css` to `public/assets/app.css` |
| `kurt css:install` | Downloads the Tailwind CLI and daisyUI, for an application created offline |

Field types:
- `string`, `text`, `int`, `float`, `bool`, `time`;
- `references`: `user:references` gives a `user_id` column and `belongs_to user`.

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
`Unauthorized`, `Forbidden`, `NotFound` or `DBError` (directly, or handed
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
| `Unauthorized` | A redirect to `/login`; 401 for JSON |
| `Forbidden` | 403 |
| `DBError` | 503; the details go only to the log |

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

### Associated records in forms

In a scaffold, a field like `user:references` becomes a select box when a
`User` model exists. The options show that table's first text column:
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

## Authentication

```sh
kurt generate authentication
kurt db:migrate
```

This sets up sign-in, sign-out and sign-up:

| Where | What |
|---|---|
| `app/models/user.iyi` | `has_secure_password`; email (lowercased, unique); password of at least 8 characters. Added to `User` if it exists. |
| migration | A new table, or `password_digest` added to an existing `users` (and an email column if it has none) |
| `SessionsController` | `GET/POST /login`, `DELETE /logout` |
| `RegistrationsController` | `GET/POST /signup` |
| `ApplicationController` | `before_action :require_authentication`, `current_user?` |
| views, layout | Sign-in and sign-up forms; the navbar shows sign in/sign up, or sign out |
| `test/sessions_test.iyi` | Sign-up, sign-in and sign-out, with a real session cookie |

From then on every page requires sign-in. A visitor who is not signed in
goes to `/login`, and comes back to the page they asked for afterwards.
A controller names its public pages:

```iyi
class PostsController < ApplicationController
  allow_unauthenticated_access only: [:index, :show]
end
```

`allow_unauthenticated_access` is short for
`skip_before_action :require_authentication`; `skip_before_action` works
for other filters too. A view asks who is signed in with
`<% if user = current_user? %>`.

Passwords:
- They are stored with bcrypt (`std/password`; tests use the lowest cost).
- A new record must have one.
- At most 72 bytes.
- If `password_confirmation` is given, it must match.
- A password left blank on an edit form keeps the old one.

Signing in:
- `User.authenticate_by("email_address", address, password)!` answers the
  user, or nil.
- When there is no such user, it still checks a password. That way, the
  response time does not reveal which addresses are registered.
- Signing in renews the session id.

In tests, `sign_in_as(user)` makes the following requests as that user.
It works only with `KURT_ENV=test`, which `kurt test` sets. The generator
adds a `sign_in_as(...)` line to existing tests, and scaffold tests
generated later come with one.

Not yet: password reset (it needs email), rate limiting of sign-in
attempts, "remember me", and sessions stored in the database so they can be
ended remotely.

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
  password: password123      # becomes a bcrypt digest in a table with password_digest

# test/fixtures/posts.yml
welcome:
  title: Welcome
  user: ada                  # user_id: the id of ada in users.yml
```

```iyi
# test/posts_test.iyi
sign_in_as(users(:ada))
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
- `input`, `select` and `textarea` (a field that fails validation turns red
  with `input-error`).

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

The model and fixture tests pass on both SQLite and PostgreSQL 16.

| File | |
|---|---|
| `model.iyi` | `Query(T)`, `derive model`, association macros, `NotFound` / `Invalid` / `Errors` |
| `controllers.iyi` | `Controller`, `render`, route macros, `before_action`, error pages |
| `strong_parameters.iyi` | `params.require(...).permit(...)` |
| `helpers.iyi` | view helpers |
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
