# Implementation Plan: MCP Integration Layer

**Branch**: `04-mcp-integrations` | **Date**: 2026-08-01 | **Spec**: [spec.md](./spec.md)

## Constitution Check

- ✅ Article II §2 — API calls are bounded, least-privilege, strictly functional
- ✅ Article I §2 — All payloads are Pydantic-validated before dispatch

## API Contract

```python
class MCPGateway:
    def __init__(self, mock_mode: bool = True): ...
    def execute_tool(self, tool_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        # Returns: {"status": "SUCCESS|ERROR|UNKNOWN_TOOL", ...tool-specific fields}
```

## Tool Response Schemas

| Tool Name | Success Response Fields |
|---|---|
| `todoist_create_task` | `status, tool, task_id, title, due_date` |
| `google_calendar_list_events` | `status, tool, date, events: List` |
| `google_calendar_create_event` | `status, tool, event_id, title, start_time, end_time` |
| `email_create_draft` | `status, tool, draft_id, to, subject` |
| `web_search` | `status, tool, query, results: List` |
| Unknown | `status: UNKNOWN_TOOL, tool, payload` |
