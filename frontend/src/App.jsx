import { useEffect, useState } from "react";

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

export default function App() {
  const [tree, setTree] = useState([]);
  const [nodeId, setNodeId] = useState(3);
  const [items, setItems] = useState([]);

  useEffect(() => {
    fetch("/api/v1/tree")
      .then((r) => r.json())
      .then(setTree);
  }, []);

  useEffect(() => {
    fetch(`/api/v1/nodes/${nodeId}/agents?include_descendants=true&page=1&size=50`)
      .then((r) => r.json())
      .then((d) => setItems(d.items || []));
  }, [nodeId]);

  return (
    <div style={{ display: "grid", gridTemplateColumns: "260px 1fr", gap: 12 }}>
      <aside>
        <h3>Tree</h3>
        <ul>
          {tree.map((n) => (
            <li key={n.id}>
              <button onClick={() => setNodeId(n.id)}>{n.path}</button>
            </li>
          ))}
        </ul>
      </aside>
      <main>
        <h3>Agents</h3>
        <table border="1" cellPadding="6">
          <thead>
            <tr>{columns.map((c) => <th key={c}>{c}</th>)}</tr>
          </thead>
          <tbody>
            {items.map((row) => (
              <tr key={row.agent_id}>
                {columns.map((c) => <td key={c}>{String(row[c] ?? "")}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </main>
    </div>
  );
}
