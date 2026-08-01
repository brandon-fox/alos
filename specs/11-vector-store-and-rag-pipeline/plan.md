# Architecture Plan: Vector Store & RAG Pipeline (Spec 11)

```mermaid
graph TD
    Query[Search Query] --> BM25[BM25 Okapi Ranker]
    Query --> Vector[LanceDB / ChromaDB Vector Engine]
    BM25 --> RRF[Reciprocal Rank Fusion RRF]
    Vector --> RRF
    RRF --> Context[ContextPayload]
```

- Combine `rank_bm25` lexical scores with `lancedb` dense vector scores via RRF.
- Chunk markdown docs using `langchain-text-splitters.MarkdownHeaderTextSplitter`.
