import { useEffect, useState } from "react";
import { Button, Tag, Typography } from "antd";
import { CaretRightOutlined, PauseOutlined, ReloadOutlined } from "@ant-design/icons";

type TableState = "available" | "occupied" | "eating" | "bill" | "dirty" | "cleaning";

interface Scene {
  title: string;
  actor: string;
  text: string;
  tables: Record<string, TableState>;
  focus?: string;
  log: string[];
  camera?: boolean;
}

const stateMeta: Record<TableState, { label: string; color: string }> = {
  available: { label: "Available", color: "#37c98a" },
  occupied: { label: "Seated", color: "#4c7cf0" },
  eating: { label: "Dining", color: "#8b5cf6" },
  bill: { label: "Bill requested", color: "#f59e0b" },
  dirty: { label: "Needs cleaning", color: "#ef5b5b" },
  cleaning: { label: "Being cleaned", color: "#14b8c4" },
};

const tableIds = ["T1", "T2", "T3", "T4", "T5", "T6"];
const base: Record<string, TableState> = {
  T1: "eating", T2: "available", T3: "occupied", T4: "available", T5: "eating", T6: "available",
};
const withT4 = (s: TableState): Record<string, TableState> => ({ ...base, T4: s });

const setup: Scene[] = [
  {
    title: "1. Cameras are mapped to tables",
    actor: "Setup",
    text: "Cameras are installed over the dining floor. Each table is outlined as a polygon on the camera view, so the system knows which pixels belong to which table.",
    tables: base,
    camera: true,
    log: ["camera cam-01 registered", "polygons T1..T6 saved for outlet", "staff roles and tables configured"],
  },
  {
    title: "2. Cameras capture each table",
    actor: "Camera",
    text: "Frames are sampled continuously. For every table polygon we record low-level observations: are people present, did they leave, is the table empty, are plates left behind.",
    tables: withT4("occupied"),
    focus: "T4",
    camera: true,
    log: ["observation T4: people_present=true", "observation T4: plates=false", "observations stored (heavy CV runs in workers)"],
  },
  {
    title: "3. AI interprets what it sees",
    actor: "AI",
    text: "Observations are combined over time into a table state. A table that was occupied and now shows guests gone with plates left becomes “needs cleaning”.",
    tables: withT4("dirty"),
    focus: "T4",
    camera: true,
    log: ["observation T4: people_present=false", "observation T4: plates=true", "AI: T4 occupied -> needs cleaning (sample confidence shown to staff)"],
  },
  {
    title: "4. Normalised operational event",
    actor: "Platform",
    text: "The result becomes a normalised operational event stored in PostgreSQL for your tenant only. Every downstream feature reads the same event stream.",
    tables: withT4("dirty"),
    focus: "T4",
    log: ["operational_event TABLE_NEEDS_CLEANING T4", "tenant isolation enforced (RLS)", "event passed to task rules"],
  },
  {
    title: "5. Task goes to the right staff",
    actor: "Staff tasking",
    text: "Event-to-task rules create a role-targeted task. Cleaning staff see “Clean T4”, without anyone walking the floor to notice.",
    tables: withT4("dirty"),
    focus: "T4",
    log: ["staff_task CLEAN T4 -> role: cleaning", "task status: pending", "delay alert if not acknowledged in time"],
  },
  {
    title: "6. Staff completes, table is ready",
    actor: "Staff",
    text: "Staff acknowledge and complete the task (pending → acknowledged → completed). The table returns to Available and the dashboard updates.",
    tables: withT4("available"),
    focus: "T4",
    log: ["task acknowledged by cleaner", "task completed -> table state updated", "T4 Available (cleaning time recorded)"],
  },
];

const posScenes: Scene[] = [
  {
    title: "Menu, prices and GST set up once",
    actor: "Owner",
    text: "Add categories, dishes and prices with the GST rate for each item. Service charge and round-off are set per outlet. Prices are entered without GST and tax is added on the bill.",
    tables: base,
    log: ["menu: Paneer Tikka ₹260, GST 5%", "menu: Cake ₹180, GST 18%", "outlet: service charge 10%, round-off on"],
  },
  {
    title: "Waiter takes the order",
    actor: "POS",
    text: "Pick the table, tap items, add notes like “less spicy”. The order is saved and a KOT goes straight to the kitchen screen. Extra items later become the next KOT.",
    tables: withT4("occupied"),
    focus: "T4",
    log: ["POST /orders (idempotency-key)", "KOT #1: 2 x Paneer Tikka, 1 x Cake", "kitchen task created"],
  },
  {
    title: "Kitchen prepares, floor serves",
    actor: "Kitchen",
    text: "The kitchen sees the KOT, marks it preparing and ready. Serving staff are told to pick it up and the table moves to Dining.",
    tables: withT4("eating"),
    focus: "T4",
    log: ["order: submitted -> preparing -> ready", "serving task -> waiter", "table T4: Dining"],
  },
  {
    title: "GST bill with discount and service charge",
    actor: "Cashier",
    text: "The cashier applies a discount (percent or fixed, with a reason), service charge and tip. CGST and SGST are calculated per rate slab and the bill gets the next consecutive number.",
    tables: withT4("bill"),
    focus: "T4",
    log: ["discount 10% (festival offer)", "CGST 2.5/9 + SGST 2.5/9 per slab", "bill no. O1/26-27/00042, round-off applied"],
  },
  {
    title: "Payment recorded, table freed",
    actor: "Cashier",
    text: "Record cash, UPI or card payments, including split payments. Once fully paid the order closes and the table is released for the next guests.",
    tables: withT4("dirty"),
    focus: "T4",
    log: ["payment: UPI ₹300 + cash ₹148", "order paid, table T4 needs cleaning", "refund and cancel-item need a reason"],
  },
];

