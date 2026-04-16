import { useState } from "react";
import { chat as chatApi } from "../api.js";
import { formatTime } from "./FileList.jsx";

export default function ChatPanel({ file, onPlay }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [stream, setStream] = useState(true);

  const submit = async (e) => {
    e.preventDefault();
    if (!input.trim() || busy) return;
    const q = input.trim();
    setInput("");
    setMessages((m) => [...m, { role: "user", text: q }]);
    setBusy(true);

    try {
      if (stream) {
        let botMsg = { role: "bot", text: "", citations: [] };
        setMessages((m) => [...m, botMsg]);
        for await (const evt of chatApi.stream(file.id, q)) {
          if (evt.event === "citations") {
            botMsg = { ...botMsg, citations: evt.data || [] };
            setMessages((m) => {
              const copy = [...m];
              copy[copy.length - 1] = botMsg;
              return copy;
            });
          } else if (evt.event === "token") {
            botMsg = { ...botMsg, text: botMsg.text + (evt.data || "") };
            setMessages((m) => {
              const copy = [...m];
              copy[copy.length - 1] = botMsg;
              return copy;
            });
          }
        }
      } else {
        const res = await chatApi.ask(file.id, q);
        setMessages((m) => [...m, { role: "bot", text: res.answer, citations: res.citations }]);
      }
    } catch (err) {
      setMessages((m) => [...m, { role: "bot", text: `Error: ${err.message}` }]);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="chat">
      <div className="messages">
        {messages.length === 0 && (
          <div className="empty">Ask a question about this file.</div>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`msg ${m.role}`}>
            {m.text || <em style={{ opacity: 0.6 }}>thinking...</em>}
            {m.citations && m.citations.length > 0 && (
              <div className="citations">
                {m.citations.map((c, j) => (
                  <button
                    key={j}
                    className="btn secondary small"
                    onClick={() => c.start_time != null && onPlay?.(c.start_time)}
                    title={c.text}
                    disabled={c.start_time == null}
                  >
                    chunk {c.chunk_index}
                    {c.start_time != null ? ` · ▶ ${formatTime(c.start_time)}` : ""}
                  </button>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
      <form onSubmit={submit}>
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask something..."
          disabled={busy}
        />
        <button className="btn" disabled={busy}>
          Send
        </button>
      </form>
      <label style={{ fontSize: 12, color: "var(--muted)" }}>
        <input
          type="checkbox"
          checked={stream}
          onChange={(e) => setStream(e.target.checked)}
        />{" "}
        stream response
      </label>
    </div>
  );
}
