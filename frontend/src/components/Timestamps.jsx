import { useState } from "react";
import { chat as chatApi } from "../api.js";
import { formatTime } from "./FileList.jsx";

export default function Timestamps({ fileId, onPlay }) {
  const [topic, setTopic] = useState("");
  const [hits, setHits] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const submit = async (e) => {
    e.preventDefault();
    if (!topic.trim()) return;
    setBusy(true);
    setError("");
    try {
      const res = await chatApi.timestamps(fileId, topic.trim());
      setHits(res.hits || []);
    } catch (err) {
      setError(err?.response?.data?.detail || err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <form onSubmit={submit} style={{ display: "flex", gap: 8, marginBottom: 12 }}>
        <input
          type="text"
          value={topic}
          onChange={(e) => setTopic(e.target.value)}
          placeholder="Enter a topic..."
          style={{
            flex: 1,
            padding: "10px 16px",
            background: "#FFF",
            color: "var(--text)",
            border: "2px solid var(--text)",
            borderRadius: 999,
            fontFamily: "var(--font-body)",
            fontSize: 14,
            outline: "none",
          }}
        />
        <button className="btn" disabled={busy}>
          Find →
        </button>
      </form>
      {error && <div style={{ color: "var(--red-2)", marginBottom: 6, fontWeight: 700 }}>{error}</div>}
      {hits.length === 0 && !busy && <div className="empty" style={{ padding: 12 }}>No results yet.</div>}
      <div className="timestamps">
        {hits.map((h) => (
          <div key={h.chunk_id} className="item">
            <span className="t">{formatTime(h.start_time)} – {formatTime(h.end_time)}</span>
            <span className="snippet">{h.text.slice(0, 120)}</span>
            <button className="btn small red" onClick={() => onPlay?.(h.start_time)}>▶ Play</button>
          </div>
        ))}
      </div>
    </div>
  );
}
