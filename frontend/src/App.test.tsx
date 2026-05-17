import "@testing-library/jest-dom/vitest";
import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import App from "./App";


describe("App", () => {
  it("shows the incident list and selected investigation placeholder", async () => {
    render(<App />);

    const incidentList = screen.getByLabelText("Curated incidents");
    expect(await within(incidentList).findByText("Payment workflow retries exhausted")).toBeInTheDocument();
    expect(within(incidentList).getByText("Inventory sync error rate increase")).toBeInTheDocument();
    expect(screen.getByText("Investigation placeholder")).toBeInTheDocument();
  });
});
