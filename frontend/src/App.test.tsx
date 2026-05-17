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
    expect(screen.getByText("Investigation placeholder")).toBeInTheDocument();
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
});
