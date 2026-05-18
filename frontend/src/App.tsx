import {
  Activity,
  BarChart3,
  Bot,
  CheckCircle2,
  Database,
  FileSearch,
  GitBranch,
  Server,
  Wrench,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import {
  createInvestigation,
  decideApproval,
  fetchIncidents,
  fetchLatestEvalSummary,
  fetchRetrievalPreview,
  seedIncidents
} from "./api";
import type { ApprovalRequest, Incident, InvestigationRun, LatestEvalSummary, RetrievalPreview } from "./types";
import "./styles.css";


/** Render seed timestamps in a compact, readable form for the UI shell. */
function formatStartedAt(value: string): string {
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    timeZoneName: "short"
  }).format(new Date(value));
}


/** Build a useful default investigation question for the selected incident. */
function buildDefaultQuestion(incident: Incident): string {
  return `why did ${incident.service} show ${incident.likely_area}`;
}


/** Render one compact quality metric card from the latest eval summary. */
function renderQualityMetric(label: string, value: number | undefined) {
  const displayValue = value === undefined ? "n/a" : value.toFixed(2);

  return (
    <article className="quality-metric" key={label}>
      <span>{label}</span>
      <strong>{displayValue}</strong>
    </article>
  );
}


/** Render the incident investigation workspace. */
export default function App() {
  const [incidents, setIncidents] = useState<Incident[]>(seedIncidents);
  const [selectedIncidentId, setSelectedIncidentId] = useState(seedIncidents[0].id);
  const [retrievalQuery, setRetrievalQuery] = useState("why did checkout payment retries exhaust");
  const [retrievalPreview, setRetrievalPreview] = useState<RetrievalPreview | null>(null);
  const [retrievalStatus, setRetrievalStatus] = useState<"idle" | "loading" | "error">("idle");
  const [investigationQuestion, setInvestigationQuestion] = useState(buildDefaultQuestion(seedIncidents[0]));
  const [investigationMode, setInvestigationMode] = useState<InvestigationRun["mode"]>("agent_tools");
  const [investigationRun, setInvestigationRun] = useState<InvestigationRun | null>(null);
  const [investigationStatus, setInvestigationStatus] = useState<"idle" | "loading" | "error">("idle");
  const [approvalRequest, setApprovalRequest] = useState<ApprovalRequest | null>(null);
  const [approvalStatus, setApprovalStatus] = useState<"idle" | "loading" | "error">("idle");
  const [latestEvalSummary, setLatestEvalSummary] = useState<LatestEvalSummary | null>(null);

  useEffect(() => {
    // Replace bundled demo data with API data when the backend is available.
    void fetchIncidents().then((nextIncidents) => {
      setIncidents(nextIncidents);
      if (nextIncidents.length > 0) {
        // Select the first API incident so the detail panel stays in sync with the list.
        setSelectedIncidentId(nextIncidents[0].id);
      }
    });
  }, []);

  useEffect(() => {
    // Load the latest eval artifact when scripts/eval_all.py has produced one locally.
    void fetchLatestEvalSummary().then((summary) => {
      setLatestEvalSummary(summary);
    });
  }, []);

  const selectedIncident = useMemo(() => {
    // Re-resolve the selected incident whenever the list or selected id changes.
    const match = incidents.find((incident) => incident.id === selectedIncidentId);
    if (match !== undefined) {
      return match;
    }

    // Fall back to the first row if the current id disappeared after an API refresh.
    return incidents[0];
  }, [incidents, selectedIncidentId]);

  if (selectedIncident === undefined) {
    return (
      <main className="app-shell empty-state">
        <h1>Incident investigation workspace</h1>
        <p>No seed incidents are available.</p>
      </main>
    );
  }

  /** Load ranked runbook chunks for the current preview query. */
  async function runRetrievalPreview() {
    // Show loading state while the FastAPI retrieval endpoint ranks chunks.
    setRetrievalStatus("loading");
    try {
      const preview = await fetchRetrievalPreview(retrievalQuery);
      setRetrievalPreview(preview);
      setRetrievalStatus("idle");
    } catch {
      // Preserve the last successful preview and only mark the new request as failed.
      setRetrievalStatus("error");
    }
  }

  /** Run the M3 workflow and render citations, tools, verifier, and trace. */
  async function runInvestigation() {
    // Show loading state while the FastAPI workflow executes synchronously.
    setInvestigationStatus("loading");
    try {
      const result = await createInvestigation(
        selectedIncident.id,
        investigationQuestion,
        investigationMode,
      );
      setInvestigationRun(result);
      setApprovalRequest(result.approval_request ?? null);
      setInvestigationStatus("idle");
    } catch {
      // Preserve the last successful investigation so operators can still inspect it.
      setInvestigationStatus("error");
    }
  }

  /** Select an incident and reset investigation inputs to that incident's context. */
  function selectIncident(incident: Incident) {
    setSelectedIncidentId(incident.id);
    setInvestigationQuestion(buildDefaultQuestion(incident));
    setInvestigationRun(null);
    setApprovalRequest(null);
  }

  /** Submit a human approval decision and update the modal state. */
  async function submitApprovalDecision(decision: "approve" | "reject") {
    if (approvalRequest === null) {
      return;
    }

    // Keep the modal visible while the audit endpoint records the decision.
    setApprovalStatus("loading");
    try {
      const nextApprovalRequest = await decideApproval(approvalRequest.approval_id, decision);
      setApprovalRequest(nextApprovalRequest);
      setApprovalStatus("idle");
    } catch {
      setApprovalStatus("error");
    }
  }

  return (
    <main className="app-shell">
      <section className="workspace-header">
        <div>
          <p className="eyebrow">Operations Assistant</p>
          <h1>Incident investigation workspace</h1>
        </div>
        <div className="status-strip" aria-label="Stack status">
          <span><Server size={16} /> FastAPI</span>
          <span><Activity size={16} /> React</span>
          <span><Database size={16} /> Postgres + Redis</span>
          <span><Bot size={16} /> Agent tools</span>
          <span><GitBranch size={16} /> Traces</span>
        </div>
      </section>

      <section className="workspace-grid">
        <aside className="incident-list" aria-label="Curated incidents">
          <div className="panel-heading">
            <h2>Seed incidents</h2>
            <span>{incidents.length} loaded</span>
          </div>
          {incidents.map((incident) => (
            <button
              className={incident.id === selectedIncident.id ? "incident-row active" : "incident-row"}
              key={incident.id}
              onClick={() => selectIncident(incident)}
              type="button"
            >
              <span className={`severity severity-${incident.severity}`}>{incident.severity}</span>
              <strong>{incident.title}</strong>
              <small>{incident.service}</small>
            </button>
          ))}
        </aside>

        <section className="incident-detail" aria-label="Incident detail">
          <div className="detail-header">
            <div>
              <p className="eyebrow">{selectedIncident.id}</p>
              <h2>{selectedIncident.title}</h2>
            </div>
            <span className="detail-status">{selectedIncident.status}</span>
          </div>

          <dl className="detail-facts">
            <div>
              <dt>Started</dt>
              <dd>{formatStartedAt(selectedIncident.started_at)}</dd>
            </div>
            <div>
              <dt>Likely area</dt>
              <dd>{selectedIncident.likely_area}</dd>
            </div>
            <div>
              <dt>Customer impact</dt>
              <dd>{selectedIncident.customer_impact}</dd>
            </div>
          </dl>

          <section className="eval-summary-panel" aria-label="Latest eval summary">
            <div className="panel-heading">
              <h3>Latest eval run</h3>
              <span>{latestEvalSummary?.arm ?? "not run"}</span>
            </div>
            {latestEvalSummary !== null ? (
              <>
                <div className="eval-run-meta">
                  <BarChart3 size={18} />
                  <strong>{latestEvalSummary.run_id}</strong>
                  <span>{latestEvalSummary.case_count} cases</span>
                </div>
                <div className="quality-metric-grid">
                  {renderQualityMetric("Retrieval precision", latestEvalSummary.metrics.retrieval_precision)}
                  {renderQualityMetric("Tool selection", latestEvalSummary.metrics.tool_selection_accuracy)}
                  {renderQualityMetric("Grounded answer rate", latestEvalSummary.metrics.grounded_answer_rate)}
                  {renderQualityMetric("Hallucination rate", latestEvalSummary.metrics.hallucination_rate)}
                  {renderQualityMetric("Cache hit rate", latestEvalSummary.metrics.cache_hit_rate)}
                </div>
                <div className="version-strip">
                  <span>Prompt</span>
                  <strong>{latestEvalSummary.version_snapshot.prompt_versions?.investigation_answer ?? "unversioned"}</strong>
                  <span>{latestEvalSummary.version_snapshot.model_profile ?? "local model"}</span>
                </div>
              </>
            ) : (
              <p className="muted-text">Run the full eval script to populate quality gate metrics.</p>
            )}
          </section>

          <div className="investigation-panel" aria-label="Investigation workflow">
            <div className="panel-heading">
              <h3>Investigation workflow</h3>
              <span>{investigationRun?.mode ?? investigationMode}</span>
            </div>
            <div className="investigation-controls">
              <label htmlFor="investigation-question">Question</label>
              <textarea
                id="investigation-question"
                onChange={(event) => setInvestigationQuestion(event.target.value)}
                value={investigationQuestion}
              />
              <div className="segmented-control" aria-label="Investigation mode">
                <button
                  className={investigationMode === "agent_tools" ? "active" : ""}
                  onClick={() => setInvestigationMode("agent_tools")}
                  type="button"
                >
                  <Wrench size={16} />
                  Agent tools
                </button>
                <button
                  className={investigationMode === "rag_only" ? "active" : ""}
                  onClick={() => setInvestigationMode("rag_only")}
                  type="button"
                >
                  <FileSearch size={16} />
                  RAG only
                </button>
              </div>
              <button className="primary-action" onClick={runInvestigation} type="button">
                <Bot size={16} />
                Run investigation
              </button>
            </div>
            {investigationStatus === "error" ? (
              <p className="error-text">Investigation workflow is unavailable.</p>
            ) : null}
            {investigationRun !== null ? (
              <div className="investigation-results">
                {investigationRun.safety_decision != null ? (
                  <div className={`guardrail-badge guardrail-${investigationRun.safety_decision.decision}`}>
                    <CheckCircle2 size={16} />
                    <strong>
                      {investigationRun.safety_decision.decision === "approval_required"
                        ? "Approval required"
                        : `Guardrail ${investigationRun.safety_decision.decision}`}
                    </strong>
                    <span>{investigationRun.safety_decision.reasons.join(", ") || "no risks detected"}</span>
                  </div>
                ) : null}
                {investigationRun.verifier != null ? (
                  <div className={`verifier-badge verifier-${investigationRun.verifier.status}`}>
                    <CheckCircle2 size={16} />
                    <strong>Verifier {investigationRun.verifier.status}</strong>
                    <span>{investigationRun.trace_id}</span>
                  </div>
                ) : null}
                {approvalRequest !== null ? (
                  <section className="approval-modal" aria-label="Approval request">
                    <div>
                      <span>{approvalRequest.permission_level}</span>
                      <h4>
                        Approval {approvalRequest.status}
                      </h4>
                      <p>{approvalRequest.risk_reason}</p>
                      <small>{approvalRequest.approval_id}</small>
                    </div>
                    {approvalRequest.status === "pending" ? (
                      <div className="approval-actions">
                        <button onClick={() => void submitApprovalDecision("approve")} type="button">
                          Approve
                        </button>
                        <button onClick={() => void submitApprovalDecision("reject")} type="button">
                          Reject
                        </button>
                      </div>
                    ) : (
                      <p className="muted-text">
                        Decided by {approvalRequest.decided_by} · {approvalRequest.note}
                      </p>
                    )}
                    {approvalStatus === "error" ? (
                      <p className="error-text">Approval decision could not be saved.</p>
                    ) : null}
                  </section>
                ) : null}
                <div className="answer-box">
                  <span>Final answer</span>
                  <p>{investigationRun.final_answer}</p>
                </div>
                <div className="timeline-grid">
                  <section aria-label="Tool call timeline">
                    <h4>Tool call timeline</h4>
                    {investigationRun.tool_results.length > 0 ? (
                      investigationRun.tool_results.map((toolResult) => (
                        <article className="timeline-item" key={`${toolResult.tool_name}-${toolResult.output_summary}`}>
                          <span>{toolResult.permission_level}</span>
                          <strong>{toolResult.tool_name}</strong>
                          <p>{toolResult.output_summary}</p>
                        </article>
                      ))
                    ) : (
                      <p className="muted-text">Baseline mode did not call read-only tools.</p>
                    )}
                  </section>
                  <section aria-label="Trace viewer">
                    <h4>Trace viewer</h4>
                    {investigationRun.trace.map((span) => (
                      <article className="trace-row" key={span.span_id}>
                        <div>
                          <strong>{span.step_name}</strong>
                          <span>{span.latency_ms.toFixed(2)} ms</span>
                        </div>
                        <p>{span.output_summary}</p>
                      </article>
                    ))}
                  </section>
                </div>
                <div className="retrieval-results">
                  {investigationRun.retrieved_chunks.map((chunk) => (
                    <article className="retrieval-result" key={`investigation-${chunk.chunk_id}`}>
                      <div>
                        <h4>{chunk.title}</h4>
                        <span>{chunk.source_id} · score {chunk.score.toFixed(2)}</span>
                      </div>
                      <p>{chunk.snippet}</p>
                      <small>Source: {chunk.citation.source_path}</small>
                    </article>
                  ))}
                </div>
              </div>
            ) : (
              <div className="signal-box">
                <span>Primary signal</span>
                <strong>{selectedIncident.symptom}</strong>
              </div>
            )}
          </div>

          <div className="retrieval-panel" aria-label="Retrieval preview">
            <div className="panel-heading">
              <h3>Retrieval preview</h3>
              <span>{retrievalPreview?.strategy ?? "hybrid_rerank_rewrite"}</span>
            </div>
            <div className="retrieval-controls">
              <label htmlFor="retrieval-query">Query</label>
              <textarea
                id="retrieval-query"
                onChange={(event) => setRetrievalQuery(event.target.value)}
                value={retrievalQuery}
              />
              <button className="primary-action" onClick={runRetrievalPreview} type="button">
                <FileSearch size={16} />
                Run retrieval preview
              </button>
            </div>
            {retrievalStatus === "error" ? (
              <p className="error-text">Retrieval preview is unavailable.</p>
            ) : null}
            {retrievalPreview !== null ? (
              <div className="retrieval-results">
                <div className="query-rewrite">
                  <span>Rewritten query</span>
                  <strong>{retrievalPreview.rewritten_query}</strong>
                </div>
                {retrievalPreview.chunks.map((chunk) => (
                  <article className="retrieval-result" key={chunk.chunk_id}>
                    <div>
                      <h4>{chunk.title}</h4>
                      <span>{chunk.source_id} · score {chunk.score.toFixed(2)}</span>
                    </div>
                    <p>{chunk.snippet}</p>
                    <small>Source: {chunk.citation.source_path}</small>
                  </article>
                ))}
              </div>
            ) : null}
          </div>
        </section>
      </section>
    </main>
  );
}
