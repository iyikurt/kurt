-- up
CREATE TABLE posts (id INTEGER PRIMARY KEY, title TEXT NOT NULL DEFAULT 'a;b');

-- down
DROP TABLE posts;
