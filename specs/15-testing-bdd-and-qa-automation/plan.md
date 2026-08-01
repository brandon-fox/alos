# Architecture Plan: Testing, BDD & QA Automation (Spec 15)

```mermaid
graph TD
    Feature[tests/features/*.feature] --> BDD[pytest-bdd Step Defs]
    BDD --> Suite[pytest Test Suite]
    Prop[hypothesis Property Tests] --> Suite
    VCR[vcrpy HTTP Cassettes] --> Suite
```

- Add `factory_boy` factory definitions in `tests/factories/`.
- Add `hypothesis` `@given` strategies for testing evaluator rule boundaries.
