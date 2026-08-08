import { api, apiFetch } from "../lib/api";

interface StatusBarProps {
  status: any;
  onRefresh: () => void;
}

export default function StatusBar({ status, onRefresh }: StatusBarProps) {
  if (!status) {
    return (
      <div style={{
        background: "rgba(10, 5, 20, 0.8)",
        backdropFilter: "blur(12px)",
        borderBottom: "1px solid var(--panel-border)",
        padding: "0.75rem 1.5rem",
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center"
      }}>
        <div>Loading status...</div>
      </div>
    );
  }

  const {
    loop_running,
    auto_publish,
    simulated_now,
    compression_ratio,
    replay_paused,
    reports_replayed,
    total_reports,
    posts_published,
  } = status;

  const handlePauseResume = async () => {
    if (replay_paused) {
      await apiFetch("/replay/resume", { method: "POST" });
    } else {
      await apiFetch("/replay/pause", { method: "POST" });
    }
    onRefresh();
  };

  const handleInit = async () => {
    await apiFetch("/init", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ auto_publish: true })
    });
    onRefresh();
  };

  return (
    <div style={{
      background: "rgba(10, 5, 20, 0.95)",
      backdropFilter: "blur(12px)",
      borderBottom: "1px solid var(--panel-border)",
      padding: "0.75rem 1.5rem",
      display: "flex",
      justifyContent: "space-between",
      alignItems: "center",
      gap: "1rem",
      flexWrap: "wrap",
      position: "sticky",
      top: 0,
      zIndex: 100
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: "1.5rem" }}>
        <span style={{ fontSize: "1.25rem", fontWeight: 700, color: "var(--color-accent)", letterSpacing: "0.05em" }}>
          OUTBREAK<span style={{ color: "#fff" }}>SHIELD</span>
        </span>
        <div style={{ height: "1.5rem", width: "1px", background: "var(--panel-border)" }}></div>
        <div style={{ fontSize: "0.9rem" }}>
          <span style={{ opacity: 0.6 }}>Simulated Date:</span>{" "}
          <strong style={{ color: "#fff", fontFamily: "monospace" }}>
            {simulated_now ? new Date(simulated_now).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : "—"}
          </strong>
        </div>
        <div style={{ fontSize: "0.9rem" }}>
          <span style={{ opacity: 0.6 }}>Compression:</span>{" "}
          <strong style={{ color: "#fff" }}>
            {compression_ratio ? `${(compression_ratio / 3600).toFixed(1)}h/sec` : "—"}
          </strong>
        </div>
        <div style={{ fontSize: "0.9rem" }}>
          <span style={{ opacity: 0.6 }}>Mode:</span>{" "}
          <span className={`tag ${auto_publish ? 'tag-stable' : 'tag-escalating'}`} style={{ fontSize: "0.7rem" }}>
            {auto_publish ? "Auto-Publish" : "Review Mode"}
          </span>
        </div>
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
        <div style={{ fontSize: "0.85rem", opacity: 0.8 }}>
          Reports: <strong>{reports_replayed}</strong>/{total_reports} · Published: <strong>{posts_published}</strong>
        </div>

        {!loop_running ? (
          <button onClick={handleInit} style={{ background: "rgba(168, 85, 247, 0.2)", borderColor: "var(--color-accent)" }}>
            ⚡ Initialize Loop
          </button>
        ) : (
          <button onClick={handlePauseResume}>
            {replay_paused ? "▶ Resume Replay" : "⏸ Pause Replay"}
          </button>
        )}
        
        <span style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
          <span style={{
            width: "8px",
            height: "8px",
            borderRadius: "50%",
            background: loop_running ? "#22c55e" : "#ef4444",
            boxShadow: loop_running ? "0 0 8px #22c55e" : "0 0 8px #ef4444"
          }}></span>
          <span style={{ fontSize: "0.8rem", textTransform: "uppercase", opacity: 0.6, fontWeight: 600 }}>
            {loop_running ? "Live" : "Stopped"}
          </span>
        </span>
      </div>
    </div>
  );
}
