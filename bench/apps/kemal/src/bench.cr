# The benchmark's endpoints in Kemal. bench/apps/kurt and bench/apps/rails
# have the same six, answering the same bodies; `bench.py check` compares
# them before any load runs.
#
# Kemal is a micro-framework: no ORM, validations or strong parameters, so
# this is what a Kemal application writes instead - SQL through crystal-db,
# a validation by hand. Sessions and CSRF are the small handlers below, not
# kemal-session and kemal-csrf: kemal-csrf replaces the token after every
# POST (a load test cannot reuse one) and kemal-session's memory engine is a
# Hash without a lock (unsafe on several threads). These keep the token for
# the session, as Rails and Kurt do, in a signed cookie.
require "kemal"
require "db"
require "pg"
require "json"
require "html"
require "uuid"
require "base64"
require "openssl/hmac"
require "crypto/subtle"
require "random/secure"

DBP    = DB.open(ENV["DATABASE_URL"])
SECRET = ENV["SESSION_SECRET"]? || raise "SESSION_SECRET is not set"

# X-Request-Id and the headers Rails' and Kurt's defaults send.
class SecurityHeaders < Kemal::Handler
  def call(env)
    headers = env.response.headers
    headers["X-Frame-Options"] = "SAMEORIGIN"
    headers["X-Content-Type-Options"] = "nosniff"
    headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    headers["X-Request-Id"] = UUID.random.to_s
    call_next(env)
  end
end

# A session in a cookie, `base64(json)--hmac`, and the CSRF token in it.
class SessionCSRF < Kemal::Handler
  COOKIE = "_bench_session"
  SAFE   = %w(GET HEAD OPTIONS)

  # The session is read only where it is used - an unsafe request here, or
  # `csrf_token` - and a cookie written only for a new one, as Rails and
  # Kurt do: a plain GET pays nothing.
  def call(env)
    unless SAFE.includes?(env.request.method)
      token = SessionCSRF.read(env).try(&.["csrf"]?) || ""
      sent = env.request.headers["X-CSRF-Token"]? || env.params.body["authenticity_token"]? || ""
      unless !token.empty? && Crypto::Subtle.constant_time_compare(sent, token)
        env.response.status_code = 422
        env.response.print "Invalid authenticity token"
        return
      end
    end
    call_next(env)
  end

  def self.csrf_token(env) : String
    session = read(env) || {} of String => String
    unless token = session["csrf"]?
      token = session["csrf"] = Random::Secure.urlsafe_base64(32)
      write(env, session)
    end
    token
  end

  def self.read(env) : Hash(String, String)?
    value = env.request.cookies[COOKIE]?.try(&.value) || return nil
    data, _, mac = value.rpartition("--")
    return nil unless Crypto::Subtle.constant_time_compare(mac, sign(data))
    Hash(String, String).from_json(Base64.decode_string(data))
  rescue
    nil
  end

  def self.write(env, session)
    data = Base64.urlsafe_encode(session.to_json)
    env.response.cookies << HTTP::Cookie.new(COOKIE, "#{data}--#{sign(data)}", path: "/", http_only: true,
      samesite: HTTP::Cookie::SameSite::Lax)
  end

  def self.sign(data)
    OpenSSL::HMAC.hexdigest(:sha256, SECRET, data)
  end
end

struct Post
  include DB::Serializable
  getter id : Int64
  getter user_id : Int64
  getter title : String
  getter body : String
  getter published : Bool
end

struct Comment
  include DB::Serializable
  getter id : Int64
  getter post_id : Int64
  getter author : String
  getter body : String
end

def h(text) : String
  HTML.escape(text.to_s)
end

def json(env, data, status = 200)
  env.response.status_code = status
  env.response.content_type = "application/json; charset=utf-8"
  data.to_json
end

def not_found(env)
  env.response.status_code = 404
  env.response.content_type = "text/plain; charset=utf-8"
  "Not found"
end

POST_COLUMNS    = "id, user_id, title, body, published"
COMMENT_COLUMNS = "id, post_id, author, body"

get "/up" do
  DBP.scalar("SELECT 1")
  "OK"
end

get "/bench/plaintext" do |env|
  env.response.content_type = "text/plain; charset=utf-8"
  "Hello, World!"
end

get "/bench/json" do |env|
  json(env, {message: "Hello, World!"})
end

# One row by primary key.
get "/bench/posts/:id" do |env|
  post = DBP.query_one?("SELECT #{POST_COLUMNS} FROM posts WHERE id = $1", env.params.url["id"].to_i64, as: Post)
  next not_found(env) unless post
  json(env, {id: post.id, user_id: post.user_id, title: post.title, body: post.body, published: post.published})
end

# 20 posts and their comments, two queries.
get "/bench/feed" do |env|
  posts = DBP.query_all("SELECT #{POST_COLUMNS} FROM posts WHERE published = true ORDER BY id DESC LIMIT 20", as: Post)
  comments = DBP.query_all("SELECT #{COMMENT_COLUMNS} FROM comments WHERE post_id = ANY($1)",
    posts.map(&.id), as: Comment).group_by(&.post_id)
  json(env, posts.map { |post|
    {id: post.id, title: post.title,
     comments: (comments[post.id]? || [] of Comment).map { |c| {id: c.id, author: c.author, body: c.body} }}
  })
end

# Layout, view, a partial per comment.
get "/bench/posts/:id/page" do |env|
  post = DBP.query_one?("SELECT #{POST_COLUMNS} FROM posts WHERE id = $1", env.params.url["id"].to_i64, as: Post)
  next not_found(env) unless post
  comments = DBP.query_all("SELECT #{COMMENT_COLUMNS} FROM comments WHERE post_id = $1 ORDER BY id", post.id, as: Comment)
  title = post.title
  render "src/views/page.ecr", "src/views/layout.ecr"
end

# A validation by hand and a transaction of two rows.
post "/bench/posts" do |env|
  title = env.params.body["post[title]"]? || ""
  body = env.params.body["post[body]"]? || ""
  user_id = (env.params.body["post[user_id]"]? || "").to_i64? || 0_i64
  next json(env, {message: "invalid"}, 422) if title.blank? || title.size > 120 || user_id == 0
  id = 0_i64
  DBP.transaction do |tx|
    db = tx.connection
    id = db.scalar("INSERT INTO posts (user_id, title, body, published, created_at, updated_at) " \
                   "VALUES ($1, $2, $3, false, now(), now()) RETURNING id", user_id, title, body).as(Int64)
    db.exec("INSERT INTO comments (post_id, author, body, created_at, updated_at) VALUES ($1, $2, $3, now(), now())",
      id, "bench", "first")
  end
  json(env, {id: id, title: title}, 201)
end

# The session cookie and token the POST scenario sends.
get "/bench/csrf" do |env|
  env.response.content_type = "text/plain; charset=utf-8"
  SessionCSRF.csrf_token(env)
end

use SecurityHeaders.new
use SessionCSRF.new
Kemal.config.env = "production"
# Crystal 1.22's default execution context is parallel but starts on one
# thread; CRYSTAL_WORKERS threads serve here, as `-w` does for Kurt.
Fiber::ExecutionContext.default.resize(Fiber::ExecutionContext.default_workers_count)
Kemal.run
