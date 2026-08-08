import { useState, useEffect } from "react";
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid, Cell } from "recharts";
import { apiFetch } from "../lib/api";

export default function BacktestChart() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    apiFetch("/backtest")
      .then((res) => res.json())
      .then((resData) => {
        setData(resData);
        setLoading(false);
      })
      .catch((err) => {
        console.error("Error fetching backtest:", err);
        setLoading(false);
      });
  }, []);

  if (loading) {
    return (
      <div className="glass-panel" style={{ height: "300px", display: "flex", justifyContent: "center", alignItems: "center", opacity: 0.5 }}>
        Running backtest over historical waves...
      </div>
    );
  }

  if (!data || !data.waves || data.waves.length === 0) {
    return (
      <div className="glass-panel" style={{ height: "300px", display: "flex", justifyContent: "center", alignItems: "center", opacity: 0.5 }}>
        No historical backtest waves detected. Ensure data/labels/wave_ground_truth.csv is present and corpus is ingested.
      </div>
    );
  }

  // Calculate average lead time
  const validLeadTimes = data.waves
    .map((w: any) => w.lead_time_days)
    .filter((lt: any) => lt !== null && !isNaN(lt));
  const avgLeadTime = validLeadTimes.length > 0 
    ? (validLeadTimes.reduce((a: number, b: number) => a + b, 0) / validLeadTimes.length).toFixed(1)
    : "—";

  const chartData = data.waves.map((w: any) => ({
    name: w.variant.split("_").map((s: string) => s.charAt(0).toUpperCase() + s.slice(1)).join(" "),
    lead_time: w.lead_time_days ?? 0,
    alert_date: w.alert_date,
    ref_date: w.reference_date
  }));

  return (
    <div className="glass-panel animate-fade-in" style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", borderBottom: "1px solid var(--panel-border)", paddingBottom: "0.75rem" }}>
        <div>
          <h3 style={{ margin: 0, fontSize: "1.2rem", color: "var(--color-accent)" }}>
            📊 Historical Backtest Evaluation (FR-7.3, FR-3.10)
          </h3>
          <p style={{ margin: 0, fontSize: "0.85rem", opacity: 0.6 }}>
            Comparison of Rt-derived warnings against historical ground-truth acceleration.
          </p>
        </div>
      </div>

      {/* Aggregate Stats */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(130px, 1fr))", gap: "1rem", background: "rgba(0,0,0,0.15)", padding: "1rem", borderRadius: "12px", border: "1px solid var(--panel-border)" }}>
        <div style={{ textAlign: "center" }}>
          <span style={{ fontSize: "0.8rem", opacity: 0.6, display: "block" }}>Waves Tracked</span>
          <strong style={{ fontSize: "1.4rem", color: "#fff" }}>{data.n_waves}</strong>
        </div>
        <div style={{ textAlign: "center" }}>
          <span style={{ fontSize: "0.8rem", opacity: 0.6, display: "block" }}>Warning Coverage</span>
          <strong style={{ fontSize: "1.4rem", color: "#22c55e" }}>{(data.coverage * 100).toFixed(0)}%</strong>
        </div>
        <div style={{ textAlign: "center" }}>
          <span style={{ fontSize: "0.8rem", opacity: 0.6, display: "block" }}>False Alarms</span>
          <strong style={{ fontSize: "1.4rem", color: data.false_alarms > 0 ? "var(--color-escalating)" : "#22c55e" }}>{data.false_alarms}</strong>
        </div>
        <div style={{ textAlign: "center" }}>
          <span style={{ fontSize: "0.8rem", opacity: 0.6, display: "block" }}>Avg Lead Time</span>
          <strong style={{ fontSize: "1.4rem", color: "var(--color-stable)" }}>{avgLeadTime} days</strong>
        </div>
      </div>

      {/* Chart */}
      <div style={{ height: "260px", background: "rgba(0,0,0,0.15)", borderRadius: "12px", border: "1px solid var(--panel-border)", padding: "12px" }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={chartData} layout="vertical" margin={{ top: 5, right: 20, left: 30, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
            <XAxis type="number" stroke="#64748b" fontSize={10} label={{ value: "Lead Time (Days Early)", fill: "#64748b", position: "bottom", offset: 0, fontSize: 10 }} />
            <YAxis dataKey="name" type="category" stroke="#64748b" fontSize={9} width={120} />
            <Tooltip
              contentStyle={{ background: "rgba(15,10,25,0.95)", border: "1px solid var(--panel-border)", borderRadius: "8px" }}
              formatter={(value: any) => [`${value.toFixed(1)} days early`, "Lead Time"]}
            />
            <Bar dataKey="lead_time" radius={[0, 4, 4, 0]}>
              {chartData.map((entry: any, index: number) => (
                <Cell 
                  key={`cell-${index}`} 
                  fill={entry.lead_time > 0 ? "rgba(34, 197, 94, 0.7)" : "rgba(244, 63, 94, 0.7)"} 
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
