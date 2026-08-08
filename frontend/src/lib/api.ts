const BASE = "/api";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(`GET ${path} failed: ${res.status}`);
  return res.json() as Promise<T>;
}

export interface StatusResponse {
  status: string;
}

export interface FeedPost {
  id: string;
  createdAt: string;
  title: string;
  technique_layer: string;
  variant_layer: string;
  action_steps: string[];
  language: string;
  target_segment: string;
  variant_id: string;
  supporting_report_count: number;
  rt_at_publish: number;
  rt_lower_bound: number;
  template_assisted: boolean;
}

export const api = {
  status: () => get<StatusResponse>("/status"),
  feed: () => get<{ posts: FeedPost[] }>("/feed"),
  lineages: () => get<{ lineages: unknown[] }>("/lineages"),
  backtest: () => get<{ waves: unknown[] }>("/backtest"),
  trace: () => get<{ events: unknown[] }>("/trace"),
};
