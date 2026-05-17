export type Incident = {
  id: string;
  title: string;
  severity: "low" | "medium" | "high" | "critical";
  service: string;
  status: string;
  started_at: string;
  symptom: string;
  customer_impact: string;
  likely_area: string;
};

export type Investigation = {
  status: string;
  summary: string;
  primary_signal: string;
  next_capability: string;
};
