"""Obsidian Brain Synthesizer for ALOS Memory.

Spec: specs/08-obsidian-vault-brain-integration/spec.md
"""

import os


class ObsidianBrainSynthesizer:
    """Synthesizes and creates daily notes and memory notes within the Obsidian vault."""

    def __init__(self, vault_dir: str):
        self.vault_dir = os.path.abspath(vault_dir)

    def append_daily_note(self, date_str: str, content: str, tags: list[str] | None = None) -> str:
        daily_dir = os.path.join(self.vault_dir, "Daily Notes")
        os.makedirs(daily_dir, exist_ok=True)
        file_path = os.path.join(daily_dir, f"{date_str}.md")

        tags_str = ""
        if tags:
            tags_str = "\n" + "\n".join(f"#{t}" for t in tags) + "\n"

        full_content = f"# Daily Note — {date_str}\n\n{content}\n{tags_str}"

        with open(file_path, "a", encoding="utf-8") as f:
            f.write(full_content)

        return file_path

    def create_memory_note(
        self,
        title: str,
        content: str,
        tags: list[str] | None = None,
        wiki_links: list[str] | None = None,
    ) -> str:
        mem_dir = os.path.join(self.vault_dir, "Memory")
        os.makedirs(mem_dir, exist_ok=True)
        file_path = os.path.join(mem_dir, f"{title}.md")

        tags_yaml = ""
        if tags:
            tags_formatted = "\n".join(f"  - {t}" for t in tags)
            tags_yaml = f"tags:\n{tags_formatted}\n"

        links_str = ""
        if wiki_links:
            links_str = "\n\nSee also: " + ", ".join(f"[[{link}]]" for link in wiki_links)

        file_body = f"---\n{tags_yaml}---\n# {title}\n\n{content}{links_str}\n"

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(file_body)

        return file_path
