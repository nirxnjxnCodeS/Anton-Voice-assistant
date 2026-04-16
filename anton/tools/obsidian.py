"""
Obsidian tools — persistent memory via markdown files in an Obsidian vault.

Vault path is set via OBSIDIAN_VAULT_PATH in .env.
All operations are pure file I/O — no Obsidian app or plugins required.
"""

import re
from datetime import date
from pathlib import Path

from anton.config import config

# ---------------------------------------------------------------------------
# Folder routing — maps topics to vault subfolders for remember()
# ---------------------------------------------------------------------------

_TOPIC_FOLDERS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\b(person|people|friend|colleague|contact|sagar|boss|mom|dad)\b", re.I), "people"),
    (re.compile(r"\b(project|app|build|feature|idea|plan|task)\b", re.I), "projects"),
    (re.compile(r"\b(prefer|preference|setting|mode|theme|colour|color|habit|style)\b", re.I), "preferences"),
]

_ANTON_MD = """\
# Anton — Vault Schema

This vault is maintained by Anton, your AI assistant.

## Folder structure
- `people/`      — notes about people Anton has been told about
- `projects/`    — project notes and ideas
- `topics/`      — articles, concepts, and general knowledge
- `preferences/` — user preferences and settings
- `daily/`       — daily notes (YYYY-MM-DD.md)

## Note format
Each note starts with a `# Title` heading and an ISO timestamp on creation.
Anton appends new information rather than overwriting existing content.

## Usage
Ask Anton to remember, recall, search, or append anything — it writes here.
"""


# ---------------------------------------------------------------------------
# Vault helpers
# ---------------------------------------------------------------------------

def _vault() -> Path:
    raw = config.OBSIDIAN_VAULT_PATH
    if not raw:
        raise ValueError(
            "OBSIDIAN_VAULT_PATH is not set, sir. "
            "Add it to your .env file pointing at the Obsidian vault folder."
        )
    return Path(raw).expanduser()


def _ensure_vault() -> Path:
    """Create standard folder structure and ANTON.md on first use."""
    vault = _vault()
    for folder in ("people", "projects", "topics", "preferences", "daily"):
        (vault / folder).mkdir(parents=True, exist_ok=True)

    anton_md = vault / "ANTON.md"
    if not anton_md.exists():
        anton_md.write_text(_ANTON_MD, encoding="utf-8")

    return vault


