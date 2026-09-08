import CandleChart from "../charts/CandleChart";
import { useSeries } from "../lib/store";
import type { CandleSeries } from "../types";

const IDS = ["nasdaq_fut", "ust2y", "wti", "dxy", "usdkrw"];

export default function LeftPanel({ clock }: { clock: number }) {
  return (
    <>
      {IDS.map((id) => (
        <Slot key={id} id={id} clock={clock} />
      ))}
    </>
  );
}

function Slot({ id, clock }: { id: string; clock: number }) {
  const s = useSeries(id) as CandleSeries | undefined;
  if (!s) return <div className="block chart-box" />;
  return <CandleChart series={s} clock={clock} />;
}
