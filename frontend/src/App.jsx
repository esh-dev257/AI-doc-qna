import { Routes, Route, Navigate } from "react-router-dom";
import { useAuth } from "./context/AuthContext.jsx";
import AuthPage from "./pages/AuthPage.jsx";
import WorkspacePage from "./pages/WorkspacePage.jsx";

export default function App() {
  const { user, loading } = useAuth();
  if (loading) return <div className="empty">Loading...</div>;
  return (
    <Routes>
      <Route
        path="/"
        element={user ? <WorkspacePage /> : <Navigate to="/login" replace />}
      />
      <Route
        path="/login"
        element={user ? <Navigate to="/" replace /> : <AuthPage />}
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
