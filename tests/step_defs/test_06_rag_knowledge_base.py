"""Step definitions for 06_rag_knowledge_base.feature."""

import os
from typing import Any

from pytest_bdd import given, scenarios, then, when

from alos.memory.spec_rag import SpecRAGIndexer

scenarios("../features/06_rag_knowledge_base.feature")


@given("repository root containing specs/, vault/, and constitution files")
def step_repo_root_files(bdd_context: dict[str, Any]) -> None:
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    bdd_context["root_dir"] = root_dir


@when("SpecRAGIndexer builds index")
def step_build_index(bdd_context: dict[str, Any]) -> None:
    root_dir: str = bdd_context["root_dir"]
    indexer = SpecRAGIndexer(root_dir)
    bdd_context["indexer"] = indexer


@then("markdown sections delineated by headers must be searchable with header weighting")
def step_verify_header_weighting(bdd_context: dict[str, Any]) -> None:
    indexer: SpecRAGIndexer = bdd_context["indexer"]
    assert len(indexer.chunks) > 0
    results = indexer.search("safety matrix", top_k=3)
    assert len(results) > 0


@given("indexed documents across spec, vault, and constitution sources")
def step_indexed_docs(bdd_context: dict[str, Any]) -> None:
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    indexer = SpecRAGIndexer(root_dir)
    bdd_context["indexer"] = indexer


@when("SpecRAGIndexer performs search with source_filter")
def step_search_source_filter(bdd_context: dict[str, Any]) -> None:
    indexer: SpecRAGIndexer = bdd_context["indexer"]
    results = indexer.search("", top_k=5, source_filter="vault")
    bdd_context["filtered_results"] = results


@then("only chunks matching the specified source_type must be returned")
def step_verify_source_filter(bdd_context: dict[str, Any]) -> None:
    results = bdd_context["filtered_results"]
    for res in results:
        assert res["source_type"] == "vault"
