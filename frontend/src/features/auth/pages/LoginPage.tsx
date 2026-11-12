import { Typography } from "antd";
import type { User } from "../api";
import { LoginForm } from "../components/LoginForm";

interface Props {
  onLogin: (user: User) => void;
}

export function LoginPage({ onLogin }: Props) {
  return (
    <main className="login-screen">
      <div className="login-card">
        <img className="login-logo" src="/images/logo.png" alt="RestoIQ" />
        <Typography.Title level={2}>Welcome back</Typography.Title>
        <Typography.Paragraph type="secondary">Sign in to your restaurant workspace.</Typography.Paragraph>
        <LoginForm onLogin={onLogin} />
      </div>
    </main>
  );
}
