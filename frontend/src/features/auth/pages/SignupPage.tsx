import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Alert, Button, Checkbox, Col, Form, Input, Radio, Row, Select, Typography } from "antd";
import { formatInr, usePlanPrices } from "../../../shared/api/usePlanPrices";
import { authApi, type SignupPayload, type User } from "../api";

interface Props {
  onSignup: (user: User) => void;
}

const states = [
  ["AP", "Andhra Pradesh"], ["AR", "Arunachal Pradesh"], ["AS", "Assam"], ["BR", "Bihar"], ["CG", "Chhattisgarh"],
  ["GA", "Goa"], ["GJ", "Gujarat"], ["HR", "Haryana"], ["HP", "Himachal Pradesh"], ["JH", "Jharkhand"],
  ["KA", "Karnataka"], ["KL", "Kerala"], ["MP", "Madhya Pradesh"], ["MH", "Maharashtra"], ["MN", "Manipur"],
  ["ML", "Meghalaya"], ["MZ", "Mizoram"], ["NL", "Nagaland"], ["OD", "Odisha"], ["PB", "Punjab"],
  ["RJ", "Rajasthan"], ["SK", "Sikkim"], ["TN", "Tamil Nadu"], ["TS", "Telangana"], ["TR", "Tripura"],
  ["UP", "Uttar Pradesh"], ["UT", "Uttarakhand"], ["WB", "West Bengal"], ["DL", "Delhi"], ["CH", "Chandigarh"],
  ["JK", "Jammu & Kashmir"], ["LA", "Ladakh"], ["PY", "Puducherry"], ["AN", "Andaman & Nicobar"],
  ["DN", "Dadra & Nagar Haveli and Daman & Diu"], ["LD", "Lakshadweep"],
].map(([value, label]) => ({ value, label }));

type FormValues = SignupPayload & { confirm: string; agree: boolean };

