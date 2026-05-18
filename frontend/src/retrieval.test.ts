import { afterEach, describe, expect, it, vi } from "vitest";

import { fetchRetrievalPreview } from "./api";


afterEach(() => {
  vi.unstubAllGlobals();
});


describe("fetchRetrievalPreview", () => {
  it("calls the retrieval preview endpoint with the improved strategy by default", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        query: "checkout retry timeout",
        rewritten_query: "checkout retry timeout runbook incident",
        strategy: "hybrid_rerank_rewrite",
        chunks: [],
      }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const preview = await fetchRetrievalPreview("checkout retry timeout");

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/retrieval?query=checkout+retry+timeout&strategy=hybrid_rerank_rewrite&top_k=3",
    );
    expect(preview.strategy).toBe("hybrid_rerank_rewrite");
  });
});
