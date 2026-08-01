# Feature Specification: MCP Integration Layer

**Feature Branch**: `04-mcp-integrations`

**Created**: 2026-08-01

**Status**: Active

**Constitution Reference**: `.specify/memory/constitution.md` — Article II §2 (Scoped Ephemeral Calls), Article I §2 (Deterministic Schemas)

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Create Todoist Task via MCP Gateway (Priority: P1)

Alex wants ALOS to automatically create a Todoist task with a due date. The MCP Gateway must translate a typed `TodoistTaskCreate` Pydantic payload into a successful tool call and return a structured response with a `task_id`.

**Acceptance Scenarios**:

1. **Given** a `TodoistTaskCreate(title="Schedule quarterly review", due_date="2026-08-05")`, **When** `MCPGateway.execute_tool("todoist_create_task", payload)` is called, **Then** response `status == "SUCCESS"` and `task_id is not None`.

---

### User Story 2 — Query Google Calendar Events via MCP Gateway (Priority: P1)

Alex's morning sweep fetches today's calendar events. The MCP Gateway must return a structured list of event objects.

**Acceptance Scenarios**:

1. **Given** a date `"2026-08-01"`, **When** `execute_tool("google_calendar_list_events", {"date": "2026-08-01"})` is called, **Then** response `status == "SUCCESS"` and `events` is a list.

---

### Edge Cases

- What if the tool name is unknown? Return `status: UNKNOWN_TOOL` without raising an exception.
- What if the API is unavailable? In mock mode, return deterministic fixture data. In live mode, return `status: ERROR` with error message.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `MCPGateway.execute_tool(tool_name, payload)` MUST accept typed dict payloads and return a structured dict response.
- **FR-002**: All responses MUST include a `status` key with values `SUCCESS | ERROR | UNKNOWN_TOOL`.
- **FR-003**: `todoist_create_task` MUST return `task_id` on success.
- **FR-004**: `google_calendar_list_events` MUST return `events: List` on success.
- **FR-005**: Unknown tool names MUST return `status: UNKNOWN_TOOL` without raising exceptions.
- **FR-006**: `MCPGateway` MUST support `mock_mode=True` for test isolation (no real API calls).

---

## Success Criteria *(mandatory)*

- **SC-001**: All 5 tool types return `status: SUCCESS` in mock mode.
- **SC-002**: Zero exceptions raised for any supported or unsupported tool call.
- **SC-003**: Response schema is consistent and parseable without type errors.

---

## Assumptions

- In `mock_mode=True`, all responses use deterministic fixture data.
- Real MCP server integration (OAuth, endpoint routing) is out of scope for this version.
- The gateway is the only component that calls external APIs; all other components call the gateway.
