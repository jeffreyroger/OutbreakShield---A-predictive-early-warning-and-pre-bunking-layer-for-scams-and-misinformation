import { useState, useEffect } from "react";
import { ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid, ReferenceLine } from "recharts";
import { apiFetch } from "../lib/api";

interface RtPanelProps {
  selectedVariantId: string | null;
  lineages: any[] | null;
}

export default function RtPanel({ selectedVariantId, lineages }: RtPanelProps) {
  const [data, setData] = useState<any[] | null>(null);
  const [loading, setLoading] = useState(false);

  // Find the selected lineage's label
  const findLabel = (nodes: any[] | null, id: string): string => {
    if (!nodes) return id;
    for (const n of nodes) {
      if (n.variant_id === id) return n.label;
      const found = findLabel(n.children, id);
      if (found !== id) return found;
    }
    return id;
  };

  const selectedLabel = selectedVariantId ? findLabel(lineages, selectedVariantId) : null;

  useEffect(() => {
    if (!selectedVariantId) {
      setData(null);
      return;
    }
    setLoading(true);
    apiFetch(`/lineages/${selectedVariantId}/rt`)
      .then((res) => res.json())
      .then((resData) => {
        setData(resData.series || []);
        setLoading(false);
      })
      .catch((err) => {
        console.error("Error fetching Rt series:", err);
        setLoading(false);
      });
  }, [selectedVariantId]);

  if (!selectedVariantId) {
    return (
      <div className="glass-panel" style={{ height: "350px", display: "flex", justifyContent: "center", alignItems: "center", opacity: 0.5 }}>
        Click on a lineage node in the forest above to plot its spread velocity (Rt).
      </div>
    );
  }

  return (
    <div className="glass-panel animate-fade-in" style={{ display: "flex", flexDirection: "column", gap: "1rem", height: "350px" }}>
      <div>
        <h3 style={{ margin: 0, fontSize: "1.2rem", color: "var(--color-accent)" }}>
          📈 Spread Velocity Analysis (FR-7.2, DR-1)
        </h3>
        <p style={{ margin: 0, fontSize: "0.85rem", opacity: 0.6 }}>
          Time-varying reproduction number (Rt) for: <strong style={{ color: "#fff" }}>{selectedLabel}</strong>
        </p>
      </div>

      <div style={{ flexGrow: 1, background: "rgba(0,0,0,0.15)", borderRadius: "12px", border: "1px solid var(--panel-border)", padding: "12px" }}>
        {loading ? (
          <div style={{ height: "100%", display: "flex", justifyContent: "center", alignItems: "center", opacity: 0.5 }}>
            Loading Rt data...
          </div>
        ) : !data || data.length === 0 ? (
          <div style={{ height: "100%", display: "flex", justifyContent: "center", alignItems: "center", opacity: 0.5 }}>
            Insufficient data to calculate Rt series.
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="rtGlow" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="var(--color-accent)" stopOpacity={0.25} />
                  <stop offset="95%" stopColor="var(--color-accent)" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
              <XAxis
                dataKey="as_of"
                tickFormatter={(val) => {
                  const d = new Date(val);
                  return `${d.getMonth() + 1}/${d.getDate()}`;
                }}
                stroke="#64748b"
                fontSize={10}
              />
              <YAxis domain={[0, 'auto']} stroke="#64748b" fontSize={10} />
              <Tooltip
                contentStyle={{ background: "rgba(15,10,25,0.95)", border: "1px solid var(--panel-border)", borderRadius: "8px" }}
                labelFormatter={(label) => new Date(label).toLocaleString()}
              />
              <ReferenceLine y={1} stroke="#f43f5e" strokeDasharray="3 3" strokeWidth={1.5} label={{ value: "Rt = 1 (Growth Threshold)", fill: "#f43f5e", fontSize: 10, position: "insideBottomLeft" }} />
              {/* credible interval area band */}
              <Area
                type="monotone"
                dataKey="rt_upper"
                stroke="none"
                fill="rgba(168, 85, 247, 0.1)"
                name="Confidence Interval Upper Bound"
              />
              <Area
                type="monotone"
                dataKey="rt"
                stroke="var(--color-accent)"
                strokeWidth={2}
                fill="url(#rtGlow)"
                name="Rt Point Estimate"
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}
