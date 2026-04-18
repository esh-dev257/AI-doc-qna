import { useEffect, useRef, useState } from "react";
import { chat as chatApi, files as filesApi } from "../api.js";
import MediaPlayer from "./MediaPlayer.jsx";
import ChatPanel from "./ChatPanel.jsx";
import Timestamps from "./Timestamps.jsx";
import MermaidDiagram from "./MermaidDiagram.jsx";

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
          <h3 style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12 }}>
            <span style={{ wordBreak: "break-all" }}>{file.filename}</span>
            <span className={`badge ${file.status}`}>{file.status}</span>
          </h3>
          {file.error && (
            <div style={{ marginTop: 6 }}>
              <span className="tag-red">ERROR</span>
              <div style={{ color: "var(--red-2)", fontWeight: 700, marginTop: 4 }}>{file.error}</div>
            </div>
          )}

          {file.kind !== "pdf" && blobUrl && (
            <MediaPlayer ref={mediaRef} kind={file.kind} src={blobUrl} />
          )}
          {file.kind === "pdf" && file.status === "ready" && (
            <div style={{ marginTop: 14 }}>
              <a
                className="btn secondary small"
                href={`/api/files/${file.id}/media`}
                target="_blank"
                rel="noopener noreferrer"
              >
                Open PDF →
              </a>
            </div>
          )}
        </div>
        <div className="card" style={{ marginTop: 18 }}>
          <h3><span className="tag-red">SUMMARY</span></h3>
          <SummaryBlock file={file} />
        </div>
        {(file.kind === "audio" || file.kind === "video") && file.status === "ready" && (
          <div className="card" style={{ marginTop: 18 }}>
            <h3><span className="tag-red">TIMESTAMPS</span></h3>
            <Timestamps fileId={file.id} onPlay={playAt} />
          </div>
        )}
      </div>
      <div className="card">
        <h3><span className="tag-red">CHAT</span></h3>
        {file.status === "ready" ? (
          <ChatPanel file={file} onPlay={playAt} />
        ) : (
          <div className="empty">
            File is <b>{file.status}</b>.{" "}
            {file.status !== "failed" && (
              <button className="btn small" onClick={onRefresh} style={{ marginLeft: 8 }}>
                Refresh
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function SummaryBlock({ file }) {
  const [text, setText] = useState("");
  const [diagram, setDiagram] = useState("");
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [diagramLoading, setDiagramLoading] = useState(false);

  // Reset whenever the selected file changes so we never flash the previous file's content.
  useEffect(() => {
    setText("");
    setDiagram("");
    setSummaryLoading(false);
    setDiagramLoading(false);
  }, [file.id]);

  // Fetch summary + diagram once the file is ready. Summary first (fast),
  // diagram lazily after (slower, gated on the summary being present).
  useEffect(() => {
    if (file.status !== "ready") return undefined;
    let cancelled = false;

    setSummaryLoading(true);
    filesApi
      .summary(file.id)
      .then((res) => {
        if (cancelled) return;
        setText(res.summary || "");
        if (res.diagram) setDiagram(res.diagram);
      })
      .catch(() => {})
      .finally(() => {
        if (!cancelled) setSummaryLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [file.id, file.status]);

  // Kick off diagram generation once we have a summary and no cached diagram.
  useEffect(() => {
    if (file.status !== "ready") return undefined;
    if (!text) return undefined;
    if (diagram) return undefined;
    let cancelled = false;

    setDiagramLoading(true);
    filesApi
      .diagram(file.id)
      .then((res) => {
        if (cancelled) return;
        setDiagram(res.diagram || "");
      })
      .catch(() => {})
      .finally(() => {
        if (!cancelled) setDiagramLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [file.id, file.status, text, diagram]);

  if (file.status === "pending" || file.status === "processing") {
    return (
      <div className="summary-loading">
        <span className="spinner" /> Generating summary — this takes ~10–30s…
      </div>
    );
  }
  if (file.status === "failed") {
    return <div className="summary" style={{ color: "var(--red-2)" }}>Processing failed. Try re-uploading.</div>;
  }
  if (summaryLoading) {
    return (
      <div className="summary-loading">
        <span className="spinner" /> Loading summary…
      </div>
    );
  }
  if (!text) return <div className="summary">No summary available yet.</div>;

  return (
    <>
      <div className="summary">{text}</div>
      {diagramLoading && !diagram && (
        <div className="summary-loading" style={{ marginTop: 14 }}>
          <span className="spinner" /> Drawing flow diagram…
        </div>
      )}
      {diagram && (
        <div className="diagram-wrap">
          <MermaidDiagram source={diagram} />
        </div>
      )}
    </>
  );
}
