import { useRef, useState } from "react";
import { files } from "../api.js";

const ACCEPT = ".pdf,.mp3,.wav,.m4a,.mp4,.mov,.mkv,.webm,application/pdf,audio/*,video/*";

export default function Uploader({ onUploaded }) {
  const ref = useRef(null);
  const [progress, setProgress] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const onFile = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
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
      <input ref={ref} type="file" accept={ACCEPT} onChange={onFile} />
      <button
        className="btn"
        onClick={() => ref.current?.click()}
        disabled={busy}
      >
        {busy ? `Uploading ${progress}%` : "Upload PDF / Audio / Video"}
      </button>
      <div style={{ fontSize: 12, color: "var(--muted)", marginTop: 8 }}>
        Max 200MB. PDF, MP3/WAV/M4A, MP4/MOV/WebM supported.
      </div>
      {error && <div style={{ color: "var(--err)", marginTop: 6 }}>{error}</div>}
    </div>
  );
}
