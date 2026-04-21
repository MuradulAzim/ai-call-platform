# WBOM Workflow API Migration Notes

Date: 2026-04-21
Audience: Frontend team, integration/API consumers
Scope: Workflow endpoints under /api/wbom/workflow

## Summary

This update standardizes workflow API contracts with explicit OpenAPI models from a single source:
- All workflow response schemas now come from models.py.
- Legacy openapi_models.py has been removed.
- Two workflow action endpoints changed from query-parameter input to JSON request body input.

## Breaking Changes

### 1) Request format changed (query -> JSON body)

The following endpoints no longer accept operational input via query parameters:

- POST /api/wbom/workflow/cases/{case_id}/status
- POST /api/wbom/workflow/cases/{case_id}/escalate

New expected payloads:

POST /cases/{case_id}/status

```json
{
  "new_status": "resolved",
  "changed_by": "ops-admin",
  "reason": "Issue fixed"
}
```

POST /cases/{case_id}/escalate

```json
{
  "action": "escalate",
  "actor": "ops-admin",
  "note": "Need supervisor review",
  "snooze_minutes": 30
}
```

### 2) OpenAPI source consolidation

- Removed: openapi_models.py
- Source of truth: models.py
- Integration impact: schema generation, API clients, and docs should use current OpenAPI output only.

## Non-breaking Changes

The following workflow endpoints keep the same behavior and route paths while now having explicit response_model declarations:

- GET /api/wbom/workflow/cases
- GET /api/wbom/workflow/cases/{case_id}
- GET /api/wbom/workflow/escalations/monitor
- GET /api/wbom/workflow/approvals/pending
- POST /api/wbom/workflow/approvals/task/{workflow_task_id}/approve
- POST /api/wbom/workflow/approvals/task/{workflow_task_id}/reject
- POST /api/wbom/workflow/approvals/payment/{staging_id}/approve

## Action Checklist For Teams

1. Update frontend API calls for the two changed POST endpoints to send application/json bodies.
2. Regenerate any typed API clients from the latest OpenAPI spec.
3. Validate status-change and escalation forms against the new body fields.
4. Confirm 400/422 handling in UI for invalid payloads and validation errors.
5. Remove any hardcoded assumptions tied to old query-parameter format.

## Quick Regression Smoke

Suggested quick checks after deployment:

1. Transition an open case to resolved via POST /cases/{id}/status with JSON body.
2. Trigger escalate and snooze actions via POST /cases/{id}/escalate.
3. Verify approvals list still renders mixed task/payment items.
4. Verify case detail still returns case + event/task timeline as expected.

## Notes

- Existing workflow tests pass with the new body contract.
- No route path changes were introduced in this update.
