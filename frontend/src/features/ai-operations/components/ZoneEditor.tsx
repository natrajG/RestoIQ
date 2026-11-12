import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Alert, Button, Empty, Modal, Select, Space, Tag, Typography, Upload, message } from "antd";
import { useMemo, useRef, useState } from "react";
import type { DiningTable } from "../../pos/api";
import { operationsApi, type Camera, type CameraRegion } from "../api";

type Point = [number, number];
const COLORS = ["#ff6a00", "#1677ff", "#52c41a", "#eb2f96", "#722ed1", "#13c2c2", "#faad14", "#f5222d"];

interface Props { outletId: number; camera: Camera; tables: DiningTable[]; open: boolean; onClose: () => void }

export function ZoneEditor({ outletId, camera, tables, open, onClose }: Props) {
  const queryClient = useQueryClient();
  const box = useRef<HTMLDivElement>(null);
  const [zones, setZones] = useState<CameraRegion[]>(camera.regions ?? []);
  const [tableId, setTableId] = useState<number>();
  const [points, setPoints] = useState<Point[]>([]);
  const [imageVersion, setImageVersion] = useState(Date.now());
  const [hasImage, setHasImage] = useState(!!camera.has_reference_image);
  const free = useMemo(() => tables.filter((t) => !zones.some((z) => z.table_id === t.id)), [tables, zones]);
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["cameras", outletId] });

  const save = useMutation({
    mutationFn: () => operationsApi.saveRegions(outletId, camera.id, zones),
    onSuccess: () => { message.success("Zones saved"); void refresh(); onClose(); },
    onError: (e: Error) => message.error(e.message),
  });

  function addPoint(event: React.MouseEvent) {
    if (!tableId || !box.current) return;
    const rect = box.current.getBoundingClientRect();
    const x = Math.min(1, Math.max(0, (event.clientX - rect.left) / rect.width));
    const y = Math.min(1, Math.max(0, (event.clientY - rect.top) / rect.height));
    setPoints((p) => (p.length < 32 ? [...p, [Number(x.toFixed(4)), Number(y.toFixed(4))]] : p));
  }

  function finishZone() {
    const table = tables.find((t) => t.id === tableId);
    if (!table || points.length < 3) return;
    setZones((z) => [...z, { table_id: table.id, name: table.name, polygon: points }]);
    setPoints([]);
    setTableId(undefined);
  }

  const svgPoints = (poly: Point[]) => poly.map((p) => `${p[0]},${p[1]}`).join(" ");

  return (
    <Modal open={open} onCancel={onClose} width={900} destroyOnClose title={`Table zones: ${camera.name}`}
      okText="Save zones" onOk={() => save.mutate()} confirmLoading={save.isPending}>
      <Alert type="info" showIcon style={{ marginBottom: 12 }}
        message="Upload a screenshot of this camera's view, then outline each table"
        description="Pick a table, click the corners of its area on the image (3 or more points, not crossing), then press Finish zone. Zones should cover the table and the chairs around it." />
      <Space wrap style={{ marginBottom: 12 }}>
        <Upload accept="image/png,image/jpeg" showUploadList={false}
          customRequest={({ file, onSuccess, onError }) => {
            operationsApi.uploadReferenceImage(outletId, camera.id, file as File)
              .then(() => { setHasImage(true); setImageVersion(Date.now()); void refresh(); onSuccess?.({}); })
              .catch((e: Error) => { message.error(e.message); onError?.(e); });
          }}>
          <Button>{hasImage ? "Replace screenshot" : "Upload camera screenshot"}</Button>
        </Upload>
        <Select style={{ width: 200 }} placeholder="Table to outline" value={tableId} disabled={!hasImage}
          onChange={(v) => { setTableId(v); setPoints([]); }}
          options={free.map((t) => ({ value: t.id, label: t.name }))} />
        <Button type="primary" disabled={points.length < 3} onClick={finishZone}>Finish zone</Button>
        <Button disabled={!points.length} onClick={() => setPoints((p) => p.slice(0, -1))}>Undo point</Button>
        <Button disabled={!points.length} onClick={() => setPoints([])}>Clear</Button>
      </Space>
      {!tables.length && <Alert type="warning" showIcon style={{ marginBottom: 12 }} message="Add tables first (Tables & floor)" />}
      {hasImage ? (
        <div ref={box} onClick={addPoint} style={{ position: "relative", cursor: tableId ? "crosshair" : "default", lineHeight: 0, userSelect: "none" }}>
          <img src={`/api/v1/outlets/${outletId}/cameras/${camera.id}/reference-image?v=${imageVersion}`} alt="Camera view" style={{ width: "100%", display: "block", borderRadius: 8 }} draggable={false} />
          <svg viewBox="0 0 1 1" preserveAspectRatio="none" style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }}>
            {zones.map((z, i) => (
              <polygon key={z.table_id} points={svgPoints(z.polygon)} fill={COLORS[i % COLORS.length]} fillOpacity={0.3}
                stroke={COLORS[i % COLORS.length]} strokeWidth={2} vectorEffect="non-scaling-stroke" />
            ))}
            {points.length > 1 && <polyline points={svgPoints(points)} fill="none" stroke="#fff" strokeWidth={2} vectorEffect="non-scaling-stroke" />}
          </svg>
          {zones.map((z) => {
            const cx = z.polygon.reduce((a, p) => a + p[0], 0) / z.polygon.length;
            const cy = z.polygon.reduce((a, p) => a + p[1], 0) / z.polygon.length;
            return <span key={z.table_id} style={{ position: "absolute", left: `${cx * 100}%`, top: `${cy * 100}%`, transform: "translate(-50%,-50%)", background: "rgba(0,0,0,.65)", color: "#fff", padding: "1px 6px", borderRadius: 4, fontSize: 12, lineHeight: 1.4, pointerEvents: "none" }}>{z.name}</span>;
          })}
          {points.map((p, i) => <span key={i} style={{ position: "absolute", left: `${p[0] * 100}%`, top: `${p[1] * 100}%`, width: 10, height: 10, margin: -5, borderRadius: "50%", background: "#ff6a00", border: "2px solid #fff", pointerEvents: "none" }} />)}
        </div>
      ) : <Empty description="Upload a screenshot of the camera view to start" />}
      <div style={{ marginTop: 12 }}>
        <Typography.Text strong>Zones ({zones.length}/{tables.length} tables)</Typography.Text>
        <div style={{ marginTop: 6 }}>
          {zones.map((z) => <Tag key={z.table_id} closable onClose={() => setZones((all) => all.filter((x) => x.table_id !== z.table_id))}>{z.name}</Tag>)}
          {!zones.length && <Typography.Text type="secondary"> none yet</Typography.Text>}
        </div>
      </div>
    </Modal>
  );
}
