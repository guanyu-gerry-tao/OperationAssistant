---
source_id: RB-1001
title: Workflow retry exhaustion checklist
service: checkout-workflow
incident_pattern: failed workflow retry plan
severity_hint: high
---

# Workflow retry exhaustion checklist

Use this runbook when checkout payments are stuck after the retry budget is exhausted. Confirm whether the workflow retried the same payment step until the timeout window closed, then compare the failed order count with the downstream payment provider status.

The first safe action is evidence gathering, not replay. Check retry counters, workflow timeout timestamps, payment provider responses, and the order state transition log. If the provider already accepted the payment, do not replay the charge. Escalate to an operator approval flow before any manual replay or state repair.

Useful signals include repeated retry exhaustion events, payment timeout errors, stuck pending orders, and mismatched confirmation events. The expected citation for this incident is this runbook plus the matching workflow retry metrics.
