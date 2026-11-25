# `allow_browser versions: :modern`, which `rails new` writes here, is left
# out: it parses every request's User-Agent and Kurt has nothing like it.
class ApplicationController < ActionController::Base
end
