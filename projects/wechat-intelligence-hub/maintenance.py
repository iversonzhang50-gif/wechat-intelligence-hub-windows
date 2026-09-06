from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


RAW_SUFFIXES = {".json", ".jsonl"}


@dataclass(frozen=True)
class CleanupCandidate:
    path: Path
    kind: str
    age_days: int
    size: int


def validate_cleanup_root(root: Path) -> Path:
    resolved = root.expanduser().resolve()
    forbidden = {Path("/").resolve(), Path.home().resolve(), Path.cwd().resolve()}
    if resolved in forbidden or resolved.name != "output":
        raise ValueError("清理目录必须是明确的 output 子目录，不能是项目根目录或用户目录")
    return resolved


def find_cleanup_candidates(
    root: Path,
    *,
    raw_days: int = 7,
    report_days: int = 30,
    now: datetime | None = None,
) -> list[CleanupCandidate]:
    resolved = validate_cleanup_root(root)
    if raw_days < 0 or report_days < 0:
        raise ValueError("保留天数不能小于 0")
    if not resolved.exists():
        return []

    current = now or datetime.now()
    candidates: list[CleanupCandidate] = []
    for path in resolved.rglob("*"):
        if not path.is_file():
            continue
        kind = "raw" if path.suffix.lower() in RAW_SUFFIXES or "raw" in path.name.lower() else "report"
        keep_days = raw_days if kind == "raw" else report_days
        age_days = max(0, int((current.timestamp() - path.stat().st_mtime) // 86400))
        if age_days >= keep_days:
            candidates.append(
                CleanupCandidate(
                    path=path,
                    kind=kind,
                    age_days=age_days,
                    size=path.stat().st_size,
                )
            )
    return sorted(candidates, key=lambda item: (item.kind, -item.age_days, str(item.path)))


def apply_cleanup(candidates: list[CleanupCandidate]) -> tuple[int, int]:
    removed = 0
    reclaimed = 0
    for candidate in candidates:
        candidate.path.unlink(missing_ok=True)
        removed += 1
        reclaimed += candidate.size
    return removed, reclaimed
