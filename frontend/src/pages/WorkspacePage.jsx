import { useCallback, useEffect, useRef, useState } from "react";
import { files as filesApi } from "../api.js";
import { useAuth } from "../context/AuthContext.jsx";
import Uploader from "../components/Uploader.jsx";
import FileList from "../components/FileList.jsx";
import FileDetail from "../components/FileDetail.jsx";

export default function WorkspacePage() {
  const { user, logout } = useAuth();
  const [items, setItems] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
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

  return (
    <div className="layout">
      <header className="topbar">
        <div className="brand">AI Document & Multimedia Q&A</div>
        <div className="user">
          <span style={{ marginRight: 12 }}>{user?.email}</span>
          <button className="btn secondary small" onClick={logout}>
            Sign out
          </button>
        </div>
      </header>
      <aside className="sidebar">
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
          <div className="empty">Upload a PDF, audio, or video file to get started.</div>
        )}
      </main>
    </div>
  );
}
