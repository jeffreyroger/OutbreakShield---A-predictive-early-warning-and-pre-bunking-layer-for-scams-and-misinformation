interface TraceViewProps {
  traces: any[] | null;
}

export default function TraceView({ traces }: TraceViewProps) {
  return (
    <div className="glass-panel" style={{ display: "flex", flexDirection: "column", gap: "1rem", height: "350px" }}>
      <h3 style={{ margin: 0, fontSize: "1.2rem", color: "var(--color-accent)" }}>
        🔍 Agent Decision Log (FR-7.6, FR-6.3)
      </h3>
      <div style={{ overflowY: "auto", flexGrow: 1, border: "1px solid var(--panel-border)", borderRadius: "8px", background: "rgba(0,0,0,0.2)" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.85rem", textAlign: "left" }}>
          <thead style={{ position: "sticky", top: 0, background: "rgba(15, 10, 25, 0.95)", borderBottom: "1px solid var(--panel-border)", zIndex: 5 }}>
            <tr>
              <th style={{ padding: "0.5rem 0.75rem" }}>Time</th>
              <th style={{ padding: "0.5rem 0.75rem" }}>Stage</th>
              <th style={{ padding: "0.5rem 0.75rem" }}>Input Summary</th>
              <th style={{ padding: "0.5rem 0.75rem" }}>Decision</th>
              <th style={{ padding: "0.5rem 0.75rem" }}>Score</th>
              <th style={{ padding: "0.5rem 0.75rem" }}>Latency</th>
            </tr>
          </thead>
          <tbody>
            {!traces || traces.length === 0 ? (
              <tr>
                <td colSpan={6} style={{ padding: "2rem", textAlign: "center", opacity: 0.5 }}>
                  No traces available yet. Initialize the loop to see live agent decisions.
                </td>
              </tr>
            ) : (
              traces.map((t) => (
                <tr key={t.id} style={{ borderBottom: "1px solid rgba(255,255,255,0.05)" }}>
                  <td style={{ padding: "0.4rem 0.75rem", fontFamily: "monospace", color: "var(--color-text-secondary)" }}>
                    {t.ts ? t.ts.split("T")[1]?.replace("Z", "") : "—"}
                  </td>
                  <td style={{ padding: "0.4rem 0.75rem" }}>
                    <span className="tag" style={{ background: "rgba(168,85,247,0.1)", color: "#c084fc", fontSize: "0.7rem", border: "1px solid rgba(168,85,247,0.2)" }}>
                      {t.stage}
                    </span>
                  </td>
                  <td style={{ padding: "0.4rem 0.75rem", maxWidth: "250px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {t.input_summary}
                  </td>
                  <td style={{ padding: "0.4rem 0.75rem", fontWeight: 500, color: t.decision?.includes("failed") || t.decision?.includes("drop") || t.decision?.includes("reject") ? "var(--color-escalating)" : "#22c55e" }}>
                    {t.decision || "—"}
                  </td>
                  <td style={{ padding: "0.4rem 0.75rem", fontFamily: "monospace" }}>
                    {t.score != null ? t.score.toFixed(3) : "—"}
                  </td>
                  <td style={{ padding: "0.4rem 0.75rem", color: t.latency_ms > 1000 ? "var(--color-escalating)" : "var(--color-text-secondary)" }}>
                    {t.latency_ms} ms
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
