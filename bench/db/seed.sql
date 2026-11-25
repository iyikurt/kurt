-- The same rows for both applications: 100 users, 10,000 posts (every
-- second one published), 5 comments a post. Deterministic, so the two
-- apps answer the same bodies. Run with: psql DB -f bench/db/seed.sql
BEGIN;
TRUNCATE comments, posts, users RESTART IDENTITY;

INSERT INTO users (name, email, created_at, updated_at)
SELECT 'User ' || i, 'user' || i || '@example.com', now(), now()
FROM generate_series(1, 100) AS i;

INSERT INTO posts (user_id, title, body, published, created_at, updated_at)
SELECT 1 + (i % 100), 'Post ' || i,
       repeat('Lorem ipsum dolor sit amet, <consectetur> & adipiscing elit. ', 8),
       i % 2 = 0, now(), now()
FROM generate_series(1, 10000) AS i;

INSERT INTO comments (post_id, author, body, created_at, updated_at)
SELECT p, 'Reader ' || c, 'Comment ' || c || ' on post ' || p || ' "quoted"', now(), now()
FROM generate_series(1, 10000) AS p, generate_series(1, 5) AS c
ORDER BY p, c;
COMMIT;
