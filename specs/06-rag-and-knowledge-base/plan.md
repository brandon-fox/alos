# Component Plan: RAG & Knowledge Base Engine

## Architecture
`alos.memory.spec_rag.SpecRAGIndexer` wraps file system traversal and section-level chunking to index markdown specs and vault notes into memory.

```
[System Specs / Vault / References]
              │
              ▼
    [SpecRAGIndexer.build_index()]
              │
              ▼
      [In-Memory Chunks]
              │
              ▼
   [SpecRAGIndexer.search(query)] ──► Top-K Relevant Context Chunks
```

## Data Models
```python
class SpecChunk(BaseModel):
    file_path: str
    file_name: str
    header: str
    content: str
    source_type: str  # "spec", "vault", "constitution", "reference"
```
