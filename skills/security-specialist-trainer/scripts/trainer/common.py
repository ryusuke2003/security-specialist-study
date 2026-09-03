"""Shared models, constants, paths, tables, and score primitives."""
from __future__ import annotations

import math
import os
import re
import stat
import tempfile
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterable, Optional
from zoneinfo import ZoneInfo



DIAGNOSTIC_DOMAIN_ORDER = [
    "Webセキュリティ",
    "ネットワークセキュリティ",
    "暗号",
    "認証・認可 / IAM",
    "PKI・証明書",
    "DNS",
    "メールセキュリティ",
    "マルウェア",
]


TERM_RECALL_MODE = "term-recall"


QUICK_REVIEW_MODE = "quick-review"


EXPLANATION_MODE = "explanation"


STANDARD_SESSION_MODE = "standard"


DEFAULT_NORMAL_QUESTION_COUNT = 6


NORMAL_SESSION_MODES = frozenset({"diagnosis", "adaptive"})


STANDARD_SESSION_DIRECTORY = "理解・応用問題"


TERM_RECALL_SESSION_DIRECTORY = "暗記語句問題"


QUICK_REVIEW_SESSION_DIRECTORY = "10分復習"


LEGACY_SESSION_DIRECTORIES = (STANDARD_SESSION_MODE, TERM_RECALL_MODE)


CURRENT_SESSIONS_DIRECTORY = "学習記録"


CURRENT_PROGRESS_DIRECTORY = "進捗"


CURRENT_REFERENCES_DIRECTORY = "参照資料"


STUDY_TIMEZONE = ZoneInfo("Asia/Tokyo")


STUDY_DAY_START_HOUR = 5


@dataclass(frozen=True)
class CatalogItem:
    term: str
    domain: str
    track: str
    importance: int
    entry_level: int
    diagnostic: bool
    prerequisites: str
    related: str


@dataclass(frozen=True)
class TermRecord:
    term: str
    domain: str
    score: int
    last_studied: Optional[date]
    attempts: int
    average: int
    last_level: int
    next_review: Optional[date]
    related: str
    notes: str
    track: str = "A/B"
    last_score: Optional[int] = None
    last_session: str = ""
    applied_sessions: tuple[str, ...] = ()
    recall_score: Optional[int] = None
    recall_attempts: int = 0
    explanation_score: Optional[int] = None
    explanation_attempts: int = 0
    recall_last_studied: Optional[date] = None
    recall_next_review: Optional[date] = None
    explanation_last_studied: Optional[date] = None
    explanation_next_review: Optional[date] = None


@dataclass(frozen=True)
class Candidate:
    item: CatalogItem
    priority: float
    weakness: float
    forgetting: float
    unseen: bool
    due: bool
    challenge: bool
    suggested_level: int
    reason: str


@dataclass(frozen=True)
class GradedQuestion:
    number: int
    domain: str
    track: str
    level: int
    primary_terms: tuple[str, ...]
    related_terms: tuple[str, ...]
    score: int
    good_point: str
    review_focus: str
    question_mode: str = EXPLANATION_MODE


@dataclass(frozen=True)
class UnansweredQuestion:
    study_date: date
    session_number: int
    question_number: int
    session_kind: str
    primary_terms: tuple[str, ...]
    session_link_path: str


@dataclass(frozen=True)
class UnreviewedItem:
    review_date: date
    term: str
    score: int
    review_link_path: str
    order: int


@dataclass(frozen=True)
class GradingCandidate:
    study_date: date
    session_number: int
    session_kind: str
    path: Path
    question_count: int


@dataclass(frozen=True)
class GradedActivity:
    study_date: date
    session_number: int
    session_kind: str
    question_count: int
    session_link_path: str


def current_study_date(now: Optional[datetime] = None) -> date:
    """Return the JST study date, which changes at 05:00 rather than midnight."""
    moment = now or datetime.now(STUDY_TIMEZONE)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=STUDY_TIMEZONE)
    else:
        moment = moment.astimezone(STUDY_TIMEZONE)
    if moment.hour < STUDY_DAY_START_HOUR:
        moment -= timedelta(days=1)
    return moment.date()


def study_directory(root: Path, current: str, legacy: str) -> Path:
    """Use the Japanese directory name, with English-only test data as a fallback."""
    current_path = root / current
    return current_path if current_path.exists() else root / legacy


def sessions_directory(root: Path) -> Path:
    return study_directory(root, CURRENT_SESSIONS_DIRECTORY, "sessions")


def progress_directory(root: Path) -> Path:
    return study_directory(root, CURRENT_PROGRESS_DIRECTORY, "progress")


def references_directory(root: Path) -> Path:
    return study_directory(root, CURRENT_REFERENCES_DIRECTORY, "references")


