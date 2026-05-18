import { afterEach, describe, expect, it, vi } from "vitest";

import { fetchIncidents, seedIncidents } from "./api";


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
