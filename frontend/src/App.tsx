import { Activity, Database, FileSearch, Server, ShieldCheck } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { fetchIncidents, fetchRetrievalPreview, seedIncidents } from "./api";
import type { Incident, Investigation, RetrievalPreview } from "./types";
import "./styles.css";


/** Build the honest M1 placeholder before retrieval and tool calls exist. */
function buildPlaceholderInvestigation(incident: Incident): Investigation {
  return {
    status: "placeholder",
    summary:
      "M1 provides the runnable incident shell. Retrieval, citations, tool calls, and verification are planned for later milestones.",
    primary_signal: incident.symptom,
    next_capability: "M2 retrieval and citations"
  };
}


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


/** Render the M1 incident investigation workspace shell. */
export default function App() {
  const [incidents, setIncidents] = useState<Incident[]>(seedIncidents);
  const [selectedIncidentId, setSelectedIncidentId] = useState(seedIncidents[0].id);
  const [retrievalQuery, setRetrievalQuery] = useState("why did checkout payment retries exhaust");
  const [retrievalPreview, setRetrievalPreview] = useState<RetrievalPreview | null>(null);
  const [retrievalStatus, setRetrievalStatus] = useState<"idle" | "loading" | "error">("idle");

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

  // M1 computes the placeholder locally because retrieval has not been implemented yet.
  const investigation = buildPlaceholderInvestigation(selectedIncident);

  async function runRetrievalPreview() {
    setRetrievalStatus("loading");
    try {
      const preview = await fetchRetrievalPreview(retrievalQuery);
      setRetrievalPreview(preview);
      setRetrievalStatus("idle");
    } catch {
      setRetrievalStatus("error");
    }
  }

  return (
    <main className="app-shell">
      <section className="workspace-header">
        <div>
          <p className="eyebrow">Operations Assistant</p>
          <h1>Incident investigation workspace</h1>
        </div>
        <div className="status-strip" aria-label="M1 stack status">
          <span><Server size={16} /> FastAPI</span>
          <span><Activity size={16} /> React</span>
          <span><Database size={16} /> Postgres + Redis</span>
          <span><ShieldCheck size={16} /> Seed data</span>
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
              onClick={() => setSelectedIncidentId(incident.id)}
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

          <div className="investigation-panel">
            <div className="panel-heading">
              <h3>Investigation placeholder</h3>
              <span>{investigation.status}</span>
            </div>
            <p>{investigation.summary}</p>
            <div className="signal-box">
              <span>Primary signal</span>
              <strong>{investigation.primary_signal}</strong>
            </div>
            <p className="next-capability">{investigation.next_capability}</p>
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
