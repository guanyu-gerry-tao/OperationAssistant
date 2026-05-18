---
source_id: RB-1003
title: Notification queue latency triage
service: notification-worker
incident_pattern: worker queue throughput
severity_hint: medium
---

# Notification queue latency triage

Use this runbook when notification delivery latency spikes during a worker queue backlog. Compare queue depth, oldest message age, worker throughput, retry rate, and downstream email provider latency.

Start with read-only checks. Confirm whether workers are alive, whether the queue is growing faster than consumers can drain it, and whether failures are retrying too aggressively. If the provider is slow, rate-limit retries instead of increasing concurrency without a capacity check.

Useful signals include queue backlog, high oldest-message age, delayed notification delivery, retry storms, and worker throughput drops.
