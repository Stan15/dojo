"""Docstring-coverage gate (owner directive 2026-07-09).

The API reference site is generated from docstrings, so an undocumented
public symbol is a hole in the product documentation. This gate walks every
module under src/dojo and fails on any public module, class, function, or
method without a docstring — 100%, no ratchet, no allowlist. Nested
functions and anything named with a leading underscore are out of scope.
"""
from __future__ import annotations

import ast
from pathlib import Path

SRC = Path(__file__).parent.parent / "src" / "dojo"


def _public_symbols(tree: ast.Module) -> list[tuple[str, ast.AST]]:
    """(qualified name, node) for every public class, function, and method at
    module or class level. Nested functions are implementation detail."""
    symbols: list[tuple[str, ast.AST]] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node.name.startswith("_"):
                continue
            symbols.append((node.name, node))
            if isinstance(node, ast.ClassDef):
                for sub in node.body:
                    if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if not sub.name.startswith("_"):
                            symbols.append((f"{node.name}.{sub.name}", sub))
    return symbols


def test_every_public_symbol_has_a_docstring():
    missing: list[str] = []
    for path in sorted(SRC.rglob("*.py")):
        rel = path.relative_to(SRC.parent)
        tree = ast.parse(path.read_text(encoding="utf-8"))
        if ast.get_docstring(tree) is None:
            missing.append(f"{rel}: <module docstring>")
        for name, node in _public_symbols(tree):
            if ast.get_docstring(node) is None:
                missing.append(f"{rel}: {name}")
    assert not missing, (
        "public surface without docstrings (the generated docs would be holes):\n  "
        + "\n  ".join(missing)
    )


def test_docstrings_are_not_placeholders():
    """A docstring that just restates the name teaches nothing. Cheap floor:
    at least four words."""
    thin: list[str] = []
    for path in sorted(SRC.rglob("*.py")):
        rel = path.relative_to(SRC.parent)
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for name, node in _public_symbols(tree):
            doc = ast.get_docstring(node)
            if doc is not None and len(doc.split()) < 4:
                thin.append(f"{rel}: {name} ({doc!r})")
    assert not thin, "placeholder docstrings:\n  " + "\n  ".join(thin)
