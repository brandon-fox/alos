# Requirements Checklist: Agent Orchestration & State Graphs (Spec 12)

- [ ] `ALOSStateGraph.run()` delegates node routing to `langgraph.graph.StateGraph`.
- [ ] Draft actions strictly validate against Pydantic models via `instructor`.
- [ ] Maximum 5 self-correction attempts enforced in graph conditional edges.
