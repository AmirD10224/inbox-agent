"""Architectural test: only `inbox_agent.llm.client` may touch the Anthropic SDK.

Rather than regex over file text (which misses `__import__("anthropic")`,
`importlib.import_module("anthropic")`, indirect re-exports, and aliased
names), we walk the AST of every source module and look for:

  - any `Import` / `ImportFrom` whose root module is `anthropic`
  - any `Call` to `__import__("anthropic")` or `importlib.import_module("anthropic")`
  - any reference to the symbols `Anthropic`, `AsyncAnthropic`, `AnthropicVertex`,
    or `AnthropicBedrock`

outside of `inbox_agent.llm.client`. This catches realistic bypasses while
remaining cheap (~ms on the whole tree).
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

PKG_ROOT = Path(__file__).resolve().parents[2] / "src" / "inbox_agent"
ALLOWED = {PKG_ROOT / "llm" / "client.py"}

FORBIDDEN_SYMBOLS = {
    "Anthropic",
    "AsyncAnthropic",
    "AnthropicVertex",
    "AnthropicBedrock",
    "AsyncAnthropicVertex",
    "AsyncAnthropicBedrock",
}


class _AnthropicReferenceVisitor(ast.NodeVisitor):
    """Collects offending nodes (line numbers + reason) within a module AST."""

    def __init__(self) -> None:
        self.offences: list[str] = []

    # `import anthropic` / `import anthropic.types as t`
    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            if alias.name == "anthropic" or alias.name.startswith("anthropic."):
                self.offences.append(f"L{node.lineno}: import {alias.name}")
        self.generic_visit(node)

    # `from anthropic import X` / `from anthropic.types import Y`
    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module == "anthropic" or (node.module or "").startswith("anthropic."):
            names = ", ".join(a.name for a in node.names)
            self.offences.append(f"L{node.lineno}: from {node.module} import {names}")
        self.generic_visit(node)

    # `__import__("anthropic")` and `importlib.import_module("anthropic")`
    def visit_Call(self, node: ast.Call) -> None:
        func = node.func
        target = None
        if isinstance(func, ast.Name) and func.id == "__import__":
            target = self._first_str_arg(node)
            if target == "anthropic" or (target or "").startswith("anthropic."):
                self.offences.append(f"L{node.lineno}: __import__({target!r})")
        elif (
            isinstance(func, ast.Attribute)
            and func.attr == "import_module"
            and isinstance(func.value, ast.Name)
            and func.value.id == "importlib"
        ):
            target = self._first_str_arg(node)
            if target == "anthropic" or (target or "").startswith("anthropic."):
                self.offences.append(f"L{node.lineno}: importlib.import_module({target!r})")
        self.generic_visit(node)

    # Any bare reference to Anthropic / AsyncAnthropic etc.
    def visit_Name(self, node: ast.Name) -> None:
        if node.id in FORBIDDEN_SYMBOLS:
            self.offences.append(f"L{node.lineno}: name {node.id!r}")
        self.generic_visit(node)

    @staticmethod
    def _first_str_arg(call: ast.Call) -> str | None:
        if not call.args:
            return None
        first = call.args[0]
        if isinstance(first, ast.Constant) and isinstance(first.value, str):
            return first.value
        return None


def test_only_client_module_touches_anthropic_sdk() -> None:
    offenders: dict[str, list[str]] = {}
    for path in PKG_ROOT.rglob("*.py"):
        if path in ALLOWED:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError as e:  # pragma: no cover, the test runner already validates syntax
            pytest.fail(f"could not parse {path}: {e}")
        visitor = _AnthropicReferenceVisitor()
        visitor.visit(tree)
        if visitor.offences:
            offenders[str(path.relative_to(PKG_ROOT))] = visitor.offences

    if offenders:
        lines = ["Only inbox_agent.llm.client may import or reference the Anthropic SDK."]
        for f, refs in offenders.items():
            lines.append(f"  {f}")
            lines.extend(f"    {r}" for r in refs)
        pytest.fail("\n".join(lines))


# --- Self-test of the visitor itself --------------------------------------


def _visit_source(src: str) -> list[str]:
    visitor = _AnthropicReferenceVisitor()
    visitor.visit(ast.parse(src))
    return visitor.offences


def test_visitor_catches_direct_import() -> None:
    assert _visit_source("import anthropic\n")


def test_visitor_catches_dotted_import() -> None:
    assert _visit_source("import anthropic.types as t\n")


def test_visitor_catches_from_import() -> None:
    assert _visit_source("from anthropic import AsyncAnthropic\n")


def test_visitor_catches_from_dotted_import() -> None:
    assert _visit_source("from anthropic.types import Message\n")


def test_visitor_catches_dunder_import_string() -> None:
    assert _visit_source("x = __import__('anthropic')\n")


def test_visitor_catches_importlib_import_module() -> None:
    assert _visit_source("import importlib\nx = importlib.import_module('anthropic')\n")


def test_visitor_catches_anthropic_class_reference() -> None:
    # Even without an import, mentioning the class name is suspicious.
    assert _visit_source("def f(x: 'AsyncAnthropic') -> None: ...\n") or _visit_source(
        "AsyncAnthropic\n"
    )


def test_visitor_passes_clean_module() -> None:
    assert _visit_source("from inbox_agent.config import get_settings\n") == []
