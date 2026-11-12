import { useState } from "react";
import { Alert, Button, Form, Input } from "antd";
import type { User } from "../api";
import { authApi } from "../api";

interface Props {
  onLogin: (user: User) => void;
}

export function LoginForm({ onLogin }: Props) {
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(values: { email: string; password: string }) {
    setBusy(true);
    setError("");
    try {
      await authApi.login(values.email, values.password);
      onLogin(await authApi.me());
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Sign-in failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      {error && <Alert type="error" showIcon message={error} className="login-error" />}
      <Form layout="vertical" onFinish={(values) => void submit(values)}>
        <Form.Item label="Email" name="email" rules={[{ required: true }, { type: "email" }]}>
          <Input size="large" autoComplete="username" placeholder="you@restaurant.com" />
        </Form.Item>
        <Form.Item label="Password" name="password" rules={[{ required: true }]}>
          <Input.Password size="large" autoComplete="current-password" placeholder="Your password" />
        </Form.Item>
        <Button type="primary" htmlType="submit" size="large" block loading={busy}>Sign in</Button>
        <div style={{ textAlign: "center", marginTop: 12 }}><a href="/forgot-password">Forgot password?</a></div>
      </Form>
    </>
  );
}
