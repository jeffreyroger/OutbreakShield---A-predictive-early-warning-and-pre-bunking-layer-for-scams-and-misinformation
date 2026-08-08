import { useState, useEffect } from "react";
import StatusBar from "./components/StatusBar";
import LineageTree from "./components/LineageTree";
import RtPanel from "./components/RtPanel";
import BacktestChart from "./components/BacktestChart";
import Feed from "./components/Feed";
import TraceView from "./components/TraceView";
import LimitationsPanel from "./components/LimitationsPanel";
import { apiFetch } from "./lib/api";

export default function App() {
  const [status, setStatus] = useState<any>(null);
  const [feedPosts, setFeedPosts] = useState<any[] | null>(null);
  const [reviewPosts, setReviewPosts] = useState<any[] | null>(null);
  const [lineages, setLineages] = useState<any[] | null>(null);
  const [traces, setTraces] = useState<any[] | null>(null);
  const [selectedVariantId, setSelectedVariantId] = useState<string | null>(null);

  const fetchAllData = async () => {
    try {
      const [statusRes, feedRes, lineagesRes, traceRes] = await Promise.all([
        apiFetch("/status").then(r => r.json()),
        apiFetch("/feed").then(r => r.json()),
        apiFetch("/lineages").then(r => r.json()),
        apiFetch("/trace").then(r => r.json())
      ]);

      setStatus(statusRes);
      setFeedPosts(feedRes.posts || []);
      setLineages(lineagesRes.lineages || []);
      setTraces(traceRes.events || []);

      // If review mode is active, fetch pending review queue posts
      if (statusRes && !statusRes.auto_publish) {
        const reviewRes = await apiFetch("/review").then(r => r.json());
        setReviewPosts(reviewRes.posts || []);
      } else {
        setReviewPosts([]);
      }
    } catch (e) {
      console.error("Error polling dashboard data:", e);
    }
  };

  useEffect(() => {
    // Initial fetch
    fetchAllData();

    // Set polling interval
    const interval = setInterval(fetchAllData, 1000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div style={{ display: "flex", flexDirection: "column", minHeight: "100vh" }}>
      <StatusBar status={status} onRefresh={fetchAllData} />
      
      <main style={{
        padding: "1.5rem",
        display: "grid",
        gridTemplateColumns: "minmax(0, 1.6fr) minmax(0, 1fr)",
        gap: "1.5rem",
        alignItems: "start",
        flexGrow: 1
      }}>
        {/* Left Column: Modeling & Analytics */}
        <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
          <LineageTree 
            lineages={lineages} 
            selectedVariantId={selectedVariantId} 
            onSelectVariant={setSelectedVariantId} 
          />
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1.5rem", alignItems: "start" }}>
            <RtPanel selectedVariantId={selectedVariantId} lineages={lineages} />
            <BacktestChart />
          </div>
          <LimitationsPanel />
        </div>

        {/* Right Column: Operations & Execution Trace */}
        <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
          <Feed 
            posts={feedPosts} 
            reviewPosts={reviewPosts} 
            autoPublish={status ? status.auto_publish : true}
            onRefresh={fetchAllData} 
          />
          <TraceView traces={traces} />
        </div>
      </main>
    </div>
  );
}