export function SignupPage({ onSignup }: Props) {
  const [params] = useSearchParams();
  const { prices } = usePlanPrices();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const initialCycle = params.get("cycle") === "monthly" ? "monthly" : "yearly";

  async function submit({ confirm: _confirm, agree: _agree, ...values }: FormValues) {
    setBusy(true);
    setError("");
    try {
      await authApi.signup({ ...values, gstin: values.gstin?.trim() || undefined });
      onSignup(await authApi.me());
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Sign-up failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="signup-screen">
      <div className="signup-card">
        <Link to="/"><img className="login-logo" style={{ margin: 0 }} src="/images/logo.png" alt="RestoIQ" /></Link>
        <Typography.Title level={2}>Start your free month</Typography.Title>
        <Typography.Paragraph type="secondary">
          Create your restaurant workspace. No payment needed for the first month.
        </Typography.Paragraph>
        {error && <Alert type="error" showIcon message={error} style={{ marginBottom: 16 }} />}
        <Form<FormValues> layout="vertical" requiredMark onFinish={(v) => void submit(v)} initialValues={{ billing_cycle: initialCycle }}>
          <div className="signup-section">RestoIQ POS · billing</div>
          <Form.Item name="billing_cycle" rules={[{ required: true }]}>
            <Radio.Group className="signup-plans" buttonStyle="solid">
              <Radio.Button value="monthly">Monthly{prices ? ` · ${formatInr(prices.monthly)}/outlet` : ""}</Radio.Button>
              <Radio.Button value="yearly">Yearly{prices ? ` · ${formatInr(prices.yearly)}/outlet${prices.monthly * 12 > prices.yearly ? ` (save ${formatInr(prices.monthly * 12 - prices.yearly)})` : ""}` : ""}</Radio.Button>
            </Radio.Group>
          </Form.Item>

          <div className="signup-section">Owner details</div>
          <Row gutter={16}>
            <Col xs={24} md={12}>
              <Form.Item label="Owner name" name="owner_name" rules={[{ required: true, min: 2 }]}>
                <Input size="large" autoComplete="name" placeholder="Full name" />
              </Form.Item>
            </Col>
            <Col xs={24} md={12}>
              <Form.Item label="Mobile number" name="mobile" rules={[{ required: true }, { pattern: /^(\+91|0)?[\s-]?[6-9]\d{9}$/, message: "Enter a valid 10-digit mobile number" }]}>
                <Input size="large" autoComplete="tel" addonBefore="+91" maxLength={13} placeholder="98765 43210" />
              </Form.Item>
            </Col>
            <Col xs={24} md={12}>
              <Form.Item label="Email" name="email" rules={[{ required: true }, { type: "email" }]}>
                <Input size="large" autoComplete="email" placeholder="you@restaurant.com" />
              </Form.Item>
            </Col>
          </Row>

          <div className="signup-section">Restaurant details</div>
          <Row gutter={16}>
            <Col xs={24} md={12}>
              <Form.Item label="Restaurant name" name="restaurant_name" rules={[{ required: true, min: 2 }]}>
                <Input size="large" placeholder="e.g. Paradise Biryani, Banjara Hills" />
              </Form.Item>
            </Col>
            <Col xs={24} md={12}>
              <Form.Item label="GSTIN (optional)" name="gstin" rules={[{ pattern: /^\d{2}[A-Za-z]{5}\d{4}[A-Za-z][A-Za-z\d]Z[A-Za-z\d]$/, message: "Enter a valid 15-character GSTIN" }]}>
                <Input size="large" maxLength={15} placeholder="36ABCDE1234F1Z5" />
              </Form.Item>
            </Col>
            <Col xs={24}>
              <Form.Item label="Address" name="address_line" rules={[{ required: true, min: 5 }]}>
                <Input size="large" autoComplete="street-address" placeholder="Building, street, area" />
              </Form.Item>
            </Col>
            <Col xs={24} md={8}>
              <Form.Item label="City" name="city" rules={[{ required: true, min: 2 }]}>
                <Input size="large" placeholder="Hyderabad" />
              </Form.Item>
            </Col>
            <Col xs={24} md={8}>
              <Form.Item label="State" name="state_code" rules={[{ required: true, message: "Select a state" }]}>
                <Select size="large" showSearch optionFilterProp="label" options={states} placeholder="Select state" />
              </Form.Item>
            </Col>
            <Col xs={24} md={8}>
              <Form.Item label="Pincode" name="pincode" rules={[{ required: true }, { pattern: /^[1-9]\d{5}$/, message: "Enter a 6-digit pincode" }]}>
                <Input size="large" maxLength={6} placeholder="500034" />
              </Form.Item>
            </Col>
          </Row>

          <div className="signup-section">Create password</div>
          <Row gutter={16}>
            <Col xs={24} md={12}>
              <Form.Item label="Password" name="password" rules={[{ required: true, min: 8, message: "At least 8 characters" }, { pattern: /^(?=.*[A-Za-z])(?=.*\d).+$/, message: "Use letters and numbers" }]}>
                <Input.Password size="large" autoComplete="new-password" />
              </Form.Item>
            </Col>
            <Col xs={24} md={12}>
              <Form.Item
                label="Confirm password"
                name="confirm"
                dependencies={["password"]}
                rules={[{ required: true }, ({ getFieldValue }) => ({
                  validator: (_, value) => (!value || getFieldValue("password") === value ? Promise.resolve() : Promise.reject(new Error("Passwords do not match"))),
                })]}
              >
                <Input.Password size="large" autoComplete="new-password" />
              </Form.Item>
            </Col>
          </Row>

          <Form.Item name="agree" valuePropName="checked" rules={[{ validator: (_, v) => (v ? Promise.resolve() : Promise.reject(new Error("Please accept the terms to continue"))) }]}>
            <Checkbox>I agree to the <a href="/legal/terms" target="_blank" rel="noreferrer">Terms</a>, <a href="/legal/privacy" target="_blank" rel="noreferrer">Privacy Policy</a> and <a href="/legal/refund" target="_blank" rel="noreferrer">Refund Policy</a></Checkbox>
          </Form.Item>
          <Button type="primary" htmlType="submit" size="large" block loading={busy}>Create account & start free month</Button>
          <Typography.Paragraph type="secondary" style={{ textAlign: "center", marginTop: 14 }}>
            Already have an account? <Link to="/">Sign in from the home page</Link>
          </Typography.Paragraph>
        </Form>
      </div>
    </main>
  );
}
