-- up
CREATE TABLE users (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL
);
CREATE INDEX users_name ON users (name);

-- down
DROP TABLE users;