def localized_file(directory: Path, japanese_name: str, legacy_name: str) -> Path:
    """Use Japanese study files while preserving English-only fixture compatibility."""
    if directory.name in {"progress", "references"} and not (directory / japanese_name).exists():
        return directory / legacy_name
    return directory / japanese_name


def progress_file(root: Path, japanese_name: str, legacy_name: str) -> Path:
    return localized_file(progress_directory(root), japanese_name, legacy_name)


def reference_file(root: Path, japanese_name: str, legacy_name: str) -> Path:
    return localized_file(references_directory(root), japanese_name, legacy_name)


def split_markdown_row(line: str) -> list[str]:
    """Split the simple pipe tables used by this repository."""
    escaped = "\u0000"
    line = line.strip().replace("\\|", escaped)
    return [cell.strip().replace(escaped, "|") for cell in line.strip("|").split("|")]


def read_table(path: Path, required_first_column: str) -> list[dict[str, str]]:
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    for index, line in enumerate(lines):
        if not line.lstrip().startswith("|"):
            continue
        headers = split_markdown_row(line)
        if not headers or headers[0] != required_first_column:
            continue
        rows: list[dict[str, str]] = []
        for row_line in lines[index + 2 :]:
            if not row_line.lstrip().startswith("|"):
                break
            values = split_markdown_row(row_line)
            if len(values) != len(headers):
                continue
            rows.append(dict(zip(headers, values)))
        return rows
    return []


