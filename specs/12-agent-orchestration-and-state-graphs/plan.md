# Architecture Plan: Agent Orchestration & State Graphs (Spec 12)

```mermaid
stateDiagram-v2
    [*] --> ContextAssembly
    ContextAssembly --> PlannerNode
    PlannerNode --> EvaluatorNode
    EvaluatorNode --> PlannerNode: Rejected (Self-Correction)
    EvaluatorNode --> ExecutionNode: Approved
    ExecutionNode --> AuditLogger
    AuditLogger --> [*]
```

- Refactor `alos/core/graph.py` to encapsulate a `langgraph.graph.StateGraph`.
- Use `instructor` to enforce Pydantic return schemas on LLM completion nodes.
