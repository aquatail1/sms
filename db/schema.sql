CREATE EXTENSION IF NOT EXISTS ltree;

CREATE TABLE IF NOT EXISTS tree_nodes (
  id BIGSERIAL PRIMARY KEY,
  parent_id BIGINT REFERENCES tree_nodes(id) ON DELETE CASCADE,
  name VARCHAR(120) NOT NULL,
  path LTREE NOT NULL UNIQUE,
  depth INT NOT NULL DEFAULT 0,
  sort_order INT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS agents (
  id UUID PRIMARY KEY,
  hostname VARCHAR(120) NOT NULL,
  os_type VARCHAR(20) NOT NULL CHECK (os_type IN ('windows','linux','macos')),
  os_version VARCHAR(120),
  ip_address INET,
  node_id BIGINT NOT NULL REFERENCES tree_nodes(id) ON DELETE RESTRICT,
  agent_version VARCHAR(40),
  status VARCHAR(20) NOT NULL DEFAULT 'unknown' CHECK (status IN ('online','offline','unknown')),
  last_seen_at TIMESTAMPTZ,
  tags JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS metrics_resource (
  time TIMESTAMPTZ NOT NULL,
  agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
  cpu_usage_pct NUMERIC(5,2),
  mem_usage_pct NUMERIC(5,2),
  mem_used_bytes BIGINT,
  mem_total_bytes BIGINT,
  disk_read_bytes_ps BIGINT,
  disk_write_bytes_ps BIGINT,
  net_rx_bytes_ps BIGINT,
  net_tx_bytes_ps BIGINT,
  load1 NUMERIC(6,2),
  load5 NUMERIC(6,2),
  load15 NUMERIC(6,2),
  PRIMARY KEY (time, agent_id)
);

CREATE INDEX IF NOT EXISTS idx_tree_nodes_path ON tree_nodes USING GIST(path);
CREATE INDEX IF NOT EXISTS idx_agents_node_id ON agents(node_id);
CREATE INDEX IF NOT EXISTS idx_agents_last_seen_at ON agents(last_seen_at DESC);
CREATE INDEX IF NOT EXISTS idx_metrics_agent_time ON metrics_resource(agent_id, time DESC);
