"""Cross-platform SpecKit & FR-XXX requirement traceability matrix generator.

Spec: specs/033-parallel-testing-and-qa-matrix/spec.md (FR-010)
"""

from __future__ import annotations

import argparse
import re
from datetime import datetime, timezone
from pathlib import Path

SPEC_DIR_RE = re.compile(r"^(\d{3})-(.+)$")
SPEC_DECL_RE = re.compile(r"^\s*#\s*spec:\s*(\d{3})\b")
FR_ID_RE = re.compile(r"\bFR-\d{3}\b")


def _collect_feature_files(repo: Path, features_dir: str) -> list[Path]:
    found: list[Path] = []
    for rel in (features_dir, "features"):
        folder = repo / rel
        if folder.is_dir():
            found.extend(sorted(folder.glob("*.feature")))
    # Deduplicate while preserving deterministic order
    seen: set[Path] = set()
    unique: list[Path] = []
    for f in found:
        resolved = f.resolve()
        if resolved not in seen:
            seen.add(resolved)
            unique.append(f)
    return unique


def _map_declared_specs(features: list[Path]) -> dict[str, Path]:
    declared: dict[str, Path] = {}
    for feat in features:
        lines = feat.read_text(encoding="utf-8", errors="replace").splitlines()[:5]
        for line in lines:
            match = SPEC_DECL_RE.match(line)
            if match:
                declared.setdefault(match.group(1), feat)
                break
    return declared


def _best_slug_feature(words: list[str], features: list[Path]) -> Path | None:
    best: tuple[int, Path] | None = None
    for feat in features:
        base = feat.stem.lower()
        hits = [w for w in words if w in base]
        long_hits = [w for w in hits if len(w) >= 7]
        score = len(hits) + len(long_hits)
        if score >= 2 and (best is None or score > best[0]):
            best = (score, feat)
    return best[1] if best is not None else None


def _best_adr(words: list[str], adrs: list[Path]) -> Path | None:
    for adr in adrs:
        base = adr.stem.lower()
        hits = [w for w in words if w in base]
        if len(hits) >= 2:
            return adr
    return None


def generate_traceability(
    repo: Path, features_dir: str = "tests/features"
) -> tuple[str, dict[str, int]]:
    repo = repo.resolve()
    spec_dirs = sorted(
        d for d in (repo / "specs").iterdir() if d.is_dir() and SPEC_DIR_RE.match(d.name)
    )
    features = _collect_feature_files(repo, features_dir)
    adrs = sorted((repo / "docs" / "adr").glob("*.md")) if (repo / "docs" / "adr").is_dir() else []
    declared = _map_declared_specs(features)

    rows: list[str] = []
    gaps = 0
    total_frs = 0

    for spec_dir in spec_dirs:
        num = spec_dir.name[:3]
        slug = spec_dir.name[4:]
        spec_md = spec_dir / "spec.md"
        has_spec = spec_md.is_file()
        has_plan = (spec_dir / "plan.md").is_file()
        has_tasks = (spec_dir / "tasks.md").is_file()
        if has_spec:
            total_frs += len(set(FR_ID_RE.findall(spec_md.read_text(encoding="utf-8"))))

        words = [w.lower() for w in slug.split("-") if len(w) > 3]
        feat = declared.get(num) or _best_slug_feature(words, features)
        adr = _best_adr(words, adrs)

        if feat is not None:
            feat_rel = feat.resolve().relative_to(repo).as_posix()
            feat_cell = f"[{feat.name}](../{feat_rel})"
        else:
            gaps += 1
            feat_cell = "none"

        adr_cell = f"[{adr.stem[:40]}](adr/{adr.name})" if adr is not None else "none"
        s_mark = "yes" if has_spec else "no"
        p_mark = "yes" if has_plan else "no"
        t_mark = "yes" if has_tasks else "no"
        rows.append(
            f"| [{spec_dir.name}](../specs/{spec_dir.name}/) | "
            f"{s_mark} | {p_mark} | {t_mark} | {feat_cell} | {adr_cell} |"
        )

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    norm_fdir = features_dir.replace("\\", "/")
    header = (
        "# Traceability\n\n"
        f"> Generated {today} by `scripts/traceability.py` from `specs/`, `{norm_fdir}/` "
        "and `docs/adr/`. Regenerate rather than edit. A feature with no acceptance file is "
        f"a gap, listed as `none`; {gaps} of {len(spec_dirs)} specs have no matched feature "
        "file today.\n\n"
        "A feature file that opens with a comment of the form `# spec: NNN-slug` is matched "
        "to that spec outright. Otherwise matching is by shared slug words (two words, or one "
        "word of seven or more letters); a row marked `none` may have coverage under a "
        "different name. The honest reading is the gap count, not the match count.\n\n"
        "| Spec | spec.md | plan.md | tasks.md | Acceptance feature | ADR |\n"
        "| --- | --- | --- | --- | --- | --- |\n"
    )
    stats = {
        "specs": len(spec_dirs),
        "features": len(features),
        "adrs": len(adrs),
        "gaps": gaps,
        "frs": total_frs,
    }
    return header + "\n".join(rows) + "\n", stats


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate cross-platform ALOS traceability report."
    )
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--features-dir", type=str, default="tests/features")
    parser.add_argument("--out", type=str, default="docs/traceability.md")
    parser.add_argument("--dry-run", action="store_true", help="Compute stats without writing file")
    args = parser.parse_args(argv)

    content, stats = generate_traceability(args.repo, args.features_dir)
    if not args.dry_run:
        out_path = args.repo / args.out
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(content, encoding="utf-8", newline="\n")
    print(
        f"specs={stats['specs']} features={stats['features']} adrs={stats['adrs']} "
        f"frs={stats['frs']} gaps={stats['gaps']} -> {args.out}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
