"""Obsidian Vault Parser for ALOS Memory.

Spec: specs/08-obsidian-vault-brain-integration/spec.md
"""

import os
import re
from typing import Any

from pydantic import BaseModel, Field


class ObsidianNote(BaseModel):
    file_name: str
    file_path: str
    content: str
    frontmatter: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    wiki_links: list[str] = Field(default_factory=list)


class ObsidianVaultParser:
    """Parses Obsidian Markdown vault notes extracting YAML frontmatter,
    tags, and [[WikiLink]] references.
    """

    def __init__(self, vault_dir: str):
        self.vault_dir = os.path.abspath(vault_dir)

    def _extract_frontmatter(self, raw_text: str) -> tuple[dict[str, Any], list[str], str]:
        frontmatter: dict[str, Any] = {}
        tags: list[str] = []
        body_text = raw_text

        if raw_text.startswith("---"):
            parts = raw_text.split("---", 2)
            if len(parts) >= 3:
                yaml_block = parts[1]
                body_text = parts[2]
                current_key: str | None = None
                for line in yaml_block.splitlines():
                    line_str = line.strip()
                    if not line_str or line_str.startswith("#"):
                        continue
                    if ":" in line_str and not line_str.startswith("-"):
                        k, v = line_str.split(":", 1)
                        current_key = k.strip()
                        val_str = v.strip()
                        frontmatter[current_key] = val_str if val_str else []
                    elif line_str.startswith("-") and current_key:
                        item = line_str.lstrip("- ").strip()
                        if isinstance(frontmatter.get(current_key), list):
                            frontmatter[current_key].append(item)

                if "tags" in frontmatter and isinstance(frontmatter["tags"], list):
                    tags.extend(frontmatter["tags"])

        return frontmatter, tags, body_text

    def parse_file(self, file_path: str) -> ObsidianNote:
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
