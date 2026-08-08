export default function LimitationsPanel() {
  return (
    <div className="glass-panel" style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
      <h3 style={{ margin: 0, fontSize: "1.2rem", color: "var(--color-accent)", display: "flex", alignItems: "center", gap: "0.5rem" }}>
        ⚠️ Model Assumptions & Limitations (ETH-7, docs.md §5)
      </h3>
      <p style={{ margin: 0, fontSize: "0.9rem", color: "var(--color-text-secondary)", lineHeight: 1.5 }}>
        OutbreakShield prioritizes transparency and scientific rigour. Below are the standing limitations and mathematical assumptions of the active modeling pipeline.
      </p>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: "1.25rem", marginTop: "0.5rem" }}>
        <div style={{ display: "flex", flexDirection: "column", gap: "0.25rem" }}>
          <h4 style={{ margin: 0, fontSize: "0.95rem", color: "#fff" }}>1. Assumed Serial Interval prior (Open Issue 1)</h4>
          <span style={{ fontSize: "0.85rem", color: "var(--color-text-secondary)", lineHeight: 1.4 }}>
            The serial interval (mean = 2.5 days, SD = 1.5 days) is assumed from literature on pathogen transmission proxies and is not measured from individual report lineages.
          </span>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: "0.25rem" }}>
          <h4 style={{ margin: 0, fontSize: "0.95rem", color: "#fff" }}>2. Uniform Propensity Weights (Open Issue 2)</h4>
          <span style={{ fontSize: "0.85rem", color: "var(--color-text-secondary)", lineHeight: 1.4 }}>
            Reporting propensity weights currently default to 1.0 across all segments. Under-reporting bias is assumed to be stable over time, as Rt estimates depend on the rate of arrival.
          </span>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: "0.25rem" }}>
          <h4 style={{ margin: 0, fontSize: "0.95rem", color: "#fff" }}>3. Vernacular Embedding Quality (DR-4)</h4>
          <span style={{ fontSize: "0.85rem", color: "var(--color-text-secondary)", lineHeight: 1.4 }}>
            Local embeddings underperform in low-resource Indian languages. To mitigate false merges, thresholds are tuned separately per language:
          </span>
          <table style={{ width: "100%", fontSize: "0.75rem", borderCollapse: "collapse", marginTop: "0.5rem", background: "rgba(0,0,0,0.2)", borderRadius: "6px" }}>
            <thead>
              <tr style={{ borderBottom: "1px solid rgba(168,85,247,0.15)", textAlign: "left" }}>
                <th style={{ padding: "4px 8px" }}>Language</th>
                <th style={{ padding: "4px 8px" }}>Best Thresh</th>
                <th style={{ padding: "4px 8px" }}>Precision</th>
                <th style={{ padding: "4px 8px" }}>F1-Score</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td style={{ padding: "4px 8px" }}>English (EN)</td>
                <td style={{ padding: "4px 8px" }}>0.52</td>
                <td style={{ padding: "4px 8px" }}>69.9%</td>
                <td style={{ padding: "4px 8px" }}>0.676</td>
              </tr>
              <tr>
                <td style={{ padding: "4px 8px" }}>Hindi (HI)</td>
                <td style={{ padding: "4px 8px" }}>0.50</td>
                <td style={{ padding: "4px 8px" }}>63.1%</td>
                <td style={{ padding: "4px 8px" }}>0.655</td>
              </tr>
              <tr style={{ color: "var(--color-text-secondary)" }}>
                <td style={{ padding: "4px 8px" }}>Tamil (TA)</td>
                <td style={{ padding: "4px 8px" }}>0.90</td>
                <td style={{ padding: "4px 8px" }}>72.3%</td>
                <td style={{ padding: "4px 8px" }}>0.573</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
