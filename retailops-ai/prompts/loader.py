"""Loads versioned agent prompt files (prompts/<agent>/vN.md) and hashes
their content. CLAUDE.md's coding rules require prompts to be versioned
files, never inline strings, and invariant 2 (full trace) requires the
hash of the exact prompt text be recorded per execution
(agent_steps.prompt_version_hash) -- a version label alone ("v1") could
silently drift from what the file actually says; the content hash can't.
"""

import hashlib
from dataclasses import dataclass
from pathlib import Path

PROMPTS_ROOT = Path(__file__).resolve().parent


@dataclass(frozen=True)
class LoadedPrompt:
    agent_name: str
    version: str
    text: str
    content_hash: str


def load_prompt(agent_name: str, version: str = "v1") -> LoadedPrompt:
    path = PROMPTS_ROOT / agent_name / f"{version}.md"
    text = path.read_text(encoding="utf-8")
    content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return LoadedPrompt(
        agent_name=agent_name, version=version, text=text, content_hash=content_hash
    )
