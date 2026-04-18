import { useState } from "react";
import { useAuth } from "../context/AuthContext.jsx";

export default function AuthPage() {
  const { login, register } = useAuth();
  const [mode, setMode] = useState("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      if (mode === "login") await login(email, password);
      else await register(email, password);
    } catch (err) {
      setError(err?.response?.data?.detail || err.message || "Something went wrong");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-page">
      <div className="auth-hero">
        <div className="hero-sign">
          <div className="road-sign road-sign-green">
            <span>PLAYGROUND</span>
            <span className="arrow">→</span>
          </div>
        </div>

        <h1>
          Chat with your <em>docs &amp; media</em>
        </h1>
        <p className="lead">
          Drop a PDF, audio, or video. Get a summary, a flow diagram, and
          clickable timestamps. Powered by <b>your own</b> API key.
        </p>

        <div className="auth-card">
          <h2>{mode === "login" ? "Welcome back" : "Create your account"}</h2>
          <form onSubmit={submit}>
            <label>
              Email
              <input
                type="email"
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </label>
            <label>
              Password
              <input
                type="password"
                autoComplete={mode === "login" ? "current-password" : "new-password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                minLength={6}
                required
              />
            </label>
            {error && <div className="error">{error}</div>}
            <div className="actions">
              <button
                type="button"
                className="btn secondary small"
                onClick={() => setMode(mode === "login" ? "register" : "login")}
              >
                {mode === "login" ? "Need an account?" : "Have an account?"}
              </button>
              <button className="btn" disabled={loading}>
                {loading ? "..." : mode === "login" ? "Sign in →" : "Create →"}
              </button>
            </div>
          </form>
        </div>

        <div style={{ marginTop: 22, display: "flex", gap: 10, justifyContent: "center", flexWrap: "wrap" }}>
          <span className="stamp">PDFs</span>
          <span className="stamp green">Audio</span>
          <span className="stamp yellow">Video</span>
          <span className="stamp red">Bring-your-own key</span>
        </div>
      </div>
    </div>
  );
}
