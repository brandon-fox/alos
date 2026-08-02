"""Obsidian vault reader tool integration for CrewAI agent tasks."""

import os

from pydantic import BaseModel, Field

from alos.memory.obsidian_vault import ObsidianVaultParser


class ObsidianVaultInput(BaseModel):
    """Input model for ObsidianVaultTool."""

    file_name: str = Field(
        ..., description="File name of the note to read from vault (e.g. USER_PROFILE.md)"
    )
    vault_dir: str = Field(
        default="vault", description="Relative or absolute path to vault directory"
    )


class ObsidianVaultTool:
    """Tool for reading notes and user profile context from local Obsidian vault."""

    name: str = "obsidian_vault_reader"
    description: str = (
        "Reads markdown notes from local Obsidian vault to access user memory and profile."
    )
    args_schema: type[BaseModel] = ObsidianVaultInput

    def __init__(self, vault_dir: str = "vault") -> None:
        self.vault_dir = os.path.abspath(vault_dir)
        self.parser = ObsidianVaultParser(self.vault_dir)

    def run(self, file_name: str, vault_dir: str = "vault") -> str:
        """Read and parse markdown note from Obsidian vault."""
        target_dir = os.path.abspath(vault_dir) if vault_dir else self.vault_dir
        target_path = os.path.join(target_dir, file_name)

        if not os.path.exists(target_path):
            return f"Note '{file_name}' not found in vault directory '{target_dir}'."

        try:
            note = self.parser.parse_file(target_path)
            return (
                f"### {note.file_name}\n"
                f"**Path**: {note.file_path}\n"
                f"**Tags**: {', '.join(note.tags)}\n"
                f"**WikiLinks**: {', '.join(note.wiki_links)}\n\n"
                f"{note.content}"
            )
        except Exception as err:
            return f"Error reading note '{file_name}': {err}"
