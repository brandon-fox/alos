import os

from alos.memory.spec_rag import SpecRAGIndexer


def test_spec_rag_indexer_builds_and_searches():
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    indexer = SpecRAGIndexer(root_dir)

    assert len(indexer.chunks) > 0, "Indexer should load spec and vault chunks"

    # Test query for safety matrix
    results = indexer.search("safety matrix", top_k=3)
    assert len(results) > 0, "Search for 'safety matrix' should return results"
    assert any("safety" in r["content"].lower() for r in results)


def test_spec_rag_source_filter():
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    indexer = SpecRAGIndexer(root_dir)

    vault_results = indexer.search("", top_k=5, source_filter="vault")
    for res in vault_results:
        assert res["source_type"] == "vault"
