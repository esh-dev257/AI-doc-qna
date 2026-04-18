import axios from "axios";

export const ALLOWED_EXTENSIONS = {
  pdf: ["pdf"],
  audio: ["mp3", "wav", "m4a"],
  video: ["mp4", "mov", "webm"],
};
export const ALLOWED_EXT_FLAT = Object.values(ALLOWED_EXTENSIONS).flat();
export const ACCEPT_ATTRIBUTE = [
  ".pdf", ".mp3", ".wav", ".m4a", ".mp4", ".mov", ".webm",
  "application/pdf", "audio/mpeg", "audio/wav", "audio/x-m4a",
  "video/mp4", "video/quicktime", "video/webm",
].join(",");

export function validateUpload(file, maxMb = 200) {
  if (!file) return "Please pick a file.";
  const name = (file.name || "").toLowerCase();
  const dot = name.lastIndexOf(".");
  const ext = dot >= 0 ? name.slice(dot + 1) : "";
  if (!ALLOWED_EXT_FLAT.includes(ext)) {
    return `Only ${ALLOWED_EXT_FLAT.join(", ").toUpperCase()} files are allowed.`;
  }
  if (file.size === 0) return "File is empty.";
  if (file.size > maxMb * 1024 * 1024) return `File too large (max ${maxMb} MB).`;
  return null;
}

export function apiKeyHeaders() {
  const out = {};
  const g = localStorage.getItem("gemini_api_key");
  const o = localStorage.getItem("openai_api_key");
  if (g) out["X-Gemini-Api-Key"] = g;
  if (o) out["X-OpenAI-Api-Key"] = o;
  return out;
}

const api = axios.create({ baseURL: "/api" });

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  const extra = apiKeyHeaders();
  for (const [k, v] of Object.entries(extra)) config.headers[k] = v;
  return config;
});

export const auth = {
  register: (email, password) => api.post("/auth/register", { email, password }).then((r) => r.data),
  login: (email, password) => api.post("/auth/login", { email, password }).then((r) => r.data),
  me: () => api.get("/auth/me").then((r) => r.data),
};

export const files = {
  list: () => api.get("/files").then((r) => r.data),
  get: (id) => api.get(`/files/${id}`).then((r) => r.data),
  upload: (formData, onProgress) =>
    api
      .post("/files", formData, {
        headers: { "Content-Type": "multipart/form-data" },
        onUploadProgress: (e) => {
          if (onProgress && e.total) onProgress(Math.round((e.loaded / e.total) * 100));
        },
      })
      .then((r) => r.data),
  summary: (id) => api.get(`/files/${id}/summary`).then((r) => r.data),
  diagram: (id) => api.post(`/files/${id}/summary/diagram`).then((r) => r.data),
  mediaUrl: (id) => {
    const token = localStorage.getItem("token");
    return `/api/files/${id}/media?t=${encodeURIComponent(token || "")}`;
  },
  remove: (id) => api.delete(`/files/${id}`).then((r) => r.data),
};

export const chat = {
  ask: (file_id, question, top_k = 4) =>
    api.post("/chat", { file_id, question, top_k }).then((r) => r.data),
  timestamps: (file_id, topic, top_k = 5) =>
    api.post("/chat/timestamps", { file_id, topic, top_k }).then((r) => r.data),
  stream: async function* (file_id, question, top_k = 4) {
    const token = localStorage.getItem("token");
    const resp = await fetch("/api/chat/stream", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
        ...apiKeyHeaders(),
      },
      body: JSON.stringify({ file_id, question, top_k }),
    });
    if (!resp.ok || !resp.body) throw new Error("stream failed");
    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let idx;
      while ((idx = buffer.indexOf("\n\n")) !== -1) {
        const block = buffer.slice(0, idx);
        buffer = buffer.slice(idx + 2);
        const event = /^event:\s*(.+)$/m.exec(block)?.[1];
        const data = /^data:\s*([\s\S]+)$/m.exec(block)?.[1];
        if (!event) continue;
        let parsed = null;
        try {
          parsed = data ? JSON.parse(data) : null;
        } catch {
          parsed = data;
        }
        yield { event, data: parsed };
      }
    }
  },
};

export default api;
