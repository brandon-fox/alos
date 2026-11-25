"""Leak scanner for diffs the build executor drafts.

Spec: specs/039-self-correcting-build-executor/spec.md (FR-3904 step 7)
"""

from __future__ import annotations

from pathlib import Path

from alos.swarm.build.leak import describe, load_terms, scan_diff

USERS = "Us" + "ers"
HOME = "ho" + "me"
BS = chr(92)
MAIL = "a@" + "gmail" + ".com"


def diff_adding(*lines: str) -> str:
    body = "\n".join(f"+{ln}" for ln in lines)
    return f"--- a/x.py\n+++ b/x.py\n@@ -0,0 +1,{len(lines)} @@\n{body}\n"


def test_clean_diff_has_no_findings() -> None:
    assert scan_diff(diff_adding("def add(a, b):", "    return a + b")) == []


def test_windows_and_posix_home_paths_are_found() -> None:
    win = "C:" + BS + USERS + BS + "someone" + BS + "repo"
    posix = "/" + HOME + "/someone/repo"
    found = scan_diff(diff_adding(f'p = "{win}"', f'q = "{posix}"'))
    assert [f.kind for f in found] == ["local path", "local path"]
    assert [f.line for f in found] == [4, 5]


def test_personal_email_is_found_but_noreply_is_not() -> None:
    assert scan_diff(diff_adding(MAIL))[0].kind == "personal email"
    assert scan_diff(diff_adding("1+someone@users.noreply.github.com")) == []


def test_only_added_lines_are_scanned() -> None:
    diff = "--- a/x.py\n+++ b/x.py\n@@ -1 +1 @@\n-p = '/" + HOME + "/someone/x'\n+p = 'x'\n"
    assert scan_diff(diff) == []


def test_private_terms_match_whole_words_and_are_not_echoed() -> None:
    found = scan_diff(diff_adding("owner = 'zebra42'", "other = 'zebra420'"), ["zebra42"])
    assert [(f.kind, f.line) for f in found] == [("private term", 4)]
    assert "zebra42" not in describe(found)


def test_terms_file_skips_blanks_and_comments(tmp_path: Path) -> None:
    f = tmp_path / "terms.txt"
    f.write_text("# private\n\nzebra42\n  box-one \n", encoding="utf-8")
    assert load_terms(f) == ["zebra42", "box-one"]
    assert load_terms(tmp_path / "missing.txt") == []


def test_an_added_line_that_starts_with_plus_signs_is_still_scanned() -> None:
    diff = "--- a/x.c\n+++ b/x.c\n@@ -1 +1,2 @@\n x\n+++counter; // " + MAIL + "\n"
    assert [f.kind for f in scan_diff(diff)] == ["personal email"]
