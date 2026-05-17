import type { Incident } from "./types";

export const seedIncidents: Incident[] = [
  {
    id: "INC-1001",
    title: "Payment workflow retries exhausted",
    severity: "high",
    service: "checkout-workflow",
    status: "open",
    started_at: "2026-05-10T09:15:00Z",
    symptom: "Checkout payments are stuck after the retry budget is exhausted.",
    customer_impact: "Some orders remain pending instead of moving to confirmation.",
    likely_area: "workflow retry handling"
  },
  {
    id: "INC-1002",
    title: "Inventory sync error rate increase",
    severity: "medium",
    service: "inventory-sync",
    status: "investigating",
    started_at: "2026-05-11T14:40:00Z",
    symptom: "Inventory sync failures increased after a partner feed schema change.",
    customer_impact: "Product availability can be stale for a small set of items.",
    likely_area: "partner feed validation"
  },
  {
    id: "INC-1003",
    title: "Notification delivery latency spike",
    severity: "medium",
    service: "notification-worker",
    status: "mitigated",
    started_at: "2026-05-12T20:05:00Z",
    symptom: "Email notification latency exceeded the service objective during a queue backlog.",
    customer_impact: "Users received delayed status notifications.",
    likely_area: "worker queue throughput"
  }
];

/** Fetch seed incidents from the local API and fall back to bundled demo data. */
export async function fetchIncidents(): Promise<Incident[]> {
  try {
    const response = await fetch("/api/incidents");
    if (!response.ok) {
      return seedIncidents;
    }

    const payload = (await response.json()) as { incidents: Incident[] };
    return payload.incidents;
  } catch {
    return seedIncidents;
  }
}
