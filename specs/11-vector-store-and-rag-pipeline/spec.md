# Feature Specification: Vector Store & RAG Pipeline (Spec 11)

## Executive Summary
This specification defines the evolution of memory retrieval via `lancedb`, `chromadb`, `sentence-transformers`, `rapidfuzz`, `tiktoken`, `langchain-text-splitters`, `unstructured`, hybrid BM25 + dense vector RRF search, and `fastembed`.

## Scope of Included Ideas (Ideas 21–30)
21. `lancedb` disk-persisted vector storage
22. `chromadb` embedded vector store
23. `sentence-transformers` local embeddings
24. `rapidfuzz` fuzzy string distance algorithms
25. `tiktoken` BPE token counting
26. `langchain-text-splitters` syntax-aware markdown chunking
27. `unstructured` multi-format document parser
28. Reciprocal Rank Fusion (RRF) hybrid BM25 + dense search
29. `fastembed` ONNX CPU embeddings
30. `qdrant-client` local testing memory mode
