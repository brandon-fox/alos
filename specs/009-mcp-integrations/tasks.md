# Tasks: MCP Integration Layer

**Input**: `specs/009-mcp-integrations/spec.md`, `specs/009-mcp-integrations/plan.md`

## Phase 1: User Story 1+2 — Gateway Implementation (P1)

### Tests (TDD — Write FIRST)

- [x] T001 [US1] `test_04_mcp_gateway_todoist_and_google` — assert task_id not None, events is list — **confirm RED → GREEN**

### Implementation

- [x] T002 [US1] Implement `MCPGateway.__init__` with `mock_mode` flag
- [x] T003 [US1] Implement `todoist_create_task` handler with uuid task_id
- [x] T004 [US2] Implement `google_calendar_list_events` handler returning fixture events
- [x] T005 [P] Implement `google_calendar_create_event`, `email_create_draft`, `web_search` handlers
- [x] T006 [P] Implement `UNKNOWN_TOOL` fallback response
- [x] T007 Run pytest — **confirm GREEN**

## Phase 2: Polish

- [x] T008 [P] Move Gherkin to `tests/features/04_mcp_integrations.feature`
- [x] T009 [P] Verify checklist requirements met
