import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert, Button, Card, Empty, Form, Input, Modal, Popconfirm, Radio, Select, Skeleton, Space, Tag, Typography, Upload, message } from "antd";
import { useState } from "react";
import { posApi } from "../../pos/api";
import { operationsApi, type Camera } from "../api";
import { ZoneEditor } from "../components/ZoneEditor";

export function CameraPage({ outletId }: { outletId: number }) {
  const queryClient = useQueryClient();
  const [form] = Form.useForm();
  const [adding, setAdding] = useState(false);
  const [zoneCamera, setZoneCamera] = useState<Camera | null>(null);
  const cameras = useQuery({ queryKey: ["cameras", outletId], queryFn: () => operationsApi.cameras(outletId), refetchInterval: 30000 });
  const coverage = useQuery({ queryKey: ["coverage", outletId], queryFn: () => operationsApi.coverage(outletId) });
  const tables = useQuery({ queryKey: ["tables", outletId], queryFn: () => posApi.tables(outletId) });
  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: ["cameras", outletId] });
    void queryClient.invalidateQueries({ queryKey: ["coverage", outletId] });
  };
  const sourceType = Form.useWatch("source_type", form);
  const floors = coverage.data?.floors ?? [];
  const create = useMutation({
    mutationFn: (v: { name: string; source_type: "rtsp" | "recording"; stream_url?: string; floor_id?: number }) => operationsApi.createCamera(outletId, v),
    onSuccess: () => { message.success("Camera added"); setAdding(false); form.resetFields(); refresh(); },
    onError: (e: Error) => message.error(e.message),
  });
  const remove = useMutation({
    mutationFn: (id: number) => operationsApi.deleteCamera(outletId, id),
    onSuccess: () => { message.success("Camera removed"); refresh(); },
    onError: (e: Error) => message.error(e.message),
  });
  const move = useMutation({
    mutationFn: ({ id, floor_id }: { id: number; floor_id: number }) => operationsApi.updateCamera(outletId, id, { floor_id }),
    onSuccess: refresh,
    onError: (e: Error) => message.error(e.message),
  });

  function cameraCard(camera: Camera) {
    return (
      <Card key={camera.id} title={camera.name} extra={<Tag color={camera.enabled ? "green" : "default"}>{camera.enabled ? "Enabled" : "Disabled"}</Tag>}>
        <Typography.Paragraph type="secondary">{camera.source_type.toUpperCase()}</Typography.Paragraph>
        <Typography.Paragraph>
          {camera.regions?.length ? <Tag color="blue">{camera.regions.length} table zones</Tag> : <Tag color="orange">No zones yet</Tag>}
        </Typography.Paragraph>
        <Typography.Paragraph type="secondary">Last observed: {camera.last_seen_at ? new Date(camera.last_seen_at).toLocaleString() : "No observation yet"}</Typography.Paragraph>
        {camera.floor_id == null && floors.length > 0 && (
          <Select placeholder="Assign floor" style={{ width: "100%", marginBottom: 12 }} onChange={(floor_id) => move.mutate({ id: camera.id, floor_id })}
            options={floors.map((f) => ({ value: f.floor_id, label: f.floor_name }))} />
        )}
        <Space wrap>
          <Button type="primary" disabled={camera.floor_id == null && floors.length > 0} onClick={() => setZoneCamera(camera)}>Table zones</Button>
          <Upload accept=".mp4,.mov,.avi,.mkv" showUploadList={false}
            customRequest={({ file, onSuccess, onError }) => {
              const hide = message.loading("Uploading recording…", 0);
              operationsApi.uploadRecording(outletId, camera.id, file as File)
                .then(() => { message.success("Recording uploaded"); refresh(); onSuccess?.({}); })
                .catch((e: Error) => { message.error(e.message); onError?.(e); })
                .finally(hide);
            }}>
            <Button>Upload recording</Button>
          </Upload>
          <Popconfirm title="Remove this camera?" onConfirm={() => remove.mutate(camera.id)}><Button danger>Remove</Button></Popconfirm>
        </Space>
      </Card>
    );
  }

  const all = cameras.data ?? [];
  const unassigned = all.filter((c) => c.floor_id == null);

  return (
    <div className="page">
      <div className="page-heading">
        <div><Typography.Title level={2}>AI monitoring</Typography.Title>
          <Typography.Paragraph type="secondary">Add as many cameras as each floor needs, then outline every table in at least one camera. Where views overlap, a table can be outlined in several cameras. Detection accuracy is not claimed without real-footage validation.</Typography.Paragraph></div>
        <Button type="primary" onClick={() => setAdding(true)}>Add camera</Button>
      </div>
      {cameras.error && <Alert type="error" showIcon message="Camera status could not be loaded" />}
      {!floors.length && !coverage.isLoading && <Alert type="warning" showIcon style={{ marginBottom: 16 }} message="No floors yet" description="Add tables first in Tables & floor; floors are created with them." />}
      {cameras.isLoading || coverage.isLoading ? <Skeleton active /> : (
        <>
          {floors.map((floor) => {
            const floorCameras = all.filter((c) => c.floor_id === floor.floor_id);
            const covered = floor.tables.length - floor.uncovered.length;
            return (
              <Card key={floor.floor_id} className="section-card" title={`${floor.floor_name}`}
                extra={<Tag color={floor.tables.length && !floor.uncovered.length ? "green" : "orange"}>{covered}/{floor.tables.length} tables covered · {floorCameras.length} camera{floorCameras.length === 1 ? "" : "s"}</Tag>}>
                {floor.uncovered.length > 0 && <Alert type="warning" showIcon style={{ marginBottom: 12 }} message={`Not covered by any camera: ${floor.uncovered.join(", ")}`} />}
                {floorCameras.length ? <div className="floor-grid">{floorCameras.map(cameraCard)}</div> : <Empty description="No cameras on this floor yet" />}
              </Card>
            );
          })}
          {unassigned.length > 0 && (
            <Card className="section-card" title="Cameras without a floor"><div className="floor-grid">{unassigned.map(cameraCard)}</div></Card>
          )}
          {!all.length && <Card><Empty description="No cameras configured for this outlet." /></Card>}
        </>
      )}

      <Modal title="Add camera" open={adding} onCancel={() => setAdding(false)} okText="Add" confirmLoading={create.isPending} destroyOnClose
        onOk={() => form.validateFields().then((v) => create.mutate(v))}>
        <Form form={form} layout="vertical" requiredMark={false} initialValues={{ source_type: "rtsp" }}>
          <Form.Item name="name" label="Camera name" rules={[{ required: true }]}><Input placeholder="e.g. Ground floor – entrance side" /></Form.Item>
          <Form.Item name="floor_id" label="Floor" rules={[{ required: floors.length > 0, message: "Select the floor this camera watches" }]}>
            <Select placeholder="Select floor" options={floors.map((f) => ({ value: f.floor_id, label: f.floor_name }))} />
          </Form.Item>
          <Form.Item name="source_type" label="Source"><Radio.Group options={[{ value: "rtsp", label: "Live RTSP stream" }, { value: "recording", label: "Recorded video (upload later)" }]} /></Form.Item>
          {sourceType === "rtsp" && (
            <Form.Item name="stream_url" label="RTSP URL" extra="Stored encrypted and never shown again." rules={[{ required: true, pattern: /^rtsps?:\/\//, message: "Must start with rtsp:// or rtsps://" }]}>
              <Input.Password placeholder="rtsp://user:password@192.168.1.10:554/stream1" autoComplete="off" />
            </Form.Item>
          )}
        </Form>
      </Modal>
      {zoneCamera && (
        <ZoneEditor key={zoneCamera.id} outletId={outletId} camera={zoneCamera} open onClose={() => setZoneCamera(null)}
          tables={(tables.data ?? []).filter((t) => zoneCamera.floor_id == null || floors.find((f) => f.floor_id === zoneCamera.floor_id)?.tables.some((ft) => ft.id === t.id))} />
      )}
    </div>
  );
}
