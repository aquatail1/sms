INSERT INTO tree_nodes (parent_id, name, path, depth)
VALUES (NULL, 'HQ', 'HQ', 0)
ON CONFLICT (path) DO UPDATE SET name = EXCLUDED.name, updated_at = NOW();

INSERT INTO tree_nodes (parent_id, name, path, depth)
SELECT id, 'Seoul', 'HQ.Seoul'::ltree, 1
FROM tree_nodes
WHERE path = 'HQ'::ltree
ON CONFLICT (path) DO UPDATE SET name = EXCLUDED.name, updated_at = NOW();

INSERT INTO tree_nodes (parent_id, name, path, depth)
SELECT id, 'Payment', 'HQ.Seoul.Payment'::ltree, 2
FROM tree_nodes
WHERE path = 'HQ.Seoul'::ltree
ON CONFLICT (path) DO UPDATE SET name = EXCLUDED.name, updated_at = NOW();
