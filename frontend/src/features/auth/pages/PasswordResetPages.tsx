import { useState } from "react";
import { Alert, Button, Form, Input, Typography } from "antd";
import { authApi } from "../api";

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <main className="login-screen">
      <div className="login-card">
        <img className="login-logo" src="/images/logo.png" alt="RestoIQ" />
        <Typography.Title level={2}>{title}</Typography.Title>
        {children}
      </div>
    </main>
  );
}

export function ForgotPasswordPage() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [sent, setSent] = useState(false);

  async function submit({ email }: { email: string }) {
    setBusy(true);
    setError("");
    try {
      await authApi.forgotPassword(email.trim());
      setSent(true);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not send the reset link");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card title="Forgot your password?">
      {sent ? (
        <Alert type="success" showIcon message="Check your email" description="If that email is registered, we have sent a link to set a new password. It works once and expires in 60 minutes." />
      ) : (
        <>
          <Typography.Paragraph type="secondary">Enter the email you signed up with and we will send you a reset link.</Typography.Paragraph>
          {error && <Alert type="error" showIcon message={error} className="login-error" />}
          <Form layout="vertical" onFinish={(v) => void submit(v)}>
            <Form.Item label="Email" name="email" rules={[{ required: true }, { type: "email" }]}>
              <Input size="large" autoComplete="username" />
            </Form.Item>
            <Button type="primary" htmlType="submit" size="large" block loading={busy}>Send reset link</Button>
          </Form>
        </>
      )}
      <div style={{ textAlign: "center", marginTop: 16 }}><a href="/login">Back to sign in</a></div>
    </Card>
  );
}

export function ResetPasswordPage() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);
  const token = new URLSearchParams(window.location.hash.replace(/^#/, "")).get("token") ?? "";

  async function submit({ password }: { password: string }) {
    setBusy(true);
    setError("");
    try {
      await authApi.resetPassword(token, password);
      window.history.replaceState(null, "", window.location.pathname);
      setDone(true);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not reset the password");
    } finally {
      setBusy(false);
    }
  }

  if (!token) {
    return <Card title="Reset password"><Alert type="error" showIcon message="This reset link is incomplete" description={<a href="/forgot-password">Request a new link</a>} /></Card>;
  }
  return (
    <Card title="Choose a new password">
      {done ? (
        <Alert type="success" showIcon message="Password updated" description={<a href="/login">Sign in with your new password</a>} />
      ) : (
        <>
          {error && <Alert type="error" showIcon message={error} description={<a href="/forgot-password">Request a new link</a>} className="login-error" />}
          <Form layout="vertical" onFinish={(v) => void submit(v)}>
            <Form.Item label="New password" name="password" rules={[{ required: true, min: 8, message: "At least 8 characters" }, { pattern: /^(?=.*[A-Za-z])(?=.*\d).+$/, message: "Use letters and numbers" }]}>
              <Input.Password size="large" autoComplete="new-password" />
            </Form.Item>
            <Form.Item label="Confirm password" name="confirm" dependencies={["password"]}
              rules={[{ required: true }, ({ getFieldValue }) => ({ validator: (_, value) => (!value || getFieldValue("password") === value ? Promise.resolve() : Promise.reject(new Error("Passwords do not match"))) })]}>
              <Input.Password size="large" autoComplete="new-password" />
            </Form.Item>
            <Button type="primary" htmlType="submit" size="large" block loading={busy}>Update password</Button>
          </Form>
        </>
      )}
    </Card>
  );
}