def _slug(text: str) -> str:
    """Convert a title to a safe filename slug."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "_", text)
    return text.strip("_") or "note"


def _infer_folder(topic: str) -> str:
    for pattern, folder in _TOPIC_FOLDERS:
        if pattern.search(topic):
            return folder
    return "topics"


def _read_note(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


def _write_note(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _append_note(path: Path, addition: str) -> None:
    existing = path.read_text(encoding="utf-8").rstrip() if path.exists() else ""
    path.write_text(existing + "\n\n" + addition.strip() + "\n", encoding="utf-8")


def _today_path(vault: Path) -> Path:
    return vault / "daily" / f"{date.today().isoformat()}.md"


# ---------------------------------------------------------------------------
# Tool registration
# ---------------------------------------------------------------------------

def register(mcp):

    @mcp.tool()
    def remember(topic: str, content: str) -> str:
        """
        Store a new fact or update Anton's memory about a topic.
        Automatically routes to the correct folder based on the topic.
        Examples:
          remember("Sagar", "Sagar is my college friend from Manipal")
          remember("dark mode preference", "User prefers dark mode in all apps")
        """
        try:
            vault = _ensure_vault()
            folder = _infer_folder(topic)
            slug = _slug(topic)
            note_path = vault / folder / f"{slug}.md"

            if note_path.exists():
                _append_note(note_path, content)
                action = "updated"
            else:
                body = f"# {topic.title()}\n\n{content}\n"
                _write_note(note_path, body)
                action = "created"

            return f"Noted, sir. I've {action} my memory on {topic}."
        except ValueError as e:
            return str(e)
        except Exception as e:
            return f"I couldn't save that memory, sir. Error: {e}"

    @mcp.tool()
    def recall(topic: str) -> str:
        """
        Read Anton's stored note about a topic.
        Examples:
          recall("Sagar")
          recall("dark mode preference")
        """
        try:
            vault = _ensure_vault()
            slug = _slug(topic)

            # Search all folders for a matching file
            for folder in ("people", "projects", "preferences", "topics", "daily"):
                candidate = vault / folder / f"{slug}.md"
                if candidate.exists():
                    content = _read_note(candidate)
                    return f"Here's what I know about {topic}, sir:\n\n{content}"

            return f"I don't have any notes on '{topic}', sir."
        except ValueError as e:
            return str(e)
        except Exception as e:
            return f"I couldn't retrieve that memory, sir. Error: {e}"

    @mcp.tool()
    def create_note(title: str, content: str, folder: str = "topics") -> str:
        """
        Create a new note in the vault.
        - title: note title (becomes the filename)
        - content: markdown body
        - folder: subfolder inside vault — one of 'people', 'projects', 'topics',
                  'preferences', 'daily'. Defaults to 'topics'.
        Examples:
          create_note("Project Ideas", "- Build habit tracker\n- MCP plugin for VS Code")
          create_note("Sagar", "College friend from Manipal", folder="people")
        """
        try:
            vault = _ensure_vault()
            valid_folders = {"people", "projects", "topics", "preferences", "daily"}
            dest_folder = folder if folder in valid_folders else "topics"

            slug = _slug(title)
            note_path = vault / dest_folder / f"{slug}.md"

            if note_path.exists():
                return (
                    f"A note called '{title}' already exists in {dest_folder}/, sir. "
                    "Use append_to_note to add to it."
                )

            body = f"# {title}\n\n{content}\n"
            _write_note(note_path, body)
            return f"Note '{title}' created in {dest_folder}/, sir."
        except ValueError as e:
            return str(e)
        except Exception as e:
            return f"I couldn't create the note, sir. Error: {e}"

    @mcp.tool()
    def append_to_note(title: str, content: str) -> str:
        """
        Append new content to an existing note anywhere in the vault.
        Searches all standard folders for a note matching the title.
        Examples:
          append_to_note("Project Ideas", "- Add voice reminders to Anton")
          append_to_note("Sagar", "Met for coffee on Apr 16")
        """
        try:
            vault = _ensure_vault()
            slug = _slug(title)

            for folder in ("people", "projects", "preferences", "topics"):
                candidate = vault / folder / f"{slug}.md"
                if candidate.exists():
                    _append_note(candidate, content)
                    return f"Added to '{title}', sir."

            return (
                f"I couldn't find a note called '{title}', sir. "
                "Use create_note to make one first."
            )
        except ValueError as e:
            return str(e)
        except Exception as e:
            return f"I couldn't update the note, sir. Error: {e}"

    @mcp.tool()
    def search_notes(query: str) -> str:
        """
        Search all vault notes for a keyword or phrase.
        Returns matching file names and the lines that contain the match.
        Examples:
          search_notes("habit tracker")
          search_notes("Sagar")
        """
        try:
            vault = _ensure_vault()
            pattern = re.compile(re.escape(query), re.IGNORECASE)
            results: list[str] = []

            for md_file in sorted(vault.rglob("*.md")):
                if md_file.name == "ANTON.md":
                    continue
                text = md_file.read_text(encoding="utf-8")
                matches = [
                    line.strip()
                    for line in text.splitlines()
                    if pattern.search(line)
                ]
                if matches:
                    rel = md_file.relative_to(vault)
                    snippet = " / ".join(matches[:3])
                    results.append(f"  • {rel}: {snippet}")

            if not results:
                return f"No notes mention '{query}', sir."

            header = f"Found '{query}' in {len(results)} note(s), sir:\n"
            return header + "\n".join(results)
        except ValueError as e:
            return str(e)
        except Exception as e:
            return f"Search failed, sir. Error: {e}"

    @mcp.tool()
    def get_daily_note() -> str:
        """
        Read today's daily note from the vault (daily/YYYY-MM-DD.md).
        Use when the user asks 'What's in my daily note?', 'What did I log today?', etc.
        """
        try:
            vault = _ensure_vault()
            path = _today_path(vault)

            if not path.exists():
                return (
                    f"No daily note for today yet, sir. "
                    "Say 'add to today's note' to create one."
                )

            content = _read_note(path)
            return f"Today's note, sir:\n\n{content}"
        except ValueError as e:
            return str(e)
        except Exception as e:
            return f"Couldn't read the daily note, sir. Error: {e}"

    @mcp.tool()
    def append_to_daily_note(content: str) -> str:
        """
        Append a new entry to today's daily note. Creates the note if it doesn't exist yet.
        Use when the user says 'Add to today's note', 'Log this', 'Note that I...', etc.
        Examples:
          append_to_daily_note("Finished Spotify integration")
          append_to_daily_note("Meeting with Sagar at 3pm went well")
        """
        try:
            vault = _ensure_vault()
            path = _today_path(vault)
            today = date.today().strftime("%A, %d %B %Y")

            if not path.exists():
                header = f"# Daily Note — {today}\n\n"
                _write_note(path, header + content.strip() + "\n")
            else:
                _append_note(path, content)

            return f"Added to today's note, sir."
        except ValueError as e:
            return str(e)
        except Exception as e:
            return f"Couldn't update the daily note, sir. Error: {e}"
