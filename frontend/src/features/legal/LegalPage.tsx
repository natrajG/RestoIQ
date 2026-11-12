import type { ReactNode } from "react";
import { Link, Navigate, useParams } from "react-router-dom";
import { Typography } from "antd";
import { formatInr, usePlanPrices } from "../../shared/api/usePlanPrices";

const { Title, Paragraph } = Typography;

// Fill these in before launch.
const COMPANY = "[Your legal business name]";
const SUPPORT_EMAIL = "[support email]";
const UPDATED = "10 November 2026";

const Section = ({ title, children }: { title: string; children: ReactNode }) => (
  <>
    <Title level={4}>{title}</Title>
    {children}
  </>
);

const PlanPrice = () => {
  const { prices } = usePlanPrices();
  return <>{prices ? `${formatInr(prices.monthly)} per outlet per month or ${formatInr(prices.yearly)} per outlet per year` : "the price shown on our pricing page"}</>;
};

const DOCS: Record<string, { title: string; body: ReactNode }> = {
  terms: {
    title: "Terms of Service",
    body: (
      <>
        <Section title="1. The service">
          <Paragraph>RestoIQ is a subscription point-of-sale and restaurant operations service provided by {COMPANY} ("we"). By creating an account you agree to these terms on behalf of your restaurant.</Paragraph>
        </Section>
        <Section title="2. Plan, price and free month">
          <Paragraph>The plan costs <PlanPrice />, plus GST. The first month is free. Prices may change for future periods; we will tell you before a change takes effect.</Paragraph>
        </Section>
        <Section title="3. Payment and renewal">
          <Paragraph>Payments are made online through Razorpay for one period (month or year) at a time. We do not store your card or UPI details. Your plan does not renew automatically: renew before the period ends. After the period ends you have 3 days of continued access, after which the account is locked until you pay. Your data is kept and access returns once payment is received.</Paragraph>
        </Section>
        <Section title="4. Your data">
          <Paragraph>Your menu, orders, bills and reports belong to you. You are responsible for the accuracy of the data you enter, including GST settings and rates. RestoIQ is a billing tool; please confirm tax treatment with your accountant.</Paragraph>
        </Section>
        <Section title="5. Acceptable use">
          <Paragraph>Do not misuse the service, attempt to access other restaurants' data, or use it for unlawful purposes. You are responsible for your staff's use of their accounts and for keeping passwords safe.</Paragraph>
        </Section>
        <Section title="6. Cameras and monitoring">
          <Paragraph>Table monitoring uses cameras you connect. You are responsible for lawful use, including notices to staff and customers where required. Detection is automated and approximate; do not rely on it as the only basis for important decisions.</Paragraph>
        </Section>
        <Section title="7. Availability and liability">
          <Paragraph>We work to keep the service available, and the POS can keep taking orders when the internet drops, but we do not guarantee uninterrupted service. To the extent permitted by law, our total liability is limited to the fees you paid in the 3 months before the claim, and we are not liable for indirect or lost-profit losses.</Paragraph>
        </Section>
        <Section title="8. Ending the service">
          <Paragraph>You can stop using the service at any time. We may suspend accounts that breach these terms. On request we will provide an export of your data.</Paragraph>
        </Section>
        <Section title="9. Law and contact">
          <Paragraph>These terms are governed by the laws of India. Questions: {SUPPORT_EMAIL}.</Paragraph>
        </Section>
      </>
    ),
  },
  privacy: {
    title: "Privacy Policy",
    body: (
      <>
        <Section title="What we collect">
          <Paragraph>Account details (owner name, mobile, email, restaurant name, address, optional GSTIN); staff accounts you create; your menu, orders, bills and payments entries; and subscription payment records. Customer details such as a name, phone and address are stored only when you enter them for takeaway or delivery orders.</Paragraph>
        </Section>
        <Section title="Camera data">
          <Paragraph>If you connect cameras, frames are analysed to detect people and table occupancy. We do not identify people by face. Recordings are only kept if you switch recording on for a camera, and are deleted after the retention period.</Paragraph>
        </Section>
        <Section title="How we use it">
          <Paragraph>To run the service, show your reports, bill your subscription, provide support and keep the platform secure. We do not sell your data or use it for advertising.</Paragraph>
        </Section>
        <Section title="Who else sees it">
          <Paragraph>Razorpay processes subscription payments and receives the details needed for that. Our hosting and email providers process data on our behalf. We disclose data when required by law.</Paragraph>
        </Section>
        <Section title="Security and isolation">
          <Paragraph>Each restaurant's data is isolated from others. Passwords are stored hashed. Connections use HTTPS.</Paragraph>
        </Section>
        <Section title="Your choices">
          <Paragraph>You can ask us to correct, export or delete your data by writing to {SUPPORT_EMAIL}. Some records, such as tax invoices, may need to be kept for legal reasons.</Paragraph>
        </Section>
      </>
    ),
  },
  refund: {
    title: "Refund & Cancellation Policy",
    body: (
      <>
        <Section title="Free month">
          <Paragraph>Your first month is free and needs no payment. You can stop at any time during it.</Paragraph>
        </Section>
        <Section title="Monthly plan">
          <Paragraph>Monthly payments are non-refundable once the period has started, because the service is available to you straight away. You can simply not renew.</Paragraph>
        </Section>
        <Section title="Yearly plan">
          <Paragraph>If you are not satisfied, write to us within 7 days of paying and we will refund the yearly payment in full. After 7 days, yearly payments are non-refundable.</Paragraph>
        </Section>
        <Section title="Duplicate or failed payments">
          <Paragraph>If you were charged twice for the same invoice, or money was deducted but your plan was not activated, we will refund the extra amount or activate your plan. Refunds go back to the original payment method within 5–7 working days after we approve them.</Paragraph>
        </Section>
        <Section title="Cancelling">
          <Paragraph>There is nothing to cancel: plans do not auto-renew. Your access simply ends at the end of the paid period (plus a 3-day grace period).</Paragraph>
        </Section>
        <Paragraph>Contact: {SUPPORT_EMAIL}.</Paragraph>
      </>
    ),
  },
};

export function LegalPage() {
  const { doc } = useParams();
  const page = doc ? DOCS[doc] : undefined;
  if (!page) return <Navigate to="/" replace />;
  return (
    <div style={{ maxWidth: 760, margin: "0 auto", padding: "32px 20px 64px" }}>
      <Link to="/">← RestoIQ</Link>
      <Title>{page.title}</Title>
      <Paragraph type="secondary">Last updated {UPDATED}</Paragraph>
      {page.body}
    </div>
  );
}

export function LegalLinks() {
  return (
    <span className="legal-links">
      <Link to="/legal/terms">Terms</Link> · <Link to="/legal/privacy">Privacy</Link> · <Link to="/legal/refund">Refunds</Link>
    </span>
  );
}
