Rails.application.routes.draw do
  get "up" => "rails/health#show", as: :rails_health_check

  get "/bench/plaintext", to: "bench#plaintext"
  get "/bench/json", to: "bench#json_hello"
  get "/bench/feed", to: "bench#feed"
  get "/bench/csrf", to: "bench#csrf"
  get "/bench/posts/:id", to: "bench#show"
  get "/bench/posts/:id/page", to: "bench#page"
  post "/bench/posts", to: "bench#create"
end
