---
source_id: RB-1002
title: Partner feed validation failure runbook
service: inventory-sync
incident_pattern: partner feed validation
severity_hint: medium
---

# Partner feed validation failure runbook

Use this runbook when inventory sync errors increase after a partner feed schema change. Start by comparing the latest accepted feed sample with the rejected records and the validation error distribution.

The safest investigation path is to identify the changed field, confirm whether the parser or schema validator rejected the payload, and isolate the affected partner IDs. Do not disable validation globally. If a temporary allowlist is needed, scope it to the affected partner and document the expected rollback.

Useful signals include schema validation errors, partner feed version changes, rejected inventory updates, and stale availability for a subset of items.
