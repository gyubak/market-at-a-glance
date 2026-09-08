import { useClock } from "./lib/session";
import TopBar from "./components/TopBar";
import LeftPanel from "./panels/LeftPanel";
import TopCenterPanel from "./panels/TopCenterPanel";
import HeatmapPanel from "./panels/HeatmapPanel";
import RightPanel from "./panels/RightPanel";

export default function App() {
  const clock = useClock();
  return (
    <div className="app-root">
      <TopBar clock={clock} />
      <div className="app">
        <div className="pane-left">
          <LeftPanel clock={clock} />
        </div>
        <div className="pane-tc">
          <TopCenterPanel clock={clock} />
        </div>
        <div className="pane-heat">
          <HeatmapPanel />
        </div>
        <div className="pane-right">
          <RightPanel clock={clock} />
        </div>
      </div>
    </div>
  );
}
