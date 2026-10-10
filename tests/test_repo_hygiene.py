"""Criteria 16 + 17."""
import subprocess

from signals import ROOT


def test_no_openrouter_keys_anywhere():
    hits = []
    for p in ROOT.rglob("*"):
        if p.is_file() and not any(x in p.parts for x in (".git", ".venv", "__pycache__")):
            try:
                if b"".join([b"sk", b"-or-"]) in p.read_bytes():
                    hits.append(str(p))
            except OSError:
                pass
    assert hits == []


def test_env_gitignored():
    assert ".env" in (ROOT / ".gitignore").read_text().split()


def test_readme_sections():
    r = (ROOT / "README.md").read_text()
    for field in ("account name", "open roles", "hiring momentum", "last funding", "news mentions", "HN mentions", "employee count",
                  "contact role titles", "paid seats", "first-use date", "owner_rep"):
        assert field in r, field
    assert "## Why this, for this role" in r and "](https://boards.greenhouse.io/figma/jobs/6013495004)" in r
    assert "](https://www.clay.com/customers/figma)" in r
    assert "## Paid options" in r and "Brave Search API" in r and "Crunchbase" in r and "Apollo" in r
