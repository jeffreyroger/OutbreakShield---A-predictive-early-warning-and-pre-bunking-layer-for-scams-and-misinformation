import { useState } from "react";
import { apiFetch } from "../lib/api";

interface FeedProps {
  posts: any[] | null;
  reviewPosts: any[] | null;
  autoPublish: boolean;
  onRefresh: () => void;
}

export default function Feed({ posts, reviewPosts, autoPublish, onRefresh }: FeedProps) {
  const [activeTab, setActiveTab] = useState<"feed" | "review">("feed");

  const handleApprove = async (id: string) => {
    try {
      const res = await apiFetch(`/review/${id}/approve`, { method: "POST" });
      if (res.ok) onRefresh();
    } catch (e) {
      console.error(e);
    }
  };

  const handleReject = async (id: string) => {
    try {
      const res = await apiFetch(`/review/${id}/reject`, { method: "POST" });
      if (res.ok) onRefresh();
    } catch (e) {
      console.error(e);
    }
  };

  const displayPosts = activeTab === "feed" ? (posts || []) : (reviewPosts || []);

  return (
    <div className="glass-panel animate-fade-in" style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", borderBottom: "1px solid var(--panel-border)", paddingBottom: "0.75rem" }}>
        <h3 style={{ margin: 0, fontSize: "1.2rem", color: "var(--color-accent)", display: "flex", alignItems: "center", gap: "0.5rem" }}>
          📢 Inoculation Dashboard (FR-7.4, FR-5.7)
        </h3>
        <div style={{ display: "flex", gap: "0.5rem" }}>
          <button
            onClick={() => setActiveTab("feed")}
            style={{
              background: activeTab === "feed" ? "rgba(168, 85, 247, 0.25)" : "transparent",
              borderColor: activeTab === "feed" ? "var(--color-accent)" : "transparent",
              fontSize: "0.85rem",
              padding: "0.4rem 0.8rem"
            }}
          >
            Published Feed ({posts?.length || 0})
          </button>
          {!autoPublish && (
            <button
              onClick={() => setActiveTab("review")}
              style={{
                background: activeTab === "review" ? "rgba(244, 63, 94, 0.2)" : "transparent",
                borderColor: activeTab === "review" ? "var(--color-escalating)" : "transparent",
                color: reviewPosts && reviewPosts.length > 0 ? "#fda4af" : "#fff",
                fontSize: "0.85rem",
                padding: "0.4rem 0.8rem",
                display: "flex",
                alignItems: "center",
                gap: "0.4rem"
              }}
            >
              Review Queue ({reviewPosts?.length || 0})
              {reviewPosts && reviewPosts.length > 0 && (
                <span style={{ width: "8px", height: "8px", borderRadius: "50%", background: "var(--color-escalating)", display: "inline-block" }}></span>
              )}
            </button>
          )}
        </div>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: "1rem", overflowY: "auto", maxHeight: "500px", paddingRight: "0.5rem" }}>
        {displayPosts.length === 0 ? (
          <div style={{ padding: "3rem", textAlign: "center", opacity: 0.5 }}>
            {activeTab === "feed"
              ? "No active warnings published. Replay reports to trigger alerts."
              : "Review queue is empty. Pending alerts will appear here."}
          </div>
        ) : (
          displayPosts.map((post) => (
            <div
              key={post.id}
              className="glass-panel"
              style={{
                background: "rgba(255, 255, 255, 0.02)",
                padding: "1.25rem",
                borderLeft: post.template_assisted
                  ? "4px solid #f59e0b"
                  : "4px solid var(--color-accent)",
                display: "flex",
                flexDirection: "column",
                gap: "0.75rem",
                animation: "fadeIn 0.3s ease-out"
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: "1rem", flexWrap: "wrap" }}>
                <div>
                  <h4 style={{ margin: 0, fontSize: "1.1rem", color: "#fff" }}>{post.title}</h4>
                  <div style={{ display: "flex", gap: "0.5rem", marginTop: "0.4rem", flexWrap: "wrap" }}>
                    <span className="tag tag-stable" style={{ fontSize: "0.65rem" }}>
                      🎯 {post.target_segment}
                    </span>
                    <span className="tag" style={{ background: "rgba(255,255,255,0.08)", color: "#fff", fontSize: "0.65rem", textTransform: "uppercase" }}>
                      🌐 {post.language}
                    </span>
                    {post.template_assisted && (
                      <span className="tag" style={{ background: "rgba(245, 158, 11, 0.15)", color: "#fcd34d", border: "1px solid rgba(245, 158, 11, 0.3)", fontSize: "0.65rem" }}>
                        🛡️ Curated Template
                      </span>
                    )}
                  </div>
                </div>

                <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", fontSize: "0.8rem", color: "var(--color-text-secondary)" }}>
                  <span>Published: <strong style={{ color: "#fff" }}>{new Date(post.created_at || post.createdAt).toLocaleTimeString()}</strong></span>
                  <span>Basis: <strong style={{ color: "#fff" }}>{post.supporting_report_count} reports</strong></span>
                  <span>Rt at alert: <strong style={{ color: "var(--color-escalating)" }}>{post.rt_at_publish?.toFixed(2)} ({post.rt_lower_bound?.toFixed(2)})</strong></span>
                </div>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: "0.75rem", marginTop: "0.25rem" }}>
                <div style={{ background: "rgba(168, 85, 247, 0.03)", border: "1px solid rgba(168, 85, 247, 0.08)", borderRadius: "8px", padding: "0.75rem" }}>
                  <span style={{ fontSize: "0.75rem", textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--color-accent)", fontWeight: 600, display: "block", marginBottom: "0.25rem" }}>
                    Layer 1: Cognitive Technique Defense (Pre-bunk)
                  </span>
                  <p style={{ margin: 0, fontSize: "0.9rem", lineHeight: 1.4, color: "var(--color-text-secondary)" }}>
                    {post.technique_layer}
                  </p>
                </div>

                <div style={{ background: "rgba(255, 255, 255, 0.01)", border: "1px solid rgba(255, 255, 255, 0.04)", borderRadius: "8px", padding: "0.75rem" }}>
                  <span style={{ fontSize: "0.75rem", textTransform: "uppercase", letterSpacing: "0.05em", color: "#fff", fontWeight: 600, display: "block", marginBottom: "0.25rem" }}>
                    Layer 2: Local Variant Signature (Weakened Dose)
                  </span>
                  <p style={{ margin: 0, fontSize: "0.9rem", lineHeight: 1.4, color: "var(--color-text-secondary)" }}>
                    {post.variant_layer}
                  </p>
                </div>
              </div>

              {post.action_steps && post.action_steps.length > 0 && (
                <div style={{ marginTop: "0.25rem" }}>
                  <span style={{ fontSize: "0.8rem", fontWeight: 600, color: "#fff", display: "block", marginBottom: "0.4rem" }}>
                    🛡️ Actions you must take:
                  </span>
                  <ul style={{ margin: 0, paddingLeft: "1.25rem", fontSize: "0.85rem", color: "var(--color-text-secondary)", display: "flex", flexDirection: "column", gap: "0.25rem" }}>
                    {post.action_steps.map((step: string, idx: number) => (
                      <li key={idx}>{step}</li>
                    ))}
                  </ul>
                </div>
              )}

              {activeTab === "review" && (
                <div style={{ display: "flex", gap: "0.75rem", marginTop: "0.5rem", justifyContent: "flex-end" }}>
                  <button
                    onClick={() => handleReject(post.id)}
                    style={{
                      background: "rgba(244, 63, 94, 0.1)",
                      borderColor: "rgba(244, 63, 94, 0.3)",
                      color: "#fda4af"
                    }}
                  >
                    Reject Post
                  </button>
                  <button
                    onClick={() => handleApprove(post.id)}
                    style={{
                      background: "rgba(34, 197, 94, 0.2)",
                      borderColor: "rgba(34, 197, 94, 0.4)",
                      color: "#86efac"
                    }}
                  >
                    Approve & Publish
                  </button>
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
