-- 0028_blog_nav_rename: the blog moved from /journal to /blog. Update the
-- already-seeded header nav item in place (existing deployments won't re-run
-- the dev seed, so the rename has to happen here too).
PRAGMA foreign_keys = ON;

UPDATE navigation_items
SET label = 'Blog', destination_reference = '/blog'
WHERE destination_type = 'internal_path' AND destination_reference = '/journal';
