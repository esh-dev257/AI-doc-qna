export default function FileList({ items, selectedId, onSelect, onDelete }) {
  if (items.length === 0) {
    return <div className="empty" style={{ padding: 10 }}>No files yet.</div>;
  }
  return (
    <ul className="file-list">
      {items.map((f) => (
        <li
          key={f.id}
          className={`file-item ${selectedId === f.id ? "active" : ""}`}
          onClick={() => onSelect(f.id)}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div className="name">{f.filename}</div>
            <span className={`badge ${f.status}`}>{f.status}</span>
          </div>
          <div className="meta">
            {f.kind.toUpperCase()} · {formatSize(f.size_bytes)}
            {f.duration_seconds ? ` · ${formatTime(f.duration_seconds)}` : ""}
          </div>
          <div style={{ marginTop: 6 }}>
            <button
              className="btn secondary small"
              onClick={(e) => {
                e.stopPropagation();
                onDelete(f.id);
              }}
            >
              Delete
            </button>
          </div>
        </li>
      ))}
    </ul>
  );
}

function formatSize(bytes) {
  if (!bytes) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  let n = bytes;
  let i = 0;
  while (n >= 1024 && i < units.length - 1) {
    n /= 1024;
    i++;
  }
  return `${n.toFixed(n > 10 ? 0 : 1)} ${units[i]}`;
}

export function formatTime(seconds) {
  if (!seconds && seconds !== 0) return "";
  const s = Math.floor(seconds % 60);
  const m = Math.floor((seconds / 60) % 60);
  const h = Math.floor(seconds / 3600);
  const pad = (n) => String(n).padStart(2, "0");
  return h ? `${h}:${pad(m)}:${pad(s)}` : `${m}:${pad(s)}`;
}