const analyticsScene: Scene = {
  title: "Sales reports, GST report and revenue ideas",
  actor: "Analytics",
  text: "Daily sales, top items and the GST report (CGST/SGST by day and rate, CSV download) come straight from your bills. Weekly and monthly reports suggest ideas by day, meal window and festival.",
  tables: withT4("available"),
  log: ["sales today vs last week", "GST report CSV for your accountant", "suggest: dinner + festival -> promote biryani combos"],
};

const addonIntro = "Add-on: camera table monitoring. ";

const zones: Record<string, { points: string; label: [number, number] }> = {
  T1: { points: "40,650 495,650 470,830 60,830", label: [120, 700] },
  T2: { points: "0,850 300,850 270,1040 0,1040", label: [30, 910] },
  T3: { points: "900,590 1290,590 1300,840 890,840", label: [980, 640] },
  T4: { points: "1030,770 1600,770 1600,1000 1060,1000", label: [1100, 830] },
  T5: { points: "1385,555 1600,555 1600,670 1385,670", label: [1400, 600] },
  T6: { points: "470,495 585,495 595,590 460,590", label: [420, 480] },
};

export function DemoPlayer() {
  const [index, setIndex] = useState(0);
  const [playing, setPlaying] = useState(true);
  const scenes = [...posScenes, ...setup.map((x, i) => (i === 0 ? { ...x, text: addonIntro + x.text } : x)), analyticsScene]
    .map((x, i) => ({ ...x, title: `${i + 1}. ${x.title.replace(/^\d+\.\s*/, "")}` }));
  const scene = scenes[index];

  useEffect(() => {
    if (!playing) return;
    const timer = window.setTimeout(() => {
      if (index < scenes.length - 1) setIndex(index + 1);
      else setPlaying(false);
    }, 6000);
    return () => window.clearTimeout(timer);
  }, [playing, index, scenes.length]);

  function go(to: number) {
    setIndex(to);
    setPlaying(false);
  }

  return (
    <div className="demo-player">
      <div className="demo-stage">
        <div className="demo-floor">
          <div className="demo-feed">
            <img src="/images/floor.jpg" alt="Restaurant dining floor as seen by the camera" />
            <svg viewBox="0 0 1600 1067" preserveAspectRatio="none" role="img" aria-label="Table zones on the camera view">
              {tableIds.map((id) => {
                const st = scene.tables[id];
                const poly = zones[id];
                const color = stateMeta[st].color;
                return (
                  <g key={id}>
                    <polygon
                      className={scene.focus === id ? "demo-zone demo-focus" : "demo-zone"}
                      points={poly.points}
                      fill={color}
                      fillOpacity={scene.camera ? 0.28 : 0.4}
                      stroke={color}
                      strokeWidth="6"
                      strokeDasharray={scene.camera ? "22 12" : undefined}
                    />
                    <g transform={`translate(${poly.label[0]} ${poly.label[1]})`}>
                      <rect x="-70" y="-30" width={scene.focus === id ? 300 : 200} height="60" rx="30" fill="#101b2c" fillOpacity="0.85" />
                      <circle cx="-38" cy="0" r="12" fill={color} />
                      <text x="-14" y="12" fontSize="34" fontWeight="700" fill="#fff">{id}</text>
                      {scene.focus === id && <text x="64" y="11" fontSize="28" fill="#fff">{stateMeta[st].label}</text>}
                    </g>
                  </g>
                );
              })}
            </svg>
            {scene.camera && (
              <div className="demo-cam-hud">
                <span className="demo-rec"><i /> CAM-01 · LIVE</span>
                <span>AI table zones on</span>
              </div>
            )}
          </div>
          <div className="demo-legend">
            {(Object.keys(stateMeta) as TableState[]).map((k) => (
              <span key={k}><i style={{ background: stateMeta[k].color }} />{stateMeta[k].label}</span>
            ))}
          </div>
        </div>

        <div className="demo-info" key={index}>
          <Tag color="orange">{scene.actor}</Tag>
          <Typography.Title level={4}>{scene.title}</Typography.Title>
          <Typography.Paragraph>{scene.text}</Typography.Paragraph>
          <div className="demo-log">
            {scene.log.map((line, i) => (
              <div key={line} className="demo-log-line" style={{ animationDelay: `${0.4 + i * 0.9}s` }}>
                <code>&gt; {line}</code>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="demo-progress">
        {scenes.map((s, i) => (
          <button
            key={s.title}
            type="button"
            title={s.title}
            aria-label={s.title}
            className={i === index ? "demo-dot demo-dot-active" : i < index ? "demo-dot demo-dot-done" : "demo-dot"}
            onClick={() => go(i)}
          />
        ))}
      </div>
      <div className="demo-controls">
        <Button disabled={index === 0} onClick={() => go(index - 1)}>Back</Button>
        <Button
          type="primary"
          icon={playing ? <PauseOutlined /> : index === scenes.length - 1 ? <ReloadOutlined /> : <CaretRightOutlined />}
          onClick={() => {
            if (!playing && index === scenes.length - 1) setIndex(0);
            setPlaying(!playing);
          }}
        >
          {playing ? "Pause" : index === scenes.length - 1 ? "Replay" : "Play"}
        </Button>
        <Button disabled={index === scenes.length - 1} onClick={() => go(index + 1)}>Next</Button>
      </div>
    </div>
  );
}