def as_int(value: str, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def as_date(value: str) -> Optional[date]:
    if not value or value == "—":
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def optional_score(value: str) -> Optional[int]:
    score = as_int(value, -1)
    if score < 0:
        return None
    return max(0, min(100, score))


def load_catalog(root: Path) -> list[CatalogItem]:
    rows = read_table(reference_file(root, "出題分類と概念カタログ.md", "taxonomy.md"), "Term")
    result = []
    for row in rows:
        result.append(
            CatalogItem(
                term=row["Term"],
                domain=row["Domain"],
                track=row["Track"],
                importance=as_int(row["Importance"], 3),
                entry_level=as_int(row["Entry Level"], 2),
                diagnostic=row["Diagnostic"].lower() == "yes",
                prerequisites=row["Prerequisites"],
                related=row["Related"],
            )
        )
    return result


def load_terms(root: Path) -> dict[str, TermRecord]:
    rows = read_table(progress_file(root, "語句別理解度.md", "terms.md"), "Term")
    result: dict[str, TermRecord] = {}
    for row in rows:
        score = as_int(row.get("Score", ""), -1)
        if score < 0:
            continue
        last_session = row.get("Last Session", "")
        if last_session == "—":
            last_session = ""
        applied_sessions = tuple(
            value.strip()
            for value in row.get("Applied Sessions", "").split(",")
            if value.strip() and value.strip() != "—"
        )
        if not applied_sessions and last_session:
            applied_sessions = (last_session,)
        has_mode_columns = "Recall Score" in row or "Explanation Score" in row
        explanation_score = (
            optional_score(row.get("Explanation Score", "")) if has_mode_columns else score
        )
        explanation_attempts = (
            as_int(row.get("Explanation Attempts", "0"))
            if has_mode_columns
            else as_int(row.get("Attempts", "0"))
        )
        result[row["Term"]] = TermRecord(
            term=row["Term"],
            domain=row["Domain"],
            score=max(0, min(100, score)),
            last_studied=as_date(row.get("Last Studied", "")),
            attempts=as_int(row.get("Attempts", "0")),
            average=as_int(row.get("Average", str(score)), score),
            last_level=as_int(row.get("Last Level", "1"), 1),
            next_review=as_date(row.get("Next Review", "")),
            related=row.get("Related", ""),
            notes=row.get("Notes", ""),
            track=row.get("Track", "A/B") if row.get("Track", "A/B") in {"A", "A/B", "B"} else "A/B",
            last_score=(
                None
                if as_int(row.get("Last Score", ""), -1) < 0
                else max(0, min(100, as_int(row.get("Last Score", ""), -1)))
            ),
            last_session=last_session,
            applied_sessions=applied_sessions,
            recall_score=optional_score(row.get("Recall Score", "")),
            recall_attempts=as_int(row.get("Recall Attempts", "0")),
            explanation_score=explanation_score,
            explanation_attempts=explanation_attempts,
            recall_last_studied=(
                as_date(row.get("Recall Last Studied", ""))
                or (as_date(row.get("Last Studied", "")) if as_int(row.get("Recall Attempts", "0")) else None)
            ),
            recall_next_review=(
                as_date(row.get("Recall Next Review", ""))
                or (as_date(row.get("Next Review", "")) if as_int(row.get("Recall Attempts", "0")) else None)
            ),
            explanation_last_studied=(
                as_date(row.get("Explanation Last Studied", ""))
                or (as_date(row.get("Last Studied", "")) if explanation_attempts else None)
            ),
            explanation_next_review=(
                as_date(row.get("Explanation Next Review", ""))
                or (as_date(row.get("Next Review", "")) if explanation_attempts else None)
            ),
        )
    return result


def merge_uncatalogued_terms(catalog: list[CatalogItem], terms: dict[str, TermRecord]) -> list[CatalogItem]:
    """Keep hand-added progress terms eligible even when absent from taxonomy."""
    merged = list(catalog)
    known = {item.term for item in merged}
    for record in terms.values():
        if record.term in known:
            continue
        merged.append(
            CatalogItem(
                term=record.term,
                domain=record.domain,
                track=record.track,
                importance=3,
                entry_level=target_level(record.score),
                diagnostic=False,
                prerequisites="",
                related=record.related,
            )
        )
    return merged


def base_interval(score: int) -> int:
    if score < 40:
        return 1
    if score < 60:
        return 2
    if score < 75:
        return 5
    if score < 90:
        return 12
    return 30


def target_level(score: Optional[int], entry_level: int = 2) -> int:
    if score is None:
        return max(1, min(3, entry_level))
    if score < 40:
        return 1
    if score < 60:
        return 2
    if score < 75:
        return 3
    if score < 88:
        return 4
    if score < 95:
        return 5
    return 6


def level_cap(level: int) -> int:
    return {1: 70, 2: 80, 3: 88, 4: 94, 5: 100, 6: 100}.get(level, 100)


def blend_mastery(old_score: Optional[int], attempts: int, evidence: int, answer_score: int) -> int:
    evidence = max(0, min(100, evidence))
    if old_score is None or attempts <= 0:
        return evidence
    alpha = 0.45 if attempts <= 2 else 0.35 if attempts <= 5 else 0.30
    if answer_score < 40:
        alpha += 0.10
    return round(old_score * (1 - alpha) + evidence * alpha)


def updated_mastery(old_score: Optional[int], attempts: int, answer_score: int, level: int) -> int:
    evidence = min(max(answer_score, 0), level_cap(level))
    return blend_mastery(old_score, attempts, evidence, answer_score)


def updated_recall_mastery(old_score: Optional[int], attempts: int, answer_score: int) -> int:
    """Track definition recall on its own 0-100 scale without the overall Level 1 cap."""
    return blend_mastery(old_score, attempts, answer_score, answer_score)


def next_interval(score: int, answer_score: int, level: int, stable_high_count: int = 0) -> int:
    interval = float(base_interval(score))
    if answer_score < 60:
        interval = max(1.0, interval / 2)
    elif answer_score >= 90 and level >= 4:
        interval *= 1.25
    if answer_score >= 90 and level >= 5 and stable_high_count >= 2:
        interval = max(interval, base_interval(score) * 1.5)
    return max(1, round(interval))


def markdown_cell(value: object) -> str:
    return str(value).replace("\n", " ").replace("|", "\\|").strip()


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o644
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        handle.write(text)
        temporary = Path(handle.name)
    os.chmod(temporary, mode)
    os.replace(temporary, path)


def _clean_term(value: str) -> str:
    return value.strip().strip("`").strip()


def parse_list_field(section: str, label: str) -> tuple[str, ...]:
    match = re.search(rf"^- {re.escape(label)}:[ \t]*([^\r\n]*)$", section, flags=re.MULTILINE)
    if not match:
        return ()
    inline = _clean_term(match.group(1))
    if inline:
        return (inline,)
    values = []
    for line in section[match.end() :].splitlines():
        if not line.strip():
            continue
        item = re.match(r"^\s{2,}-\s+(.+?)\s*$", line)
        if not item:
            break
        values.append(_clean_term(item.group(1)))
    return tuple(value for value in values if value)


def _first_feedback_bullet(section: str, heading: str) -> str:
    match = re.search(rf"^#### {re.escape(heading)}[ \t]*$", section, flags=re.MULTILINE)
    if not match:
        return ""
    for line in section[match.end() :].splitlines():
        if line.startswith("#### ") or line.startswith("### "):
            break
        bullet = re.match(r"^-\s+(.+?)\s*$", line)
        if bullet:
            return bullet.group(1).strip()
    return ""


def quick_review_checked_choices(question: str) -> tuple[str, ...]:
    """Return checked A/B/C task-list choices in a quick-review question."""
    return tuple(
        match.group(1)
        for match in re.finditer(
            r"^- \[[xX]\][ \t]+([ABC])\.[ \t]+",
            question,
            flags=re.MULTILINE,
        )
    )


def term_recall_track_counts(count: int) -> tuple[int, int]:
    """Allocate whole questions to A first, leaving every fractional remainder to B."""
    a_count = math.floor(count * 0.40)
    return a_count, count - a_count
