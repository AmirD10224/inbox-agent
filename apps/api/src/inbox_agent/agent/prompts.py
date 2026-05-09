"""Versioned prompt loader.

Prompts live in `prompts/` as markdown with frontmatter. Filenames are
`<name>.v<semver>.md`. The loader picks the highest semver per name unless
overridden, validates frontmatter on load, and returns split (system, user)
templates so callers don't parse markdown.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml


# Locate prompts/ relative to the package root, then walk up to find apps/api/prompts/.
def _default_prompts_dir() -> Path:
    here = Path(__file__).resolve()
    # src/inbox_agent/agent/prompts.py → src/inbox_agent/agent → src/inbox_agent → src → apps/api
    api_root = here.parents[3]
    return api_root / "prompts"


_FILENAME_RE = re.compile(r"^(?P<name>[a-z_]+)\.v(?P<version>\d+\.\d+\.\d+)\.md$")
_FRONTMATTER_RE = re.compile(r"^---\n(?P<fm>.*?)\n---\n(?P<body>.*)\Z", re.DOTALL)
_SECTION_RE = re.compile(
    r"(?ms)^#\s+(System|User)\s*$\n(?P<body>.*?)(?=^#\s+(?:System|User)\s*$|\Z)"
)


@dataclass(frozen=True, slots=True)
class Prompt:
    name: str
    version: str
    model: str
    system_template: str
    user_template: str
    metadata: dict[str, Any]

    def render(self, **vars: Any) -> tuple[str, str]:
        """Render system + user with `str.format(**vars)`. Missing keys raise."""
        return self.system_template.format(**vars), self.user_template.format(**vars)


class PromptLoader:
    def __init__(self, prompts_dir: Path | None = None) -> None:
        self._dir = prompts_dir or _default_prompts_dir()
        if not self._dir.exists():
            msg = f"Prompts directory not found: {self._dir}"
            raise FileNotFoundError(msg)
        self._cache: dict[str, Prompt] = {}
        self._index_by_name: dict[str, list[str]] = {}
        self._index()

    def _index(self) -> None:
        for path in self._dir.glob("*.md"):
            m = _FILENAME_RE.match(path.name)
            if not m:
                continue
            name = m.group("name")
            version = m.group("version")
            self._index_by_name.setdefault(name, []).append(version)

        for versions in self._index_by_name.values():
            versions.sort(key=lambda v: tuple(int(p) for p in v.split(".")), reverse=True)

    def load(self, name: str, version: str | None = None) -> Prompt:
        if name not in self._index_by_name:
            msg = f"Unknown prompt: {name}. Available: {sorted(self._index_by_name)}"
            raise KeyError(msg)
        chosen = version or self._index_by_name[name][0]
        cache_key = f"{name}@{chosen}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        path = self._dir / f"{name}.v{chosen}.md"
        if not path.exists():
            msg = f"Prompt file not found: {path}"
            raise FileNotFoundError(msg)

        text = path.read_text(encoding="utf-8")
        fm_match = _FRONTMATTER_RE.match(text)
        if fm_match is None:
            msg = f"Prompt {path} missing YAML frontmatter"
            raise ValueError(msg)

        fm = yaml.safe_load(fm_match.group("fm")) or {}
        body = fm_match.group("body")

        system_template = ""
        user_template = ""
        for sec in _SECTION_RE.finditer(body):
            kind = sec.group(1)
            content = sec.group("body").strip()
            if kind == "System":
                system_template = content
            elif kind == "User":
                user_template = content

        if not system_template or not user_template:
            msg = f"Prompt {path} must contain '# System' and '# User' sections"
            raise ValueError(msg)

        prompt = Prompt(
            name=fm.get("name", name),
            version=fm.get("version", chosen),
            model=fm.get("model", "claude-sonnet-4-6"),
            system_template=system_template,
            user_template=user_template,
            metadata=fm,
        )
        self._cache[cache_key] = prompt
        return prompt


@lru_cache(maxsize=1)
def get_prompt_loader() -> PromptLoader:
    return PromptLoader()
