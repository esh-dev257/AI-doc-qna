import { useRef, useState } from "react";
import { ACCEPT_ATTRIBUTE, files, validateUpload } from "../api.js";

export default function Uploader({ onUploaded }) {
  const ref = useRef(null);
  const [progress, setProgress] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const onFile = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const problem = validateUpload(file);
    if (problem) {
      setError(problem);
      if (ref.current) ref.current.value = "";
      return;
    }
    setBusy(true);
    setProgress(0);
    setError("");
    const fd = new FormData();
    fd.append("file", file);
    try {
      const created = await files.upload(fd, setProgress);
      onUploaded?.(created);
    } catch (err) {
      setError(err?.response?.data?.detail || err.message || "Upload failed");
    } finally {
      setBusy(false);
      if (ref.current) ref.current.value = "";
    }
  };

  return (
    <div className="uploader">
      <input ref={ref} type="file" accept={ACCEPT_ATTRIBUTE} onChange={onFile} />
      <div style={{ fontFamily: "var(--font-display)", fontWeight: 800, fontSize: 18, marginTop: 6, marginBottom: 10 }}>
        Drop a file
      </div>
      <button
        className="btn"
        onClick={() => ref.current?.click()}
        disabled={busy}
      >
        {busy ? `Uploading ${progress}%` : "Choose file →"}
      </button>
      <div style={{ fontSize: 12, color: "var(--muted)", marginTop: 12, fontFamily: "var(--font-mono)" }}>
        Max 200MB &nbsp;·&nbsp; PDF, MP3, WAV, M4A, MP4, MOV, WebM
      </div>
      {error && (
        <div style={{ marginTop: 12, display: "inline-block" }}>
          <span className="tag-red">ERROR</span>
          <div style={{ color: "var(--red-2)", marginTop: 6, fontWeight: 700 }}>{error}</div>
        </div>
      )}
    </div>
  );
}
