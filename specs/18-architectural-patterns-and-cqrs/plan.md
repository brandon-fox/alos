# Architecture Plan: Architectural Design Patterns & CQRS (Spec 18)

```mermaid
graph TD
    User[User Query] --> ReadPath[CQRS Read Path: ContextAssembler]
    ReadPath --> Memory[Vector Store & Graph Memory]

    User --> WritePath[CQRS Write Path: ALOSStateGraph]
    WritePath --> Evaluator[EvaluatorNode Strategy]
    Evaluator --> Saga[Saga Execution & Compensating Rollback]
```

- Separate read-heavy memory synthesis (Queries) from write-heavy action evaluation (Commands).
- Implement Saga compensating actions in `MCPGateway` if tool execution fails halfway.
