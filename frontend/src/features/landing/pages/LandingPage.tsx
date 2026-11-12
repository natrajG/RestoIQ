import { useState } from "react";
import { LegalLinks } from "../../legal/LegalPage";
import { Link, useNavigate } from "react-router-dom";
import { Button, Card, Col, Modal, Row, Tag, Typography } from "antd";
import {
  AimOutlined,
  CheckCircleOutlined,
  LineChartOutlined,
  TeamOutlined,
  ShoppingCartOutlined,
  FileTextOutlined,
  WalletOutlined,
} from "@ant-design/icons";
import type { User } from "../../auth/api";
import { LoginForm } from "../../auth/components/LoginForm";
import { formatInr, usePlanPrices } from "../../../shared/api/usePlanPrices";
import { DemoPlayer } from "../components/DemoPlayer";

const plan = {
  name: "RestoIQ POS",
  tag: "One plan, everything included",
  features: [
    "Complete POS: menu, GST billing, KOT, discounts, payments, refunds",
    "Live CCTV table monitoring & delay alerts (included)",
    "Role-based staff tasking",
    "Revenue analytics and weekly/monthly reports",
    "Day, meal-window & festival menu recommendations",
  ],
};

const features = [
  { icon: <ShoppingCartOutlined />, title: "Fast order & KOT", text: "Dine-in orders by table, notes, add items later, cancel with a reason, and a live kitchen screen." },
  { icon: <FileTextOutlined />, title: "GST billing", text: "Item-wise GST, CGST/SGST split, discounts, service charge, round-off, consecutive bill numbers and a GST report." },
  { icon: <WalletOutlined />, title: "Payments & refunds", text: "Cash, UPI and card with split payments and refunds recorded safely against each bill." },
  { icon: <AimOutlined />, title: "Live table monitoring", text: "Cameras and AI track seated, dining, bill-requested and needs-cleaning tables." },
  { icon: <TeamOutlined />, title: "Staff in sync", text: "Role-based tasks for kitchen, waiters, cashier and cleaners, with delay alerts." },
  { icon: <LineChartOutlined />, title: "Reports & ideas", text: "Daily sales, weekly and monthly reports, and menu suggestions by day, meal window and festival." },
];

interface Props {
  onLogin: (user: User) => void;
}

