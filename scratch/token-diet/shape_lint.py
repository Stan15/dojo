"""Template shape-lint (scratch prototype → test_prompts.py with the winner).

Checks the OUTPUT block of each task template for weak-model-hostile patterns
measured in the token-diet batteries (src/dojo/prompts/README.md items 1/2/6
plus the "..." placeholder finding from armJ):

  FAIL enum-pipe        "a|b|c" option strings as skeleton values (copied
                        verbatim as the value by ≤4B models)
  FAIL slash-comment    // comments (copied into output or crowd out fields)
  FAIL dots-placeholder "..." values (teach nothing; models omit or echo)
  WARN numeric-in-value caps embedded in skeleton string values (rumination
                        bait for thinking models — pending qwen armJ data)

Usage: python shape_lint.py <template-dir> [...]
"""
import re
import sys
from pathlib import Path

ENUM_PIPE = re.compile(r'"[a-z_]+(\|[a-z_]+)+"')
SLASH_COMMENT = re.compile(r"//")
DOTS_VALUE = re.compile(r':\s*"\.\.\."|\["\.\.\."\]|"\.\.\.\?"')
NUM_IN_VALUE = re.compile(r'"[^"\n]*(?:≤\s*(?:\d+|\{\{\s*\w+\s*\}\}))[^"\n]*"')


def output_block(text: str) -> str:
    m = re.search(r"^OUTPUT\b.*$", text, re.M)
    return text[m.start():] if m else text


def lint_dir(d: Path) -> int:
    fails = 0
    for p in sorted(d.glob("*.md")):
        if p.name == "README.md":
            continue
        block = output_block(p.read_text(encoding="utf-8"))
        found = []
        if ENUM_PIPE.search(block):
            found.append(("FAIL", "enum-pipe", ENUM_PIPE.search(block).group(0)))
        if SLASH_COMMENT.search(block):
            found.append(("FAIL", "slash-comment", "//"))
        if DOTS_VALUE.search(block):
            found.append(("FAIL", "dots-placeholder", DOTS_VALUE.search(block).group(0)))
        for m in NUM_IN_VALUE.finditer(block):
            found.append(("WARN", "numeric-in-value", m.group(0)[:60]))
        for level, rule, ev in found:
            print(f"  {level} {p.name:<24} {rule:<17} {ev}")
            fails += level == "FAIL"
        if not found:
            print(f"  ok   {p.name}")
    return fails


total = 0
for arg in sys.argv[1:]:
    print(f"== {arg}")
    total += lint_dir(Path(arg))
print(f"\n{total} FAIL findings")
sys.exit(1 if total else 0)
