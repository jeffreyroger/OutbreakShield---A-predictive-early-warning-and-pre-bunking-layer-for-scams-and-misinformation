import { useEffect, useRef } from "react";
import * as d3 from "d3";

interface LineageTreeProps {
  lineages: any[] | null;
  selectedVariantId: string | null;
  onSelectVariant: (id: string) => void;
}

export default function LineageTree({ lineages, selectedVariantId, onSelectVariant }: LineageTreeProps) {
  const svgRef = useRef<SVGSVGElement | null>(null);

  useEffect(() => {
    if (!lineages || lineages.length === 0 || !svgRef.current) return;

    // Clear previous elements
    d3.select(svgRef.current).selectAll("*").remove();

    const svg = d3.select(svgRef.current);
    const width = svgRef.current.clientWidth || 800;
    const height = 450;
    svg.attr("height", height);

    // Combine all roots into a single dummy root for layout
    const dummyRoot: any = {
      variant_id: "dummy-root",
      label: "All Lineages",
      children: lineages,
      report_count: 0,
      rt_status: "INSUFFICIENT_DATA"
    };

    const root = d3.hierarchy(dummyRoot);
    const treeLayout = d3.tree().size([width - 100, height - 120]);
    treeLayout(root);

    // Filter out the dummy root node and its links for rendering
    const nodes = root.descendants().filter(d => d.data.variant_id !== "dummy-root");
    const links = root.links().filter(l => l.source.data.variant_id !== "dummy-root");

    // Adjust positions: shift nodes down because there's no visible single root at the top
    nodes.forEach(d => {
      d.y = d.y - 40;
    });

    const g = svg.append("g").attr("transform", "translate(50, 40)");

    // Draw Links
    g.selectAll(".link")
      .data(links)
      .enter()
      .append("path")
      .attr("class", "link")
      .attr("fill", "none")
      .attr("stroke", "rgba(168, 85, 247, 0.2)")
      .attr("stroke-width", 2)
      .attr("d", d3.linkVertical()
        .x((d: any) => d.x)
        .y((d: any) => d.y)
      );

    // Draw Nodes
    const nodeGroups = g.selectAll(".node")
      .data(nodes)
      .enter()
      .append("g")
      .attr("class", "node")
      .attr("transform", (d: any) => `translate(${d.x},${d.y})`)
      .style("cursor", "pointer")
      .on("click", (event, d: any) => {
        onSelectVariant(d.data.variant_id);
      });

    // Node Circle
    nodeGroups.append("circle")
      .attr("r", (d: any) => Math.max(12, Math.min(24, Math.sqrt(d.data.report_count || 1) * 3)))
      .attr("fill", (d: any) => {
        if (d.data.variant_id === selectedVariantId) return "#c084fc";
        if (d.data.rt_status === "ESCALATING") return "var(--color-escalating)";
        if (d.data.rt_status === "STABLE") return "var(--color-stable)";
        return "var(--color-insufficient)";
      })
      .attr("stroke", (d: any) => {
        if (d.data.variant_id === selectedVariantId) return "#fff";
        return "rgba(255, 255, 255, 0.2)";
      })
      .attr("stroke-width", (d: any) => (d.data.variant_id === selectedVariantId ? 3 : 1))
      .style("filter", (d: any) => {
        if (d.data.rt_status === "ESCALATING") return "drop-shadow(0 0 6px var(--color-escalating))";
        if (d.data.rt_status === "STABLE") return "drop-shadow(0 0 4px var(--color-stable))";
        return "none";
      });

    // Node Labels
    nodeGroups.append("text")
      .attr("dy", (d: any) => {
        const radius = Math.max(12, Math.min(24, Math.sqrt(d.data.report_count || 1) * 3));
        return radius + 15;
      })
      .attr("text-anchor", "middle")
      .attr("fill", "#e2e8f0")
      .style("font-size", "0.75rem")
      .style("font-weight", (d: any) => (d.data.variant_id === selectedVariantId ? 700 : 500))
      .text((d: any) => {
        const label = d.data.label || "variant";
        return label.length > 18 ? label.substring(0, 16) + "..." : label;
      });

    // Node Counts (inside circle)
    nodeGroups.append("text")
      .attr("dy", "0.31em")
      .attr("text-anchor", "middle")
      .attr("fill", "#fff")
      .style("font-size", "0.7rem")
      .style("font-weight", "bold")
      .style("pointer-events", "none")
      .text((d: any) => d.data.report_count);

  }, [lineages, selectedVariantId]);

  return (
    <div className="glass-panel" style={{ flexGrow: 1, display: "flex", flexDirection: "column", gap: "1rem" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <h3 style={{ margin: 0, fontSize: "1.2rem", color: "var(--color-accent)" }}>
            🌿 Scam Mutation Forest (FR-7.1, Phase 2)
          </h3>
          <p style={{ margin: 0, fontSize: "0.85rem", opacity: 0.6 }}>
            Interactive family lineage tree. Node size indicates report count, color denotes Rt spreading velocity. Click to inspect.
          </p>
        </div>
        <div style={{ display: "flex", gap: "0.75rem", fontSize: "0.75rem" }}>
          <span style={{ display: "flex", alignItems: "center", gap: "0.25rem" }}>
            <span style={{ width: "8px", height: "8px", borderRadius: "50%", background: "var(--color-escalating)" }}></span>
            Escalating (Rt &gt; 1)
          </span>
          <span style={{ display: "flex", alignItems: "center", gap: "0.25rem" }}>
            <span style={{ width: "8px", height: "8px", borderRadius: "50%", background: "var(--color-stable)" }}></span>
            Stable
          </span>
          <span style={{ display: "flex", alignItems: "center", gap: "0.25rem" }}>
            <span style={{ width: "8px", height: "8px", borderRadius: "50%", background: "var(--color-insufficient)" }}></span>
            Insufficient Data
          </span>
        </div>
      </div>

      <div style={{ background: "rgba(0,0,0,0.15)", borderRadius: "12px", border: "1px solid var(--panel-border)", overflow: "hidden" }}>
        {!lineages || lineages.length === 0 ? (
          <div style={{ height: "450px", display: "flex", justifyContent: "center", alignItems: "center", opacity: 0.5 }}>
            No lineages detected. Ingest or replay data to generate lineage forest.
          </div>
        ) : (
          <svg ref={svgRef} style={{ width: "100%", display: "block" }} />
        )}
      </div>
    </div>
  );
}
