import "@testing-library/jest-dom/vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import App from "./App";


afterEach(() => {
  vi.unstubAllGlobals();
});


describe("App", () => {
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
});