export function LandingPage({ onLogin }: Props) {
  const [loginOpen, setLoginOpen] = useState(false);
  const navigate = useNavigate();
  const { prices } = usePlanPrices();
  const inr = formatInr;
  const saving = prices ? prices.monthly * 12 - prices.yearly : 0;

  return (
    <div className="landing">
      <Modal open={loginOpen} onCancel={() => setLoginOpen(false)} footer={null} destroyOnClose title="Sign in to your restaurant workspace">
        <LoginForm onLogin={onLogin} />
        <div className="landing-modal-foot">New to RestoIQ? <Link to="/signup">Start your free month</Link></div>
      </Modal>

      <header className="landing-nav">
        <a href="/" aria-label="RestoIQ home" onClick={(e) => { e.preventDefault(); window.scrollTo({ top: 0, behavior: "smooth" }); }}>
          <img className="landing-logo" src="/images/logo.png" alt="RestoIQ - Restaurant Operations & Revenue Intelligence" style={{ cursor: "pointer" }} />
        </a>
        <nav>
          <a href="#demo">Demo</a>
          <a href="#plans">Plans</a>
          <Button onClick={() => setLoginOpen(true)}>Sign in</Button>
          <Button type="primary" onClick={() => navigate("/signup")}>Start free trial</Button>
        </nav>
      </header>

      <div className="landing-first">
      <section className="landing-hero">
        <div className="landing-hero-inner">
          <span className="landing-pill">Complete restaurant POS · GST billing · First month free</span>
          <Typography.Title>Billing, kitchen and GST in one POS. <em>Plus live table monitoring.</em></Typography.Title>
          <Typography.Paragraph>
            Take orders, send KOTs to the kitchen, print GST bills and collect payments from any device. Then add live camera table monitoring, staff tasks and sales reports, all in one ₹499 a month plan.
          </Typography.Paragraph>
          <Button type="primary" size="large" onClick={() => navigate("/signup")}>Start your free month</Button>{" "}
          <a href="#demo"><Button size="large" ghost>Watch the demo</Button></a>
          <div className="landing-hero-stats">
            <div><b>1</b><span>simple plan</span></div>
            <div><b>GST</b><span>ready billing</span></div>
            <div><b>KOT</b><span>kitchen screen</span></div>
            <div><b>Live</b><span>table monitoring</span></div>
          </div>
        </div>
      </section>

      <section id="features" className="landing-section">
        <Typography.Title level={2}>Everything your restaurant needs</Typography.Title>
        <Typography.Paragraph type="secondary">A complete POS, with monitoring and insights built in.</Typography.Paragraph>
        <div className="landing-features">
          {features.map((f) => (
            <div key={f.title} className="landing-feature">
              {f.icon}
              <Typography.Title level={4}>{f.title}</Typography.Title>
              <p>{f.text}</p>
            </div>
          ))}
        </div>
      </section>

      </div>

      <section id="demo" className="landing-band">
        <div className="landing-section">
          <Typography.Title level={2}>See it end to end</Typography.Title>
          <Typography.Paragraph type="secondary">
            From menu setup to order, kitchen, GST bill and payment, then table monitoring and reports. Sample data, no sign-in needed.
          </Typography.Paragraph>
          <DemoPlayer />
          <Typography.Paragraph type="secondary" className="landing-note">
            Recommendations use day of week, meal window and festivals. Camera detections are operational assistance and are validated against your restaurant footage.
          </Typography.Paragraph>
        </div>
      </section>

      <section className="landing-split">
        <div className="landing-split-img" role="img" aria-label="Plated dish on a restaurant table" />
        <div className="landing-split-text">
          <Typography.Title level={2}>Faster service, fewer mistakes</Typography.Title>
          <Typography.Paragraph type="secondary">
            Accurate bills and a connected kitchen and floor mean happier guests and more covers per evening.
          </Typography.Paragraph>
          <ul>
            <li><CheckCircleOutlined />Orders reach the kitchen instantly</li>
            <li><CheckCircleOutlined />Correct GST on every bill</li>
            <li><CheckCircleOutlined />Tables cleaned and ready sooner, with problems visible before guests complain</li>
          </ul>
        </div>
      </section>

      <section id="plans" className="landing-section">
        <Typography.Title level={2}>One simple plan</Typography.Title>
        <Typography.Paragraph className="landing-sub">
          Your first month is free. Then billed per outlet, excluding GST. {saving > 0 && `Pay yearly and save ${inr(saving)}.`}
        </Typography.Paragraph>
        <Row gutter={[20, 20]} justify="center">
          {prices && [{ label: "Monthly", price: prices.monthly, unit: "/ outlet / month", cycle: "monthly", featured: false },
            { label: "Yearly", price: prices.yearly, unit: "/ outlet / year", cycle: "yearly", featured: true }].map((o) => (
            <Col xs={24} md={10} key={o.cycle}>
              <Card className={o.featured ? "landing-plan landing-plan-featured" : "landing-plan"} bordered={false}>
                <Tag color={o.featured ? "orange" : "geekblue"}>{o.featured && saving > 0 ? `Best value · save ${inr(saving)}` : plan.tag}</Tag>
                <Typography.Title level={3}>{plan.name} · {o.label}</Typography.Title>
                <div className="landing-price"><b>{inr(o.price)}</b><span>{o.unit} after trial</span></div>
                <ul className="landing-plan-list">
                  {plan.features.map((f) => (
                    <li key={f}>{f}</li>
                  ))}
                </ul>
                <Button type="primary" size="large" block onClick={() => navigate(`/signup?cycle=${o.cycle}`)}>Start your free month</Button>
              </Card>
            </Col>
          ))}
        </Row>
      </section>

      <footer className="landing-footer"><img src="/images/logo.png" alt="RestoIQ" /><div>© RestoIQ · Restaurant Operations &amp; Revenue Intelligence</div><div style={{ marginTop: 8 }}><LegalLinks /></div></footer>
    </div>
  );
}
