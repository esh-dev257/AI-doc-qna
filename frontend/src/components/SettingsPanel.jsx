import { useEffect, useState } from "react";

function readKey(name) {
  return localStorage.getItem(name) || "";
}

function writeKey(name, value) {
  if (value) localStorage.setItem(name, value);
  else localStorage.removeItem(name);
}

export default function SettingsPanel({ open, onClose }) {
  const [gemini, setGemini] = useState("");
  const [openai, setOpenai] = useState("");
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (open) {
      setGemini(readKey("gemini_api_key"));
      setOpenai(readKey("openai_api_key"));
      setSaved(false);
    }
  }, [open]);

  if (!open) return null;

  const save = (e) => {
    e.preventDefault();
    writeKey("gemini_api_key", gemini.trim());
    writeKey("openai_api_key", openai.trim());
    setSaved(true);
    setTimeout(() => setSaved(false), 1500);
  };

  const clear = () => {
    setGemini("");
    setOpenai("");
    writeKey("gemini_api_key", "");
    writeKey("openai_api_key", "");
    setSaved(true);
    setTimeout(() => setSaved(false), 1500);
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="road-sign road-sign-green" style={{ margin: "0 auto 18px", maxWidth: 300 }}>
          <span className="arrow">🔑</span>
          API KEYS
        </div>
        <p className="modal-lead">
          Your keys stay in <b>this browser only</b> (localStorage) and are sent
          with each request. We never persist them on the server.
        </p>

        <form onSubmit={save}>
          <label className="field">
            <span className="field-label">Gemini API Key</span>
            <input
              type="password"
              placeholder="AIza..."
              value={gemini}
              onChange={(e) => setGemini(e.target.value)}
              autoComplete="off"
            />
            <span className="field-hint">
              Get one at <a href="https://aistudio.google.com/app/apikey" target="_blank" rel="noreferrer">aistudio.google.com</a>
            </span>
          </label>

          <label className="field">
            <span className="field-label">OpenAI API Key</span>
            <input
              type="password"
              placeholder="sk-..."
              value={openai}
              onChange={(e) => setOpenai(e.target.value)}
              autoComplete="off"
            />
            <span className="field-hint">
              Get one at <a href="https://platform.openai.com/api-keys" target="_blank" rel="noreferrer">platform.openai.com</a>
            </span>
          </label>

          {saved && <div className="stamp-ok">Saved ✓</div>}

          <div className="modal-actions">
            <button type="button" className="btn secondary small" onClick={clear}>
              Clear keys
            </button>
            <div style={{ display: "flex", gap: 8 }}>
              <button type="button" className="btn secondary" onClick={onClose}>
                Close
              </button>
              <button className="btn" type="submit">
                Save
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
}
