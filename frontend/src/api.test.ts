import { afterEach, describe, expect, it, vi } from "vitest";

import { createInvestigation, fetchIncidents, seedIncidents } from "./api";


afterEach(() => {
  vi.unstubAllGlobals();
});


describe("fetchIncidents", () => {
  it("falls back to bundled seed incidents for non-ok responses", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: false,
      json: async () => ({ incidents: [] }),
    }));

    const incidents = await fetchIncidents();

    expect(incidents).toBe(seedIncidents);
  });

  it("falls back to bundled seed incidents for empty API payloads", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ incidents: [] }),
    }));

    const incidents = await fetchIncidents();

    expect(incidents).toBe(seedIncidents);
  });
});


describe("createInvestigation", () => {
  it("posts the selected incident, question, and mode", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        trace_id: "trace-test",
        incident_id: "INC-1001",
        question: "why did checkout fail",
        mode: "agent_tools",
        final_answer: "answer",
        retrieved_chunks: [],
        selected_tools: [],
        tool_results: [],
        verifier: { status: "passed", grounded: true, checks: [] },
        trace: [],
        latency_ms: 1,
      }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await createInvestigation("INC-1001", "why did checkout fail", "agent_tools");

    expect(result.trace_id).toBe("trace-test");
    expect(fetchMock).toHaveBeenCalledWith("/api/investigations", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        incident_id: "INC-1001",
        question: "why did checkout fail",
        mode: "agent_tools",
      }),
    });
  });
});
