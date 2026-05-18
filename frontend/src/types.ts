/** Curated incident record shown in the M1 investigation workspace. */
export type Incident = {
  id: string;
  title: string;
  severity: "low" | "medium" | "high" | "critical";
  service: string;
  status: string;
  started_at: string;
  symptom: string;
  customer_impact: string;
  likely_area: string;
};

/** Static M1 investigation summary used before retrieval and tool calls exist. */
export type Investigation = {
  status: string;
  summary: string;
  primary_signal: string;
  next_capability: string;
};

/** Source citation attached to one retrieved runbook chunk. */
export type RetrievalCitation = {
  source_id: string;
  source_title: string;
  source_path: string;
  chunk_id: string;
};

/** Ranked retrieval result rendered in the citation preview panel. */
export type RetrievalChunk = {
  chunk_id: string;
  source_id: string;
  title: string;
  snippet: string;
  score: number;
  metadata: Record<string, string>;
  citation: RetrievalCitation;
};

/** API response for one retrieval preview request. */
export type RetrievalPreview = {
  query: string;
  rewritten_query: string;
  strategy: "lexical" | "hybrid_rerank_rewrite";
  chunks: RetrievalChunk[];
  latency_ms?: number;
};
