import { useCallback, useEffect, useRef, useState } from "react";
import { files as filesApi } from "../api.js";
import { useAuth } from "../context/AuthContext.jsx";
import Uploader from "../components/Uploader.jsx";
import FileList from "../components/FileList.jsx";
import FileDetail from "../components/FileDetail.jsx";
import SettingsPanel from "../components/SettingsPanel.jsx";

function hasAnyApiKey() {
  return Boolean(
    localStorage.getItem("gemini_api_key") || localStorage.getItem("openai_api_key"),
  );
}

export default function WorkspacePage() {
  const { user, logout } = useAuth();
  const [items, setItems] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [hasKey, setHasKey] = useState(hasAnyApiKey());
  const pollRef = useRef(null);

  const refresh = useCallback(async () => {
    const list = await filesApi.list();
    setItems(list);
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  useEffect(() => {
    const anyPending = items.some((f) => f.status === "pending" || f.status === "processing");
    if (anyPending) {
      pollRef.current = setInterval(refresh, 1500);
      return () => clearInterval(pollRef.current);
    }
  }, [items, refresh]);

  const selected = items.find((f) => f.id === selectedId) || null;

  const handleUploaded = async (file) => {
    setItems((prev) => [file, ...prev.filter((f) => f.id !== file.id)]);
    setSelectedId(file.id);
  };

  const handleDelete = async (id) => {
    if (!window.confirm("Delete this file?")) return;
    await filesApi.remove(id);
    if (selectedId === id) setSelectedId(null);
    await refresh();
  };

  const openSettings = () => setSettingsOpen(true);
  const closeSettings = () => {
    setSettingsOpen(false);
    setHasKey(hasAnyApiKey());
  };

  return (
    <div className="layout">
      <header className="topbar">
        <div className="brand">
          <span className="mini-sign">AI Q&amp;A →</span>
          <span>Docs &amp; Media Playground</span>
        </div>
        <div className="user">
          <button className="btn small yellow" onClick={openSettings}>
            🔑 API Keys
          </button>
          <span className="stamp">{user?.email}</span>
          <button className="btn secondary small" onClick={logout}>
            Sign out
          </button>
        </div>
      </header>
      <aside className="sidebar">
        {!hasKey && (
          <div className="card" style={{ marginBottom: 16, padding: 16 }}>
            <span className="tag-red">HEADS UP</span>
            <p style={{ marginTop: 10, marginBottom: 10 }}>
              Add your Gemini or OpenAI key so uploads get proper summaries &amp; chat.
            </p>
            <button className="btn small" onClick={openSettings}>Add API keys →</button>
          </div>
        )}
        <Uploader onUploaded={handleUploaded} />
        <FileList
          items={items}
          selectedId={selectedId}
          onSelect={setSelectedId}
          onDelete={handleDelete}
        />
      </aside>
      <main className="main">
        {selected ? (
          <FileDetail file={selected} onRefresh={refresh} />
        ) : (
          <WelcomePanel onOpenSettings={openSettings} hasKey={hasKey} />
        )}
      </main>

      <SettingsPanel open={settingsOpen} onClose={closeSettings} />
    </div>
  );
}

function WelcomePanel({ onOpenSettings, hasKey }) {
  return (
    <div>
      <div className="polaroid" style={{ textAlign: "center", padding: "36px 28px 48px" }}>
        <span className="corner-stamp tl" />
        <span className="corner-stamp tr" />
        <span className="corner-stamp bl" />
        <span className="corner-stamp br" />

        <div style={{ display: "inline-flex", marginBottom: 20 }}>
          <div className="road-sign road-sign-green">
            <span className="arrow">←</span>
            <span>HI, FRIEND</span>
          </div>
        </div>

        <h2 style={{ fontSize: 38, lineHeight: 1.08, margin: "10px 0 10px" }}>
          Drop a file. Ask anything. Get a <em style={{ color: "var(--red)" }}>flow diagram</em>.
        </h2>
        <p style={{ color: "var(--muted)", maxWidth: 560, margin: "0 auto 22px" }}>
          Upload a PDF, MP3 / WAV / M4A, or MP4 / MOV / WebM on the left. We&apos;ll
          transcribe, summarize, draw a flow, and let you chat with it — citations and
          clickable timestamps included.
        </p>

        <div style={{ display: "flex", gap: 10, justifyContent: "center", flexWrap: "wrap" }}>
          <span className="stamp">PDF</span>
          <span className="stamp green">AUDIO</span>
          <span className="stamp yellow">VIDEO</span>
          <span className="stamp red">BYO KEY</span>
        </div>

        {!hasKey && (
          <div style={{ marginTop: 28 }}>
            <button className="btn" onClick={onOpenSettings}>
              🔑 Add your API key
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
