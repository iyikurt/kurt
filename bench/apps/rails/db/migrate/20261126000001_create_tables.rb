# The same tables as bench/apps/kurt's migrations: no foreign key
# constraints (Kurt's generator writes none), an index on each *_id.
class CreateTables < ActiveRecord::Migration[8.1]
  def change
    create_table :users do |t|
      t.string :name, null: false, default: ""
      t.string :email, null: false, default: ""
      t.timestamps default: -> { "now()" }
    end

    create_table :posts do |t|
      t.bigint :user_id, null: false, default: 0, index: true
      t.string :title, null: false, default: ""
      t.text :body, null: false, default: ""
      t.boolean :published, null: false, default: false
      t.timestamps default: -> { "now()" }
    end

    create_table :comments do |t|
      t.bigint :post_id, null: false, default: 0, index: true
      t.string :author, null: false, default: ""
      t.text :body, null: false, default: ""
      t.timestamps default: -> { "now()" }
    end
  end
end
