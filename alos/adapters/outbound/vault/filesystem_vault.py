"""Filesystem Obsidian vault adapter implementing VaultRepositoryPort (ADR-0024)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from alos.domain.models.memory import ObsidianNote
from alos.memory.brain_synthesizer import ObsidianBrainSynthesizer
from alos.memory.obsidian_vault import ObsidianVaultParser

logger = logging.getLogger(__name__)
_ALIASES = {"preferences.md": "PREFERENCES.md", "corrections.md": "CORRECTION_LEDGER.md"}


class FilesystemVaultAdapter:
    """Ring 3 Hexagonal outbound adapter implementing VaultRepositoryPort over local files."""

    def __init__(
        self, vault_dir: str, *, use_native: bool | None = None, native_parser_cls: Any = None
    ) -> None:
        """Initialize adapter delegating parsing and synthesis to local vault storage."""
        self._parser = ObsidianVaultParser(
            vault_dir, use_native=use_native, native_parser_cls=native_parser_cls
        )
        self._synthesizer = ObsidianBrainSynthesizer(vault_dir)
        self.vault_dir = self._parser.vault_dir

    def parse_file(self, file_path: str) -> ObsidianNote:
        """Parse a single markdown note file into an immutable ObsidianNote."""
        return self._parser.parse_file(file_path)

    def parse_all(self) -> list[ObsidianNote]:
        """Parse all markdown notes recursively, logging and skipping unreadable files."""
        return self._parser.parse_all()

    def _read_lines(self, filename: str) -> list[str]:
        """Resolve vault markdown file or alias and return non-heading lines."""
        root, alias = Path(self.vault_dir), _ALIASES.get(filename.lower())
        for path in (root / filename, root / alias if alias else None):
            if path is not None and path.is_file():
                try:
                    raw = path.read_text(encoding="utf-8")
                    return [ln for ln in raw.splitlines() if not ln.startswith("#")]
                except (OSError, UnicodeDecodeError) as err:
                    logger.warning("Failed reading vault file '%s': %s", path, err)
                    return []
        return []

    def read_profile(self) -> dict[str, Any]:
        """Read structured key-value user profile metadata from USER_PROFILE.md."""
        lines = self._read_lines("USER_PROFILE.md") or self._read_lines("user_profile.md")
        items = [ln.strip().lstrip("- ").split(":", 1) for ln in lines if ":" in ln]
        return {k.strip(): v.strip() for k, v in items}

    def read_list(self, filename: str) -> list[str]:
        """Read normalized non-empty bulleted entries from a vault markdown file."""
        return [
            item for ln in self._read_lines(filename) if (item := ln.strip().lstrip("- ").strip())
        ]

    def collect_wiki_links(self) -> list[str]:
        """Collect deduplicated ordered WikiLinks across all vault notes."""
        return list(dict.fromkeys(link for note in self.parse_all() for link in note.wiki_links))

    def append_daily_note(self, date_str: str, content: str, tags: list[str] | None = None) -> str:
        """Append daily entry to Daily Notes/{date_str}.md and return its file path."""
        return self._synthesizer.append_daily_note(date_str=date_str, content=content, tags=tags)

    def create_memory_note(
        self,
        title: str,
        content: str,
        tags: list[str] | None = None,
        wiki_links: list[str] | None = None,
    ) -> str:
        """Write a structured memory note with frontmatter and WikiLinks into Memory/."""
        return self._synthesizer.create_memory_note(
            title=title, content=content, tags=tags, wiki_links=wiki_links
        )
