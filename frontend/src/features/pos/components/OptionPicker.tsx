import { useEffect, useState } from "react";
import { Checkbox, Modal, Radio, Space, Typography } from "antd";
import { lineUnitPrice, type MenuItem } from "../api";

export interface Picked { variantId?: number; addonIds: number[] }

export function OptionPicker({ item, currency, onCancel, onPick }: {
  item: MenuItem | null; currency: string; onCancel: () => void; onPick: (picked: Picked) => void;
}) {
  const [variantId, setVariantId] = useState<number>();
  const [addonIds, setAddonIds] = useState<number[]>([]);
  useEffect(() => {
    setVariantId(item?.variants[0]?.id);
    setAddonIds([]);
  }, [item]);
  if (!item) return null;
  const m = (v: string | number) => `${currency} ${Number(v).toFixed(2)}`;
  return (
    <Modal open title={item.name} okText={`Add · ${m(lineUnitPrice(item, variantId, addonIds))}`} onCancel={onCancel}
      onOk={() => onPick({ variantId, addonIds })} destroyOnClose>
      {item.variants.length > 0 && (
        <div style={{ marginBottom: 16 }}>
          <Typography.Text strong>Size / variant</Typography.Text><br />
          <Radio.Group value={variantId} onChange={(e) => setVariantId(e.target.value)}>
            <Space direction="vertical">{item.variants.map((v) => <Radio key={v.id} value={v.id}>{v.name} · {m(v.price)}</Radio>)}</Space>
          </Radio.Group>
        </div>
      )}
      {item.addons.length > 0 && (
        <div>
          <Typography.Text strong>Add-ons</Typography.Text><br />
          <Checkbox.Group value={addonIds} onChange={(v) => setAddonIds(v as number[])}>
            <Space direction="vertical">{item.addons.map((a) => <Checkbox key={a.id} value={a.id}>{a.name} · + {m(a.price)}</Checkbox>)}</Space>
          </Checkbox.Group>
        </div>
      )}
    </Modal>
  );
}
