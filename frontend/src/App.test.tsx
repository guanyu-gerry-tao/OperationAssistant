import "@testing-library/jest-dom/vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import App from "./App";


afterEach(() => {
  vi.unstubAllGlobals();
});


describe("App", () => {
  it("renders incidents returned by the API", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        incidents: [
          {
            id: "INC-API",
            title: "API supplied incident",
            severity: "high",
            service: "api-service",
            status: "open",
            started_at: "2026-05-15T12:00:00Z",
            symptom: "The API supplied this incident.",
            customer_impact: "Operators can see API data.",
            likely_area: "api contract"
          }
        ],
      }),
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);

    const incidentList = screen.getByLabelText("Curated incidents");
    expect(await within(incidentList).findByText("API supplied incident")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith("/api/incidents");
    const detailPanel = screen.getByLabelText("Incident detail");
    expect(within(detailPanel).getByText("api contract")).toBeInTheDocument();
  });

  it("shows bundled seed incidents when the API is unavailable", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("API unavailable")));

    render(<App />);

    const incidentList = screen.getByLabelText("Curated incidents");
    expect(await within(incidentList).findByText("Payment workflow retries exhausted")).toBeInTheDocument();
    expect(within(incidentList).getByText("Inventory sync error rate increase")).toBeInTheDocument();
    expect(screen.getByText("Investigation workflow")).toBeInTheDocument();
  });

  it("updates the detail panel when a different incident is selected", async () => {
    const user = userEvent.setup();
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("API unavailable")));

    render(<App />);

    const incidentList = screen.getByLabelText("Curated incidents");
    await user.click(await within(incidentList).findByRole("button", {
      name: /Inventory sync error rate increase/,
    }));

    const detailPanel = screen.getByLabelText("Incident detail");
    expect(within(detailPanel).getByRole("heading", {
      name: "Inventory sync error rate increase",
    })).toBeInTheDocument();
    expect(within(detailPanel).getByText("partner feed validation")).toBeInTheDocument();
  });

  it("shows retrieval citations returned by the API", async () => {
    const user = userEvent.setup();
    vi.stubGlobal("fetch", vi.fn((url: string) => {
      if (url.startsWith("/api/incidents")) {
        return Promise.resolve({
          ok: false,
          json: async () => ({ incidents: [] }),
        });
      }

      return Promise.resolve({
        ok: true,
        json: async () => ({
          query: "checkout retry timeout",
          rewritten_query: "checkout retry timeout runbook incident",
          strategy: "hybrid_rerank_rewrite",
          chunks: [
            {
              chunk_id: "RB-1001-001",
              source_id: "RB-1001",
              title: "Workflow retry exhaustion checklist",
              snippet: "Check retry exhaustion before replay planning.",
              score: 0.92,
              metadata: { service: "checkout-workflow", incident_pattern: "failed workflow retry plan" },
              citation: {
                source_id: "RB-1001",
                source_title: "Workflow retry exhaustion checklist",
                source_path: "data/runbooks/workflow_retry_exhaustion.md",
                chunk_id: "RB-1001-001",
              },
            },
          ],
        }),
      });
    }));

    render(<App />);

    await user.click(await screen.findByRole("button", { name: "Run retrieval preview" }));

    expect(await screen.findByText("Workflow retry exhaustion checklist")).toBeInTheDocument();
    expect(screen.getByText("Source: data/runbooks/workflow_retry_exhaustion.md")).toBeInTheDocument();
    expect(screen.getByText("hybrid_rerank_rewrite")).toBeInTheDocument();
  });

  it("shows tool timeline, trace viewer, and verifier for an investigation", async () => {
    const user = userEvent.setup();
    vi.stubGlobal("fetch", vi.fn((url: string, options?: RequestInit) => {
      if (url.startsWith("/api/incidents")) {
        return Promise.resolve({
          ok: false,
          json: async () => ({ incidents: [] }),
        });
      }
      if (url === "/api/investigations" && options?.method === "POST") {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            trace_id: "trace-ui",
            incident_id: "INC-1001",
            question: "why did checkout fail",
            mode: "agent_tools",
            final_answer: "Observed fact from RB-1001 and failed event wf-checkout-7741.",
            retrieved_chunks: [
              {
                chunk_id: "RB-1001-001",
                source_id: "RB-1001",
                title: "Workflow retry exhaustion checklist",
                snippet: "Check retry exhaustion before replay planning.",
                score: 0.95,
                metadata: { service: "checkout-workflow" },
                citation: {
                  source_id: "RB-1001",
                  source_title: "Workflow retry exhaustion checklist",
                  source_path: "data/runbooks/workflow_retry_exhaustion.md",
                  chunk_id: "RB-1001-001",
                },
              },
            ],
            selected_tools: [
              {
                tool_name: "get_failed_events",
                arguments: { incident_id: "INC-1001" },
                reason: "Workflow questions need failed event evidence.",
              },
            ],
            tool_results: [
              {
                tool_name: "get_failed_events",
                arguments: { incident_id: "INC-1001" },
                permission_level: "read_only",
                output: {},
                output_summary: "failed event wf-checkout-7741 has 5 retries",
              },
            ],
            verifier: { status: "passed", grounded: true, checks: [] },
            trace: [
              {
                trace_id: "trace-ui",
                span_id: "span-01",
                parent_span_id: null,
                step_name: "triage",
                input_summary: "why did checkout fail",
                output_summary: "INC-1001 affects checkout-workflow",
                latency_ms: 0,
                token_cost_estimate: 0,
                error: null,
              },
              {
                trace_id: "trace-ui",
                span_id: "span-02",
                parent_span_id: "span-01",
                step_name: "tool_execute:get_failed_events",
                input_summary: "{ incident_id: INC-1001 }",
                output_summary: "failed event wf-checkout-7741 has 5 retries",
                latency_ms: 1.2,
                token_cost_estimate: 0,
                error: null,
              },
            ],
            latency_ms: 4.2,
          }),
        });
      }

      return Promise.resolve({
        ok: false,
        json: async () => ({}),
      });
    }));

    render(<App />);

    await user.click(await screen.findByRole("button", { name: "Run investigation" }));

    expect(await screen.findByText("Verifier passed")).toBeInTheDocument();
    expect(screen.getByLabelText("Tool call timeline")).toHaveTextContent("get_failed_events");
    expect(screen.getByLabelText("Trace viewer")).toHaveTextContent("tool_execute:get_failed_events");
    expect(screen.getByText("Workflow retry exhaustion checklist")).toBeInTheDocument();
  });
});
