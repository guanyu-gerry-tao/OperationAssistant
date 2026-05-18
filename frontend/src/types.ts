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

/** Read-only tool call selected by the M3 investigation workflow. */
export type ToolCall = {
  tool_name: string;
  arguments: Record<string, string>;
  reason: string;
};

/** Read-only sample tool output rendered in the tool timeline. */
export type ToolResult = {
  tool_name: string;
  arguments: Record<string, string>;
  permission_level: "read_only";
  output: Record<string, unknown>;
  output_summary: string;
};

/** One OpenTelemetry-style span captured during an investigation run. */
export type TraceSpan = {
  trace_id: string;
  span_id: string;
  parent_span_id: string | null;
  step_name: string;
  input_summary: string;
  output_summary: string;
  latency_ms: number;
  token_cost_estimate: number;
  error: string | null;
};

/** Product verifier check shown in the investigation panel. */
export type VerificationCheck = {
  name: string;
  passed: boolean;
  detail: string;
};

/** Product verifier result for the runtime final answer. */
export type VerificationResult = {
  status: string;
  grounded: boolean;
  checks: VerificationCheck[];
};

/** API response for one synchronous M3 investigation run. */
export type InvestigationRun = {
  trace_id: string;
  incident_id: string;
  question: string;
  mode: "rag_only" | "agent_tools";
  final_answer: string;
  retrieved_chunks: RetrievalChunk[];
  selected_tools: ToolCall[];
  tool_results: ToolResult[];
  verifier: VerificationResult;
  trace: TraceSpan[];
  latency_ms: number;
};
