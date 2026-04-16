import axios from "axios";

const api = axios.create({ baseURL: "/api" });

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
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
