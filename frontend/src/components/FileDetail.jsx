import { useEffect, useRef, useState } from "react";
import { chat as chatApi, files as filesApi } from "../api.js";
import MediaPlayer from "./MediaPlayer.jsx";
import ChatPanel from "./ChatPanel.jsx";
import Timestamps from "./Timestamps.jsx";

export default function FileDetail({ file, onRefresh }) {
  const mediaRef = useRef(null);
  const [blobUrl, setBlobUrl] = useState(null);

  useEffect(() => {
    let revoked;
    const load = async () => {
      setBlobUrl(null);
      if (file.kind === "pdf") return;
      if (file.status !== "ready") return;
      const token = localStorage.getItem("token");
      const resp = await fetch(`/api/files/${file.id}/media`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!resp.ok) return;
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      revoked = url;
      setBlobUrl(url);
    };
    load();
    return () => {
      if (revoked) URL.revokeObjectURL(revoked);
    };
  }, [file.id, file.kind, file.status]);

  const playAt = (seconds) => {
    if (!mediaRef.current) return;
    mediaRef.current.currentTime = seconds;
    mediaRef.current.play?.();
  };

  return (
    <div className="viewer">
      <div>
        <div className="card">
          <h3 style={{ display: "flex", justifyContent: "space-between" }}>
            <span>{file.filename}</span>
            <span className={`badge ${file.status}`}>{file.status}</span>
          </h3>
          {file.error && <div style={{ color: "var(--err)" }}>Error: {file.error}</div>}

          {file.kind !== "pdf" && blobUrl && (
            <MediaPlayer ref={mediaRef} kind={file.kind} src={blobUrl} />
          )}
          {file.kind === "pdf" && file.status === "ready" && (
            <div style={{ marginTop: 10 }}>
              <a
                className="btn secondary small"
                href={`/api/files/${file.id}/media`}
                target="_blank"
                rel="noopener noreferrer"
              >
                Open PDF
              </a>
            </div>
          )}
        </div>
        <div className="card" style={{ marginTop: 16 }}>
          <h3>Summary</h3>
          <SummaryBlock file={file} />
        </div>
        {(file.kind === "audio" || file.kind === "video") && file.status === "ready" && (
          <div className="card" style={{ marginTop: 16 }}>
            <h3>Find Timestamps</h3>
            <Timestamps fileId={file.id} onPlay={playAt} />
          </div>
        )}
      </div>
      <div className="card">
        <h3>Chat</h3>
        {file.status === "ready" ? (
          <ChatPanel file={file} onPlay={playAt} />
        ) : (
          <div className="empty">
            File is {file.status}. {file.status !== "failed" && <button className="btn small" onClick={onRefresh}>Refresh</button>}
          </div>
        )}
      </div>
    </div>
  );
}

function SummaryBlock({ file }) {
  const [text, setText] = useState(file.summary || "");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (file.summary) {
      setText(file.summary);
      return;
    }
    if (file.status !== "ready") return;
    setLoading(true);
    filesApi
      .summary(file.id)
      .then((res) => setText(res.summary || ""))
      .finally(() => setLoading(false));
  }, [file.id, file.status, file.summary]);

  if (loading) return <div className="summary">Loading summary...</div>;
  if (!text) return <div className="summary">No summary available yet.</div>;
  return <div className="summary">{text}</div>;
}
