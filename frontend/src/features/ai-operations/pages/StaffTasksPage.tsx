import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert, Button, Card, Empty, Space, Tag, Typography, message } from "antd";
import { CheckOutlined, ClockCircleOutlined } from "@ant-design/icons";
import { operationsApi, type StaffTask } from "../api";

export function StaffTasksPage({ outletId }: { outletId: number }) {
  const client = useQueryClient();
  const tasks = useQuery({ queryKey: ["staff-tasks", outletId], queryFn: () => operationsApi.tasks(outletId), refetchInterval: 10000 });
  const updateTask = useMutation({
    mutationFn: ({ task, action }: { task: StaffTask; action: "acknowledge" | "complete" }) =>
      action === "acknowledge"
        ? operationsApi.acknowledge(outletId, task.id)
        : operationsApi.complete(outletId, task.id),
    onSuccess: async () => client.invalidateQueries({ queryKey: ["staff-tasks", outletId] }),
    onError: (error: Error) => message.error(error.message),
  });

  return (
    <div className="page">
      <div className="page-heading"><div><Typography.Title level={2}>Staff task queue</Typography.Title><Typography.Paragraph type="secondary">Cleaning, serving and billing tasks routed to the right team.</Typography.Paragraph></div></div>
      {tasks.error && <Alert type="error" showIcon message="Could not refresh the task queue" />}
      <div className="task-list">
        {(tasks.data ?? []).map((task) => (
          <Card className="task-card" key={task.id}>
            <div className="task-card-main">
              <div className={`task-avatar task-${task.target_role}`}>{task.target_role.slice(0, 1).toUpperCase()}</div>
              <div className="task-copy">
                <Typography.Title level={5}>{task.title}</Typography.Title>
                <Space wrap>
                  <Tag color="blue">{task.target_role}</Tag>
                  <Tag>{task.status}</Tag>
                  {task.table_id && <Typography.Text type="secondary">Table #{task.table_id}</Typography.Text>}
                  {task.order_id && <Typography.Text type="secondary">Order #{task.order_id}</Typography.Text>}
                </Space>
              </div>
              <Space>
                {task.status === "pending" && <Button icon={<ClockCircleOutlined />} onClick={() => updateTask.mutate({ task, action: "acknowledge" })} loading={updateTask.isPending}>Acknowledge</Button>}
                <Button type="primary" icon={<CheckOutlined />} onClick={() => updateTask.mutate({ task, action: "complete" })} loading={updateTask.isPending}>Complete</Button>
              </Space>
            </div>
          </Card>
        ))}
        {!tasks.isLoading && !tasks.error && !tasks.data?.length && <Card><Empty description="All caught up — no open tasks." /></Card>}
      </div>
    </div>
  );
}
