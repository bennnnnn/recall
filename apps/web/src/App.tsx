import { Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider, useAuth } from "@/auth/AuthContext";
import { Login } from "@/components/Login";
import { ChatList } from "@/components/ChatList";
import { ChatView } from "@/components/ChatView";
import type { ReactNode } from "react";

function Protected({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="loading-screen">Loading…</div>;
  if (!user) return <Navigate to="/" replace />;
  return <>{children}</>;
}

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/" element={<Login />} />
        <Route
          path="/chats"
          element={
            <Protected>
              <ChatList />
            </Protected>
          }
        />
        <Route
          path="/chats/:chatId"
          element={
            <Protected>
              <ChatView />
            </Protected>
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AuthProvider>
  );
}
