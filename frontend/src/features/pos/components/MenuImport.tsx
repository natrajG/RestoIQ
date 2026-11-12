import { useState } from "react";
import { Alert, Button, Card, Space, Table, Tag, Typography, Upload, message } from "antd";
import { UploadOutlined } from "@ant-design/icons";
import { menuApi, type MenuImportReport } from "../api";

export function MenuImport({ outletId, onDone }: { outletId: number; onDone: () => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [report, setReport] = useState<MenuImportReport | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function run(chosen: File, commit: boolean) {
    setBusy(true);
    setError("");
    try {
      const result = await menuApi.importMenu(outletId, chosen, commit);
      if (commit) {
        message.success(`Menu imported: ${result.created} new, ${result.updated} updated`);
        setFile(null);
        setReport(null);
        onDone();
      } else {
        setReport(result);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Import failed");
      setReport(null);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card className="section-card" title="Import menu from Excel or CSV">
      <Typography.Paragraph type="secondary">
        Fill the template with your items (category, name, code, price, GST, and optional sizes like <code>Half=120;Full=200</code> and add-ons like <code>Extra cheese=20</code>), then upload it. You see a preview before anything is saved. Existing items with the same code (or name) are updated.
      </Typography.Paragraph>
      <Space wrap>
        <Button href={`/api/v1/outlets/${outletId}/menu/import-template`}>Download template</Button>
        <Upload accept=".csv,.xlsx" showUploadList={false} beforeUpload={(f) => { setFile(f); void run(f, false); return false; }}>
          <Button icon={<UploadOutlined />} loading={busy}>Choose file</Button>
        </Upload>
      </Space>
      {error && <Alert style={{ marginTop: 12 }} type="error" showIcon message={error} />}
      {report && file && (
        <div style={{ marginTop: 12 }}>
          <Alert type={report.errors ? "warning" : "success"} showIcon
            message={report.errors ? `${report.errors} row(s) need fixing. Correct the file and upload it again; nothing is saved until all rows are valid.`
              : `Ready: ${report.created} new item(s), ${report.updated} to update.`} />
          <Table size="small" style={{ marginTop: 8 }} rowKey="row" dataSource={report.rows} pagination={{ pageSize: 10, hideOnSinglePage: true }}
            columns={[
              { title: "Row", dataIndex: "row", width: 60 },
              { title: "Item", dataIndex: "name" },
              { title: "Category", dataIndex: "category" },
              { title: "Code", dataIndex: "code" },
              { title: "Price", dataIndex: "price" },
              { title: "GST", dataIndex: "gst" },
              { title: "Result", render: (_, r) => r.status === "error" ? <Tag color="red">{r.message}</Tag> : <Tag color={r.status === "new" ? "green" : "blue"}>{r.status}</Tag> },
            ]} />
          <Button type="primary" style={{ marginTop: 8 }} disabled={report.errors > 0} loading={busy} onClick={() => void run(file, true)}>
            Import {report.created + report.updated} item(s)
          </Button>
        </div>
      )}
    </Card>
  );
}
