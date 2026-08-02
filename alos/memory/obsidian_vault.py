"""Obsidian Vault Parser for ALOS Memory.

Spec: specs/08-obsidian-vault-brain-integration/spec.md
"""

import logging
import os
import re
from typing import Any

import frontmatter
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Try importing compiled Rust native extension module for 10x+ parsing acceleration
try:
    from alos_native import FastVaultParser  # type: ignore[import-not-found]

    HAS_RUST_NATIVE = True
except ImportError:
    FastVaultParser = None
    HAS_RUST_NATIVE = False


class ObsidianNote(BaseModel):
    """Structured representation of an Obsidian vault markdown note."""

    file_name: str
    file_path: str
    content: str
    frontmatter: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    wiki_links: list[str] = Field(default_factory=list)


class ObsidianVaultParser:
    """Parses Obsidian Markdown vault notes extracting YAML frontmatter,
    tags, and [[WikiLink]] references. Uses Rust native extension when available.
    """

    def __init__(self, vault_dir: str):
        self.vault_dir = os.path.abspath(vault_dir)
        self._native_parser = (
            FastVaultParser(self.vault_dir) if HAS_RUST_NATIVE and FastVaultParser else None
        )

    def _extract_frontmatter(self, raw_text: str) -> tuple[dict[str, Any], list[str], str]:
        tags: list[str] = []
        try:
            post = frontmatter.loads(raw_text)
            metadata = dict(post.metadata)
            body_text = post.content

            if "tags" in metadata:
                val = metadata["tags"]
                if isinstance(val, list):
                    tags.extend([str(t) for t in val])
                elif isinstance(val, str):
                    tags.append(val)
            return metadata, tags, body_text
        except Exception:
            return {}, [], raw_text

    def parse_file(self, file_path: str) -> ObsidianNote:
        """Parse single markdown note file into structured ObsidianNote."""
        if self._native_parser:
            try:
                native_note = self._native_parser.parse_file(file_path)
                return ObsidianNote(
                    file_name=native_note.file_name,
                    file_path=native_note.file_path,
                    content=native_note.content,
                    frontmatter=native_note.frontmatter,
                    tags=native_note.tags,
                    wiki_links=native_note.wiki_links,
                )
            except Exception as err:
                logger.debug("Native FastVaultParser parse_file failed: %s", err)

        file_name = os.path.basename(file_path)

        with open(file_path, encoding="utf-8") as f:
            raw_text = f.read()

        frontmatter, tags, body_text = self._extract_frontmatter(raw_text)

        # Extract inline #tags from body
        inline_tags = re.findall(r"(?:^|\s)#([a-zA-Z0-9_\-\/]+)", body_text)
        for tag in inline_tags:
            if tag not in tags:
                tags.append(tag)

        # Extract [[WikiLinks]]
        raw_links = re.findall(r"\[\[(.*?)\]\]", raw_text)
        wiki_links: list[str] = []
        for link in raw_links:
            clean_link = link.split("|")[0].split("#")[0].strip()
            if clean_link and clean_link not in wiki_links:
                wiki_links.append(clean_link)

        return ObsidianNote(
            file_name=file_name,
            file_path=file_path,
            content=body_text,
            frontmatter=frontmatter,
            tags=tags,
            wiki_links=wiki_links,
        )

    def parse_all(self) -> list[ObsidianNote]:
        """Parse all markdown notes in vault directory recursively."""
        if self._native_parser:
            try:
                native_notes = self._native_parser.parse_all()
                return [
                    ObsidianNote(
                        file_name=n.file_name,
                        file_path=n.file_path,
                        content=n.content,
                        frontmatter=n.frontmatter,
                        tags=n.tags,
                        wiki_links=n.wiki_links,
                    )
                    for n in native_notes
                ]
            except Exception as err:
                logger.debug("Native FastVaultParser parse_all failed: %s", err)

        notes: list[ObsidianNote] = []
        if not os.path.exists(self.vault_dir):
            return notes

        for root, _, files in os.walk(self.vault_dir):
            for file in files:
                if file.endswith(".md"):
                    full_path = os.path.join(root, file)
                    try:
                        notes.append(self.parse_file(full_path))
                    except (OSError, UnicodeDecodeError, ValueError):
                        continue
        return notes
