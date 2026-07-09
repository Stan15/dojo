"""Generate virtual doc pages at build time (mkdocs-gen-files).

Two products, neither ever committed:
- one API-reference page per public dojo module under ``reference/``
  (standard mkdocstrings recipe: mkdocstrings.github.io/recipes), so new
  modules appear in the site without touching any config;
- ``adr/index.md``, a decision-record index derived from each ADR file's
  first heading.
"""

import re
from pathlib import Path

import mkdocs_gen_files

# --- API reference: one page per module, package root at reference/index.md
nav = mkdocs_gen_files.Nav()
src = Path("src")

for path in sorted(src.rglob("*.py")):
    parts = tuple(path.relative_to(src).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    elif parts[-1].startswith("_"):
        continue

    rel = parts[1:]  # drop the top-level "dojo" segment from URLs
    is_package = (src / Path(*parts) / "__init__.py").exists()
    doc_path = Path(*rel, "index.md") if is_package else Path(*rel).with_suffix(".md")

    with mkdocs_gen_files.open(Path("reference", doc_path), "w") as fd:
        fd.write(f"::: {'.'.join(parts)}")
    mkdocs_gen_files.set_edit_path(Path("reference", doc_path), path)
    if rel:
        nav[rel] = doc_path.as_posix()

with mkdocs_gen_files.open("reference/SUMMARY.md", "w") as nav_file:
    nav_file.write("- [dojo (package overview)](index.md)\n")
    nav_file.writelines(nav.build_literate_nav())

# --- ADR index: title list derived from the files themselves
lines = [
    "# Decision records",
    "",
    "Architecture Decision Records, in order. ADRs 010-016 supersede earlier",
    "ADRs where they conflict.",
    "",
]
for adr in sorted(Path("docs/adr").glob("*.md")):
    if adr.name == "index.md":
        continue
    first_heading = next(
        (m.group(1) for line in adr.read_text().splitlines() if (m := re.match(r"#\s+(.*)", line))),
        adr.stem,
    )
    lines.append(f"- [{first_heading}]({adr.name})")

with mkdocs_gen_files.open("adr/index.md", "w") as fd:
    fd.write("\n".join(lines) + "\n")
