import CandleChart from "../charts/CandleChart";
import FlowChart from "../charts/FlowChart";
import { useSeries } from "../lib/store";
import type { CandleSeries, FlowSeries } from "../types";

const ROW1 = ["kospi_fut", "kosdaq_fut"];

export default function TopCenterPanel({ clock }: { clock: number }) {
  const flow = useSeries("kospi_flow") as FlowSeries | undefined;
  return (
    <>
      <div className="tc-row1">
        {ROW1.map((id) => (
          <Slot key={id} id={id} clock={clock} />
        ))}
      </div>
      <div className="tc-row2">
        {flow ? (
          <FlowChart series={flow} clock={clock} className="block flow-box" />
        ) : (
          <div className="block flow-box" />
        )}
      </div>
    </>
  );
}

function Slot({ id, clock }: { id: string; clock: number }) {
  const s = useSeries(id) as CandleSeries | undefined;
  if (!s) return <div className="block chart-box" />;
  return <CandleChart series={s} clock={clock} />;
}
