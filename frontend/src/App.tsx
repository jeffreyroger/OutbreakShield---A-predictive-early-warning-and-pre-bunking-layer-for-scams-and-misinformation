import StatusBar from "./components/StatusBar";
import LineageTree from "./components/LineageTree";
import RtPanel from "./components/RtPanel";
import BacktestChart from "./components/BacktestChart";
import Feed from "./components/Feed";
import TraceView from "./components/TraceView";
import LimitationsPanel from "./components/LimitationsPanel";

export default function App() {
  return (
    <div>
      <StatusBar />
      <main style={{ padding: "1rem", display: "grid", gap: "1.5rem" }}>
        <LineageTree />
        <RtPanel />
        <BacktestChart />
        <Feed />
        <TraceView />
        <LimitationsPanel />
      </main>
    </div>
  );
}
