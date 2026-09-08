import { fmtClockSeconds } from "../lib/session";
import { useHoverOHLC } from "../lib/hover";

export default function TopBar({ clock }: { clock: number }) {
  const h = useHoverOHLC();
  return (
    <div className="topbar">
      <div className="price-indicator">
        {h && (
          <>
            <span className="pi-name">{h.label}</span>
            <span className="pi-ohlc">
              시 {h.o.toFixed(h.decimals)}　고 {h.h.toFixed(h.decimals)}　저 {h.l.toFixed(h.decimals)}　종
              <b style={{ color: h.c >= h.o ? "var(--up)" : "var(--down)" }}> {h.c.toFixed(h.decimals)}</b>
            </span>
          </>
        )}
      </div>
      <div className="topbar-clock">
        {fmtClockSeconds(clock)} <span className="tz">KST</span>
      </div>
    </div>
  );
}
