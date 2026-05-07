import { useEffect, useMemo, useState } from "react";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";

const columns = [
  "hostname",
  "os_type",
  "status",
  "cpu_usage_pct",
  "mem_usage_pct",
  "disk_read_bytes_ps",
  "disk_write_bytes_ps",
  "net_rx_bytes_ps",
  "net_tx_bytes_ps",
  "last_seen_at",
];

function apiUrl(path) {
  return `${API_BASE}${path}`;
}

function TreeNode({ node, selectedNodeId, onSelect }) {
  return (
    <li>
      <button
        onClick={() => onSelect(node.id)}
        style={{ fontWeight: selectedNodeId === node.id ? "bold" : "normal" }}
      >
        {node.name}
      </button>
      {node.children.length > 0 && (
        <ul>
          {node.children.map((child) => (
            <TreeNode key={child.id} node={child} selectedNodeId={selectedNodeId} onSelect={onSelect} />
          ))}
        </ul>
      )}
    </li>
  );
}

function buildTree(rows) {
  const byId = new Map(rows.map((row) => [row.id, { ...row, children: [] }]));
  const roots = [];

  for (const node of byId.values()) {
    if (node.parent_id && byId.has(node.parent_id)) {
      byId.get(node.parent_id).children.push(node);
    } else {
      roots.push(node);
    }
  }

  return roots;
}

export default function App() {
  const [tree, setTree] = useState([]);
  const [nodeId, setNodeId] = useState(null);
  const [items, setItems] = useState([]);
  const [error, setError] = useState(null);

  const treeRoots = useMemo(() => buildTree(tree), [tree]);

  useEffect(() => {
    fetch(apiUrl("/api/v1/tree"))
      .then((r) => {
        if (!r.ok) throw new Error(`tree fetch failed: ${r.status}`);
        return r.json();
      })
      .then((rows) => {
        setTree(rows);
        setNodeId((current) => current ?? rows[0]?.id ?? null);
        setError(null);
      })
      .catch((err) => setError(err.message));
  }, []);

  useEffect(() => {
    if (!nodeId) {
      setItems([]);
      return;
    }

    fetch(apiUrl(`/api/v1/nodes/${nodeId}/agents?include_descendants=true&page=1&size=50`))
      .then((r) => {
        if (!r.ok) throw new Error(`agents fetch failed: ${r.status}`);
        return r.json();
      })
      .then((d) => {
        setItems(d.items || []);
        setError(null);
      })
      .catch((err) => setError(err.message));
  }, [nodeId]);

  return (
    <div style={{ display: "grid", gridTemplateColumns: "260px 1fr", gap: 12 }}>
      <aside>
        <h3>Tree</h3>
        {error && <p style={{ color: "crimson" }}>{error}</p>}
        {treeRoots.length === 0 ? (
          <p>No tree nodes. Run an agent once or seed `tree_nodes`.</p>
        ) : (
          <ul>
            {treeRoots.map((node) => (
              <TreeNode key={node.id} node={node} selectedNodeId={nodeId} onSelect={setNodeId} />
            ))}
          </ul>
        )}
      </aside>
      <main>
        <h3>Agents</h3>
        <table border="1" cellPadding="6">
          <thead>
            <tr>{columns.map((c) => <th key={c}>{c}</th>)}</tr>
          </thead>
          <tbody>
            {items.length === 0 ? (
              <tr>
                <td colSpan={columns.length}>No agents for selected tree node.</td>
              </tr>
            ) : (
              items.map((row) => (
                <tr key={row.agent_id}>
                  {columns.map((c) => <td key={c}>{String(row[c] ?? "")}</td>)}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </main>
    </div>
  );
}
