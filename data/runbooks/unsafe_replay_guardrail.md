---
source_id: RB-1004
title: Unsafe replay guardrail note
service: operations-control
incident_pattern: unsafe replay request
severity_hint: high
---

# Unsafe replay guardrail note

Use this note when an operator asks to replay a workflow or repair state while customer-visible side effects may already have happened. The system should gather evidence first and require explicit approval before any action that can create a duplicate payment, duplicate notification, or irreversible state transition.

The retrieval layer should cite the relevant runbook and explain why the replay is sensitive. It should not execute the replay, call tools, or claim that a repair happened.
