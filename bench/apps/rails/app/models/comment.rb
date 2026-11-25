class Comment < ApplicationRecord
  belongs_to :post

  validates :post_id, :author, presence: true
end
