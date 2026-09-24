#!/usr/bin/env python3
"""Check every skill before publishing. / 发布前检查所有技能。

Checks:
  1. skills/<dir>/SKILL.md exists, frontmatter has `name` and `description`
  2. `name` equals the folder name, lowercase-hyphen, <= 64 chars
  3. description <= 1024 chars
  4. each skill has a README.md
  5. privacy: no file under skills/ contains a term from `.privacy-denylist`
     (one term per line, local only — the file is git-ignored and never published)

Usage: python3 scripts/validate.py        exit code 1 on any failure
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILLS = ROOT / "skills"
DENYLIST = ROOT / ".privacy-denylist"
NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
TEXT_SUFFIXES = {".md", ".py", ".sh", ".js", ".mjs", ".cjs", ".ts", ".json", ".yaml", ".yml", ".txt", ".lua"}


def frontmatter(text):
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        return None
    fields = {}
    for line in m.group(1).splitlines():
        k, sep, v = line.partition(":")
        if sep and not line.startswith((" ", "\t")):
            fields[k.strip()] = v.strip()
    return fields


def main():
    errors = []
    terms = []
    if DENYLIST.exists():
        terms = [t.strip() for t in DENYLIST.read_text(encoding="utf-8").splitlines()
                 if t.strip() and not t.startswith("#")]

    dirs = sorted(d for d in SKILLS.iterdir() if d.is_dir()) if SKILLS.exists() else []
    for d in dirs:
        skill_md = d / "SKILL.md"
        if not skill_md.exists():
            errors.append(f"{d.name}: missing SKILL.md")
            continue
        fm = frontmatter(skill_md.read_text(encoding="utf-8"))
        if fm is None:
            errors.append(f"{d.name}: SKILL.md has no YAML frontmatter")
            continue
        name, desc = fm.get("name", ""), fm.get("description", "")
        if not name or not desc:
            errors.append(f"{d.name}: frontmatter needs both name and description")
        if name and name != d.name:
            errors.append(f"{d.name}: name '{name}' != folder name")
        if name and (not NAME_RE.match(name) or len(name) > 64):
            errors.append(f"{d.name}: name must be lowercase-hyphen, <= 64 chars")
        if len(desc) > 1024:
            errors.append(f"{d.name}: description is {len(desc)} chars (max 1024)")
        if not (d / "README.md").exists():
            errors.append(f"{d.name}: missing README.md")

        for f in d.rglob("*"):
            if f.is_file() and f.suffix in TEXT_SUFFIXES and terms:
                body = f.read_text(encoding="utf-8", errors="ignore")
                for t in terms:
                    if t in body:
                        errors.append(f"{f.relative_to(ROOT)}: contains private term '{t}'")

    note = f"{len(terms)} privacy terms" if terms else "no .privacy-denylist (privacy check skipped)"
    print(f"Checked {len(dirs)} skill(s), {note}.")
    for e in errors:
        print(f"✗ {e}")
    if errors:
        sys.exit(1)
    print("✓ All good.")


if __name__ == "__main__":
    main()
