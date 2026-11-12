import { useEffect, useState } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { Spin } from "antd";
import { authApi, type User } from "../features/auth/api";
import { ApiError } from "../shared/api/client";
import { LoginPage } from "../features/auth/pages/LoginPage";
import { LandingPage } from "../features/landing/pages/LandingPage";
import { SignupPage } from "../features/auth/pages/SignupPage";
import { LegalPage } from "../features/legal/LegalPage";
import { ForgotPasswordPage, ResetPasswordPage } from "../features/auth/pages/PasswordResetPages";
import { AppShell } from "./layout/AppShell";

export function App() {
  const [user, setUser] = useState<User | null>(null);
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    authApi.me().then(setUser).catch((error: unknown) => {
      if (!(error instanceof ApiError) || error.status !== 401) console.error(error);
      setUser(null);
    }).finally(() => setChecking(false));
  }, []);

  if (checking) return <div className="boot-screen"><Spin size="large" /></div>;

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/forgot-password" element={<ForgotPasswordPage />} />
        <Route path="/reset-password" element={<ResetPasswordPage />} />
        <Route path="/legal/:doc" element={<LegalPage />} />
        <Route path="/login" element={user ? <Navigate to="/" replace /> : <LoginPage onLogin={setUser} />} />
        <Route path="/signup" element={user ? <Navigate to="/" replace /> : <SignupPage onSignup={setUser} />} />
        {!user && <Route path="/" element={<LandingPage onLogin={setUser} />} />}
        <Route path="/*" element={user ? <AppShell user={user} onLogout={() => setUser(null)} /> : <Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
