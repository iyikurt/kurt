# The benchmark's endpoints. bench/apps/kurt has the same six, answering
# the same bodies; bench/check.sh compares them before any load runs.
class BenchController < ApplicationController
  # GET /bench/plaintext
  def plaintext
    render plain: "Hello, World!"
  end

  # GET /bench/json
  def json_hello
    render json: { message: "Hello, World!" }
  end

  # GET /bench/posts/:id - one row by primary key
  def show
    post = Post.find(params[:id])
    render json: { id: post.id, user_id: post.user_id, title: post.title, body: post.body, published: post.published }
  end

  # GET /bench/feed - 20 posts and their comments, two queries
  def feed
    posts = Post.where(published: true).order(id: :desc).limit(20).includes(:comments)
    render json: posts.map { |post|
      { id: post.id, title: post.title,
        comments: post.comments.map { |c| { id: c.id, author: c.author, body: c.body } } }
    }
  end

  # GET /bench/posts/:id/page - layout, view, a partial per comment
  def page
    @post = Post.find(params[:id])
    @comments = @post.comments.order(:id).to_a
  end

  # POST /bench/posts - strong params, validation, a transaction of two rows
  def create
    attrs = params.expect(post: [ :title, :body, :user_id ])
    post = Post.transaction do
      post = Post.create!(attrs)
      Comment.create!(post_id: post.id, author: "bench", body: "first")
      post
    end
    render json: { id: post.id, title: post.title }, status: :created
  rescue ActiveRecord::RecordInvalid
    render json: { message: "invalid" }, status: :unprocessable_content
  end

  # GET /bench/csrf - the session cookie and token the POST scenario sends
  def csrf
    render plain: form_authenticity_token
  end
end
