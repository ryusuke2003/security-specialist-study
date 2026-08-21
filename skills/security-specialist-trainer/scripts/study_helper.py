#!/usr/bin/env python3
"""Plan topics and idempotently record model-scored study results in Markdown.

Question authoring and semantic grading remain model-led. The record command
performs deterministic arithmetic and atomic Markdown state updates.
"""

from __future__ import annotations

import argparse
import hashlib
import math
import os
import re
import stat
import sys
import tempfile
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterable, Optional


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
EXPLANATION_MODE = "explanation"
STANDARD_SESSION_MODE = "standard"
DEFAULT_NORMAL_QUESTION_COUNT = 6
NORMAL_SESSION_MODES = frozenset({"diagnosis", "adaptive"})
STANDARD_SESSION_DIRECTORY = "理解・応用問題"
TERM_RECALL_SESSION_DIRECTORY = "暗記語句問題"
LEGACY_SESSION_DIRECTORIES = (STANDARD_SESSION_MODE, TERM_RECALL_MODE)
CURRENT_SESSIONS_DIRECTORY = "学習記録"
CURRENT_PROGRESS_DIRECTORY = "進捗"
CURRENT_REFERENCES_DIRECTORY = "参照資料"


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


def session_bounds(text: str, session_number: int) -> tuple[int, int]:
    headings = list(re.finditer(r"^## Session (\d+)[ \t]*$", text, flags=re.MULTILINE))
    for index, heading in enumerate(headings):
        if int(heading.group(1)) != session_number:
            continue
        end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        return heading.start(), end
    raise ValueError(f"Session {session_number} not found")


def session_file_paths(root: Path) -> list[Path]:
    """Return current Session files plus legacy English and root-level files."""
    sessions_root = sessions_directory(root)
    paths = [
        *sessions_root.glob("*.md"),
        *(sessions_root / STANDARD_SESSION_DIRECTORY).glob("*.md"),
        *(sessions_root / TERM_RECALL_SESSION_DIRECTORY).glob("*.md"),
    ]
    for directory in LEGACY_SESSION_DIRECTORIES:
        paths.extend((sessions_root / directory).glob("*.md"))
    return sorted(
        {path for path in paths if as_date(path.stem) is not None},
        key=lambda path: (as_date(path.stem) or date.min, path.as_posix()),
    )


def unanswered_questions(root: Path) -> list[UnansweredQuestion]:
    """Find question blocks whose answer contains only the standard placeholder."""
    unanswered: list[UnansweredQuestion] = []
    for path in session_file_paths(root):
        study_date = as_date(path.stem)
        if study_date is None:
            continue
        text = path.read_text(encoding="utf-8")
        session_headings = list(
            re.finditer(r"^## Session ([1-9][0-9]*)[ \t]*$", text, flags=re.MULTILINE)
        )
        for session_index, session_heading in enumerate(session_headings):
            session_end = (
                session_headings[session_index + 1].start()
                if session_index + 1 < len(session_headings)
                else len(text)
            )
            session = text[session_heading.start() : session_end]
            if re.search(r"^- Status:[ \t]*cancelled[ \t]*$", session, flags=re.MULTILINE):
                continue
            session_number = int(session_heading.group(1))
            try:
                mode = session_mode_for_path(root, path, text, session_number)
            except ValueError:
                mode = TERM_RECALL_MODE if path.parent.name == TERM_RECALL_SESSION_DIRECTORY else STANDARD_SESSION_MODE
            session_kind = "暗記語句問題" if mode == TERM_RECALL_MODE else "理解・応用問題"
            question_headings = list(
                re.finditer(r"^### Q([1-9][0-9]*)[ \t]*$", session, flags=re.MULTILINE)
            )
            for question_index, question_heading in enumerate(question_headings):
                question_end = (
                    question_headings[question_index + 1].start()
                    if question_index + 1 < len(question_headings)
                    else len(session)
                )
                question = session[question_heading.start() : question_end]
                answer_match = re.search(
                    r"^### 回答[ \t]*\n(?P<answer>.*?)(?=^### |\Z)",
                    question,
                    flags=re.MULTILINE | re.DOTALL,
                )
                if answer_match is None:
                    continue
                answer = re.sub(r"<!--.*?-->", "", answer_match.group("answer"), flags=re.DOTALL)
                if answer.strip():
                    continue
                primary_terms = parse_list_field(question, "Primary Terms")
                unanswered.append(
                    UnansweredQuestion(
                        study_date=study_date,
                        session_number=session_number,
                        question_number=int(question_heading.group(1)),
                        session_kind=session_kind,
                        primary_terms=primary_terms,
                        session_link_path=Path(
                            os.path.relpath(path, progress_directory(root))
                        ).as_posix(),
                    )
                )
    return sorted(
        unanswered,
        key=lambda item: (item.study_date, item.session_number, item.question_number),
    )


def unanswered_primary_terms(root: Path) -> set[str]:
    """Return terms already assigned to unanswered questions."""
    return {
        term
        for question in unanswered_questions(root)
        for term in question.primary_terms
    }


def render_unanswered_index(questions: list[UnansweredQuestion]) -> str:
    lines = ["# 未解答一覧", ""]
    if not questions:
        lines.append("未解答はありません。")
        return "\n".join(lines) + "\n"
    for kind in ("理解・応用問題", "暗記語句問題"):
        entries = [question for question in questions if question.session_kind == kind]
        if not entries:
            continue
        lines.extend([f"## {kind}", ""])
        grouped: dict[tuple[date, int, str], list[int]] = {}
        for question in entries:
            grouped.setdefault(
                (
                    question.study_date,
                    question.session_number,
                    question.session_link_path,
                ),
                [],
            ).append(question.question_number)
        for (study_date, session_number, session_link_path), numbers in grouped.items():
            ranges: list[str] = []
            range_start = range_end = numbers[0]
            for number in numbers[1:]:
                if number == range_end + 1:
                    range_end = number
                    continue
                ranges.append(
                    f"Q{range_start}"
                    if range_start == range_end
                    else f"Q{range_start}~{range_end}"
                )
                range_start = range_end = number
            ranges.append(
                f"Q{range_start}"
                if range_start == range_end
                else f"Q{range_start}~{range_end}"
            )
            lines.append(
                f"- [{study_date.isoformat()} / Session {session_number} / "
                f"{', '.join(ranges)}]({session_link_path})"
            )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_unanswered_index(root: Path) -> Path:
    path = progress_directory(root) / "未解答一覧.md"
    atomic_write(path, render_unanswered_index(unanswered_questions(root)))
    return path


def session_path_for_mode(root: Path, study_date: date, mode: str) -> Path:
    directory = (
        TERM_RECALL_SESSION_DIRECTORY
        if mode == TERM_RECALL_MODE
        else STANDARD_SESSION_DIRECTORY
    )
    return sessions_directory(root) / directory / f"{study_date.isoformat()}.md"


def session_mode(
    text: str,
    session_number: int,
    allow_missing: bool = True,
) -> str:
    start, end = session_bounds(text, session_number)
    section = text[start:end]
    values = re.findall(r"^- Mode:[ \t]*(\S+)[ \t]*$", section, flags=re.MULTILINE)
    if not values:
        if allow_missing:
            return STANDARD_SESSION_MODE
        raise ValueError(f"Session {session_number} must have exactly one Mode")
    if len(values) != 1:
        raise ValueError(f"Session {session_number} must have exactly one Mode")
    value = values[0]
    if value == TERM_RECALL_MODE:
        return TERM_RECALL_MODE
    if value in NORMAL_SESSION_MODES:
        return STANDARD_SESSION_MODE
    allowed = ", ".join(sorted((*NORMAL_SESSION_MODES, TERM_RECALL_MODE)))
    raise ValueError(
        f"Session {session_number} has unsupported Mode {value!r}; expected one of: {allowed}"
    )


def is_legacy_session_path(root: Path, path: Path) -> bool:
    sessions_root = sessions_directory(root)
    return path.parent == sessions_root or (
        path.parent.parent == sessions_root
        and path.parent.name in LEGACY_SESSION_DIRECTORIES
    )


def expected_mode_for_current_path(root: Path, path: Path) -> Optional[str]:
    sessions_root = sessions_directory(root)
    if path.parent == sessions_root / STANDARD_SESSION_DIRECTORY:
        return STANDARD_SESSION_MODE
    if path.parent == sessions_root / TERM_RECALL_SESSION_DIRECTORY:
        return TERM_RECALL_MODE
    return None


def session_mode_for_path(
    root: Path,
    path: Path,
    text: str,
    session_number: int,
) -> str:
    actual_mode = session_mode(
        text,
        session_number,
        allow_missing=is_legacy_session_path(root, path),
    )
    expected_mode = expected_mode_for_current_path(root, path)
    if expected_mode is not None and actual_mode != expected_mode:
        raise ValueError(
            f"Session {session_number} under {path.parent} must use {expected_mode} mode, "
            f"not {actual_mode}"
        )
    return actual_mode


def next_session_number(root: Path, study_date: date) -> int:
    numbers = []
    for path in session_file_paths(root):
        if as_date(path.stem) != study_date:
            continue
        text = path.read_text(encoding="utf-8")
        numbers.extend(
            int(match.group(1))
            for match in re.finditer(r"^## Session (\d+)[ \t]*$", text, flags=re.MULTILINE)
        )
    return max(numbers, default=0) + 1


def resolve_session_path(
    root: Path,
    study_date: date,
    session_number: int,
    mode: Optional[str] = None,
) -> Path:
    matches: list[tuple[Path, str]] = []
    for path in session_file_paths(root):
        if as_date(path.stem) != study_date:
            continue
        text = path.read_text(encoding="utf-8")
        try:
            session_bounds(text, session_number)
        except ValueError:
            continue
        actual_mode = session_mode_for_path(root, path, text, session_number)
        matches.append((path, actual_mode))
    if not matches:
        expected = session_path_for_mode(root, study_date, mode or STANDARD_SESSION_MODE)
        raise ValueError(f"Session {session_number} not found for {study_date}: expected under {expected.parent}")
    if len(matches) > 1:
        paths = ", ".join(str(path) for path, _ in matches)
        raise ValueError(
            f"Session {study_date.isoformat()}#{session_number} exists in multiple files: {paths}"
        )
    path, actual_mode = matches[0]
    if mode is not None and actual_mode != mode:
        raise ValueError(
            f"Session {study_date.isoformat()}#{session_number} is {actual_mode}, not {mode}: {path}"
        )
    return path


def parse_graded_session(
    text: str,
    session_number: int,
    allow_missing_mode: bool = True,
) -> tuple[str, list[GradedQuestion]]:
    start, end = session_bounds(text, session_number)
    session = text[start:end]
    status_match = re.search(r"^- Status:[ \t]*(\S+)[ \t]*$", session, flags=re.MULTILINE)
    if not status_match:
        raise ValueError(f"Session {session_number} has no Status")
    status = status_match.group(1)
    parsed_mode = session_mode(text, session_number, allow_missing=allow_missing_mode)
    question_mode = TERM_RECALL_MODE if parsed_mode == TERM_RECALL_MODE else EXPLANATION_MODE
    question_count_values = re.findall(
        r"^- Question Count:[ \t]*(.*?)[ \t]*$", session, flags=re.MULTILINE
    )
    if len(question_count_values) != 1:
        raise ValueError(
            f"Session {session_number} must have exactly one Question Count"
        )
    question_count_text = question_count_values[0]
    if not re.fullmatch(r"\d+", question_count_text):
        raise ValueError(f"Session {session_number} Question Count must be an integer")
    question_count = int(question_count_text)
    if not 1 <= question_count <= 30:
        raise ValueError(
            f"Session {session_number} Question Count must be between 1 and 30"
        )
    question_heading_candidates = list(
        re.finditer(r"^###[ \t]+Q[^\r\n]*$", session, flags=re.MULTILINE)
    )
    invalid_question_headings = [
        heading.group(0).strip()
        for heading in question_heading_candidates
        if not re.fullmatch(r"### Q[1-9][0-9]*[ \t]*", heading.group(0))
    ]
    if invalid_question_headings:
        invalid = ", ".join(invalid_question_headings)
        raise ValueError(
            f"Session {session_number} has invalid question headings: {invalid}"
        )
    question_headings = list(
        re.finditer(r"^### Q([1-9][0-9]*)[ \t]*$", session, flags=re.MULTILINE)
    )
    if len(question_headings) != question_count:
        raise ValueError(
            f"Session {session_number} Question Count is {question_count}, "
            f"but found {len(question_headings)} question headings"
        )
    actual_question_numbers = [heading.group(1) for heading in question_headings]
    expected_question_numbers = [str(number) for number in range(1, question_count + 1)]
    if actual_question_numbers != expected_question_numbers:
        actual = ", ".join(f"Q{number}" for number in actual_question_numbers)
        expected = ", ".join(f"Q{number}" for number in expected_question_numbers)
        raise ValueError(
            f"Session {session_number} question headings must be consecutive and unique "
            f"from Q1; expected {expected}, got {actual}"
        )
    questions: list[GradedQuestion] = []
    seen_primary: set[str] = set()
    for index, heading in enumerate(question_headings):
        question_end = question_headings[index + 1].start() if index + 1 < len(question_headings) else len(session)
        block = session[heading.start() : question_end]
        domain_match = re.search(r"^- Domain:[ \t]*(.+?)[ \t]*$", block, flags=re.MULTILINE)
        track_match = re.search(r"^- Track:[ \t]*(A/B|A|B)[ \t]*$", block, flags=re.MULTILINE)
        level_match = re.search(r"^- Level:[ \t]*([1-6])[ \t]*$", block, flags=re.MULTILINE)
        score_match = re.search(
            r"^Score:[ \t]*(\d{1,3})[ \t]*/[ \t]*100[ \t]*$",
            block,
            flags=re.MULTILINE,
        )
        primary = parse_list_field(block, "Primary Terms")
        if not primary:
            legacy = parse_list_field(block, "Terms")
            primary = legacy
        related = parse_list_field(block, "Related Terms")
        if not all((domain_match, track_match, level_match, score_match, primary)):
            raise ValueError(f"Q{heading.group(1)} is missing metadata or Score")
        score = int(score_match.group(1))
        if not 0 <= score <= 100:
            raise ValueError(f"Q{heading.group(1)} has an invalid Score")
        duplicates = seen_primary.intersection(primary)
        if duplicates:
            raise ValueError(f"Primary Terms repeated in one session: {', '.join(sorted(duplicates))}")
        seen_primary.update(primary)
        questions.append(
            GradedQuestion(
                number=int(heading.group(1)),
                domain=domain_match.group(1).strip(),
                track=track_match.group(1),
                level=int(level_match.group(1)),
                primary_terms=primary,
                related_terms=related,
                score=score,
                good_point=_first_feedback_bullet(block, "良かった点"),
                review_focus=_first_feedback_bullet(block, "次回確認する観点"),
                question_mode=question_mode,
            )
        )
    if not questions:
        raise ValueError(f"Session {session_number} has no questions")
    if question_mode == TERM_RECALL_MODE:
        if any(len(question.primary_terms) != 1 for question in questions):
            raise ValueError(
                "term-recall questions must have exactly one Primary Term each"
            )
        if any(question.level != 1 for question in questions):
            raise ValueError("term-recall questions must use Level 1")
        if any(question.track not in {"A", "B"} for question in questions):
            raise ValueError("term-recall questions must use Track A or B")
        expected_a, expected_b = term_recall_track_counts(question_count)
        actual_a = sum(question.track == "A" for question in questions)
        actual_b = sum(question.track == "B" for question in questions)
        if (actual_a, actual_b) != (expected_a, expected_b):
            raise ValueError(
                "term-recall Track allocation must be "
                f"A {expected_a} / B {expected_b}; got A {actual_a} / B {actual_b}"
            )
    return status, questions


def render_terms(records: dict[str, TermRecord]) -> str:
    lines = [
        "# 語句・概念ごとの理解度",
        "",
        "`Score` は両モードを合わせた現在の総合理解度です。`Recall Score` は暗記語句、`Explanation Score` は通常説明で確認した理解度、`Average` は全問題点の平均です。RecallとExplanationの最終学習日・復習期限は別々に管理し、共通の`Next Review`は早い方を表示します。日付は `YYYY-MM-DD`、未設定値は `—` とし、`Applied Sessions` は採点の二重反映を防ぐ台帳です。",
        "",
        "| Term | Domain | Track | Score | Recall Score | Explanation Score | Last Studied | Recall Last Studied | Explanation Last Studied | Last Session | Applied Sessions | Attempts | Recall Attempts | Explanation Attempts | Average | Last Score | Last Level | Next Review | Recall Next Review | Explanation Next Review | Related | Notes |",
        "|---|---|---|---:|---:|---:|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---|---|---|---|---|",
    ]
    for record in records.values():
        values = [
            record.term,
            record.domain,
            record.track,
            record.score,
            record.recall_score if record.recall_score is not None else "—",
            record.explanation_score if record.explanation_score is not None else "—",
            record.last_studied.isoformat() if record.last_studied else "—",
            record.recall_last_studied.isoformat() if record.recall_last_studied else "—",
            record.explanation_last_studied.isoformat() if record.explanation_last_studied else "—",
            record.last_session or "—",
            ", ".join(record.applied_sessions) or "—",
            record.attempts,
            record.recall_attempts,
            record.explanation_attempts,
            record.average,
            record.last_score if record.last_score is not None else "—",
            record.last_level,
            record.next_review.isoformat() if record.next_review else "—",
            record.recall_next_review.isoformat() if record.recall_next_review else "—",
            record.explanation_next_review.isoformat() if record.explanation_next_review else "—",
            record.related or "—",
            record.notes or "—",
        ]
        lines.append("| " + " | ".join(markdown_cell(value) for value in values) + " |")
    return "\n".join(lines) + "\n"


def update_term_records(
    root: Path,
    study_date: date,
    session_number: int,
    questions: list[GradedQuestion],
    catalog: list[CatalogItem],
) -> dict[str, TermRecord]:
    records = load_terms(root)
    catalog_by_term = {item.term: item for item in catalog}
    session_key = f"{study_date.isoformat()}#{session_number}"
    for question in questions:
        for term in question.primary_terms:
            old = records.get(term)
            if not old or session_key in old.applied_sessions or not old.last_session:
                continue
            try:
                last_day_text, last_number_text = old.last_session.rsplit("#", 1)
                last_order = (datetime.strptime(last_day_text, "%Y-%m-%d").date(), int(last_number_text))
            except (ValueError, TypeError):
                continue
            if last_order > (study_date, session_number):
                raise ValueError(
                    f"{term} already contains newer evidence from {old.last_session}; record sessions chronologically"
                )
    for question in questions:
        for term in question.primary_terms:
            old = records.get(term)
            if old and session_key in old.applied_sessions:
                continue
            old_score = old.score if old else None
            old_attempts = old.attempts if old else 0
            new_score = updated_mastery(old_score, old_attempts, question.score, question.level)
            new_attempts = old_attempts + 1
            old_total = (old.average * old_attempts) if old else 0
            new_average = round((old_total + question.score) / new_attempts)
            stable_high = (
                2
                if old
                and old.last_score is not None
                and old.last_score >= 90
                and old.last_level >= 5
                and question.score >= 90
                else 0
            )
            recall_score = old.recall_score if old else None
            recall_attempts = old.recall_attempts if old else 0
            explanation_score = old.explanation_score if old else None
            explanation_attempts = old.explanation_attempts if old else 0
            recall_last_studied = old.recall_last_studied if old else None
            recall_next_review = old.recall_next_review if old else None
            explanation_last_studied = old.explanation_last_studied if old else None
            explanation_next_review = old.explanation_next_review if old else None
            if question.question_mode == TERM_RECALL_MODE:
                recall_score = updated_recall_mastery(recall_score, recall_attempts, question.score)
                recall_attempts += 1
                recall_last_studied = study_date
                recall_next_review = study_date + timedelta(
                    days=next_interval(recall_score, question.score, question.level, 0)
                )
            else:
                explanation_score = updated_mastery(
                    explanation_score,
                    explanation_attempts,
                    question.score,
                    question.level,
                )
                explanation_attempts += 1
                explanation_last_studied = study_date
                explanation_next_review = study_date + timedelta(
                    days=next_interval(explanation_score, question.score, question.level, stable_high)
                )
            review_dates = [
                value for value in (recall_next_review, explanation_next_review) if value is not None
            ]
            catalog_item = catalog_by_term.get(term)
            track = catalog_item.track if catalog_item else question.track
            related = catalog_item.related if catalog_item else " / ".join(question.related_terms)
            note_parts = [part for part in (question.good_point, question.review_focus) if part]
            notes = " / ".join(note_parts) if note_parts else (old.notes if old else "")
            records[term] = TermRecord(
                term=term,
                domain=question.domain,
                score=new_score,
                last_studied=study_date,
                attempts=new_attempts,
                average=new_average,
                last_level=question.level,
                next_review=min(review_dates) if review_dates else None,
                related=related,
                notes=notes,
                track=track,
                last_score=question.score,
                last_session=session_key,
                applied_sessions=(old.applied_sessions if old else ()) + (session_key,),
                recall_score=recall_score,
                recall_attempts=recall_attempts,
                explanation_score=explanation_score,
                explanation_attempts=explanation_attempts,
                recall_last_studied=recall_last_studied,
                recall_next_review=recall_next_review,
                explanation_last_studied=explanation_last_studied,
                explanation_next_review=explanation_next_review,
            )
    atomic_write(progress_file(root, "語句別理解度.md", "terms.md"), render_terms(records))
    return records


def recent_domain_counts(root: Path, limit_sessions: int = 5) -> dict[str, int]:
    counts: dict[str, int] = {}
    sections: list[tuple[date, int, str]] = []
    for path in session_file_paths(root):
        session_day = as_date(path.stem)
        if session_day is None:
            continue
        text = path.read_text(encoding="utf-8")
        for match in re.finditer(r"^## Session (\d+)[ \t]*$", text, flags=re.MULTILINE):
            try:
                session_mode_for_path(root, path, text, int(match.group(1)))
            except ValueError:
                continue
            start, end = session_bounds(text, int(match.group(1)))
            sections.append((session_day, int(match.group(1)), text[start:end]))
    for _, _, section in sorted(sections, reverse=True)[:limit_sessions]:
        for domain in re.findall(r"^- Domain:[ \t]*(.+?)[ \t]*$", section, flags=re.MULTILINE):
            counts[domain] = counts.get(domain, 0) + 1
    return counts


def recent_term_counts(root: Path, today: date, limit_sessions: int = 5) -> dict[str, int]:
    """Weight same-day appearances more heavily, including ungraded sessions."""
    counts: dict[str, int] = {}
    sections: list[tuple[date, int, str]] = []
    for path in session_file_paths(root):
        session_day = as_date(path.stem)
        if session_day is None:
            continue
        text = path.read_text(encoding="utf-8")
        for match in re.finditer(r"^## Session (\d+)[ \t]*$", text, flags=re.MULTILINE):
            try:
                session_mode_for_path(root, path, text, int(match.group(1)))
            except ValueError:
                continue
            start, end = session_bounds(text, int(match.group(1)))
            sections.append((session_day, int(match.group(1)), text[start:end]))
    for session_day, _, section in sorted(sections, reverse=True)[:limit_sessions]:
        weight = 4 if session_day == today else 1
        for question in re.split(r"(?=^### Q\d+[ \t]*$)", section, flags=re.MULTILINE)[1:]:
            terms = parse_list_field(question, "Primary Terms")
            if not terms:
                terms = parse_list_field(question, "Terms")
            for term in terms:
                counts[term] = counts.get(term, 0) + weight
    return counts


def all_scored_questions(root: Path) -> list[tuple[date, int, GradedQuestion]]:
    results: list[tuple[date, int, GradedQuestion]] = []
    for path in session_file_paths(root):
        study_date = as_date(path.stem)
        if study_date is None:
            continue
        text = path.read_text(encoding="utf-8")
        numbers = [
            int(match.group(1))
            for match in re.finditer(r"^## Session (\d+)[ \t]*$", text, flags=re.MULTILINE)
        ]
        for number in numbers:
            try:
                session_mode_for_path(root, path, text, number)
                status, questions = parse_graded_session(
                    text,
                    number,
                    allow_missing_mode=is_legacy_session_path(root, path),
                )
            except ValueError:
                continue
            if status not in {"grading", "graded"}:
                continue
            results.extend((study_date, number, question) for question in questions)
    return sorted(results, key=lambda item: (item[0], item[1], item[2].number))


def domain_level(score: int) -> str:
    if score < 40:
        return "Beginner"
    if score < 70:
        return "Intermediate"
    if score < 85:
        return "Proficient"
    return "Advanced"


def render_domains(
    existing_rows: list[dict[str, str]],
    records: dict[str, TermRecord],
    scored: list[tuple[date, int, GradedQuestion]],
    today: date,
) -> str:
    domain_order = [row["Domain"] for row in existing_rows]
    for record in records.values():
        if record.domain not in domain_order:
            domain_order.append(record.domain)
    lines = [
        "# 分野ごとの理解度",
        "",
        "語句の現在スコアと直近セッションの成績から推定します。履歴がない分野は `Unassessed` とし、0点とは扱いません。",
        "",
        "| Domain | Score | Level | Last Studied | Attempts | Due Terms | Notes |",
        "|---|---:|---|---|---:|---:|---|",
    ]
    existing_by_domain = {row["Domain"]: row for row in existing_rows}
    for domain in domain_order:
        term_records = [record for record in records.values() if record.domain == domain]
        domain_questions = [(day, question) for day, _, question in scored if question.domain == domain]
        if not term_records and not domain_questions:
            row = existing_by_domain.get(domain, {})
            values = [domain, "—", "Unassessed", "—", 0, 0, row.get("Notes", "未評価")]
        else:
            term_mean = sum(record.score for record in term_records) / len(term_records) if term_records else None
            recent = [
                min(question.score, level_cap(question.level))
                for _, question in domain_questions[-5:]
            ]
            recent_mean = sum(recent) / len(recent) if recent else None
            if term_mean is not None and recent_mean is not None:
                score = round(term_mean * 0.70 + recent_mean * 0.30)
            else:
                score = round(term_mean if term_mean is not None else recent_mean or 0)
            dates = [record.last_studied for record in term_records if record.last_studied]
            dates.extend(day for day, _ in domain_questions)
            last_studied = max(dates).isoformat() if dates else "—"
            due = sum(bool(record.next_review and record.next_review <= today) for record in term_records)
            prefix = f"Provisional（{len(domain_questions)}問）: " if len(domain_questions) < 2 else ""
            weakest = min(term_records, key=lambda record: record.score).term if term_records else "—"
            strongest = max(term_records, key=lambda record: record.score).term if term_records else "—"
            notes = f"{prefix}強み候補 {strongest} / 次の確認 {weakest}"
            values = [domain, score, domain_level(score), last_studied, len(domain_questions), due, notes]
        lines.append("| " + " | ".join(markdown_cell(value) for value in values) + " |")
    return "\n".join(lines) + "\n"


def update_domains(
    root: Path,
    records: dict[str, TermRecord],
    study_date: date,
) -> dict[str, int]:
    existing = read_table(progress_file(root, "分野別理解度.md", "domains.md"), "Domain")
    scored = all_scored_questions(root)
    atomic_write(
        progress_file(root, "分野別理解度.md", "domains.md"),
        render_domains(existing, records, scored, study_date),
    )
    result: dict[str, int] = {}
    for row in read_table(progress_file(root, "分野別理解度.md", "domains.md"), "Domain"):
        score = as_int(row.get("Score", ""), -1)
        if score >= 0:
            result[row["Domain"]] = score
    return result


def render_history(rows: list[dict[str, str]]) -> str:
    headers = [
        "Date",
        "Session",
        "Questions",
        "Average",
        "Subject B",
        "Weak Domains",
        "Strong Domains",
        "Next Focus",
        "Session File",
    ]
    lines = [
        "# 学習履歴",
        "",
        "セッションごとの結果を時系列で記録します。`Subject B` は科目B中心問題の比率です。",
        "",
        "| " + " | ".join(headers) + " |",
        "|---|---|---:|---:|---:|---|---|---|---|",
    ]
    for row in rows:
        lines.append("| " + " | ".join(markdown_cell(row.get(header, "")) for header in headers) + " |")
    return "\n".join(lines) + "\n"


def update_history(
    root: Path,
    study_date: date,
    session_number: int,
    questions: list[GradedQuestion],
    records: dict[str, TermRecord],
    session_path: Path,
) -> dict[str, object]:
    rows = read_table(progress_file(root, "学習履歴.md", "history.md"), "Date")
    average = round(sum(question.score for question in questions) / len(questions))
    b_ratio = round(100 * sum(question.track == "B" for question in questions) / len(questions))
    by_domain: dict[str, list[int]] = {}
    for question in questions:
        by_domain.setdefault(question.domain, []).append(question.score)
    domain_averages = {domain: round(sum(scores) / len(scores)) for domain, scores in by_domain.items()}
    weak = [domain for domain, score in domain_averages.items() if score < 60]
    strong = [domain for domain, score in domain_averages.items() if score >= 85]
    weakest_questions = sorted(questions, key=lambda question: question.score)[:2]
    focus = "、".join(question.primary_terms[0] for question in weakest_questions)
    review_dates = [
        records[term].next_review
        for question in questions
        for term in question.primary_terms
        if term in records and records[term].next_review
    ]
    next_review = min(review_dates).isoformat() if review_dates else "—"
    relative_path = session_path.relative_to(root).as_posix()
    history_target = os.path.relpath(session_path, progress_directory(root))
    row = {
        "Date": study_date.isoformat(),
        "Session": str(session_number),
        "Questions": str(len(questions)),
        "Average": str(average),
        "Subject B": f"{b_ratio}%",
        "Weak Domains": "、".join(weak) or "—",
        "Strong Domains": "、".join(strong) or "—",
        "Next Focus": f"{focus}を{next_review}に復習",
        "Session File": f"[{relative_path}]({history_target}#session-{session_number})",
    }
    replaced = False
    for index, existing in enumerate(rows):
        if existing.get("Date") == row["Date"] and existing.get("Session") == row["Session"]:
            rows[index] = row
            replaced = True
            break
    if not replaced:
        rows.append(row)
    atomic_write(progress_file(root, "学習履歴.md", "history.md"), render_history(rows))
    return {
        "average": average,
        "weak": weak,
        "strong": strong,
        "next_review": next_review,
    }


def finalize_session(
    path: Path,
    session_number: int,
    summary: dict[str, object],
) -> None:
    text = path.read_text(encoding="utf-8")
    start, end = session_bounds(text, session_number)
    session = text[start:end]
    session = re.sub(
        r"^- Status:[ \t]*\S+[ \t]*$",
        "- Status: graded",
        session,
        count=1,
        flags=re.MULTILINE,
    )
    strong = "、".join(summary["strong"]) if summary["strong"] else "—"
    weak = "、".join(summary["weak"]) if summary["weak"] else "—"
    summary_text = (
        f"## Session {session_number} Summary\n\n"
        f"- Average: {summary['average']} / 100\n"
        f"- Strong points: {strong}\n"
        f"- Weak points: {weak}\n"
        f"- Recommended next review: {summary['next_review']}\n"
        "- Progress updated: 語句別理解度.md / 分野別理解度.md / 学習履歴.md\n"
    )
    summary_pattern = re.compile(
        rf"^## Session {session_number} Summary[ \t]*$.*\Z",
        flags=re.MULTILINE | re.DOTALL,
    )
    if summary_pattern.search(session):
        session = summary_pattern.sub(summary_text, session)
    else:
        session = session.rstrip() + "\n\n" + summary_text.rstrip() + "\n"
    atomic_write(path, text[:start] + session + text[end:])


def record_progress(
    root: Path,
    study_date: date,
    session_number: int,
    mode: Optional[str] = None,
) -> dict[str, object]:
    session_path = resolve_session_path(root, study_date, session_number, mode)
    text = session_path.read_text(encoding="utf-8")
    status, questions = parse_graded_session(
        text,
        session_number,
        allow_missing_mode=is_legacy_session_path(root, session_path),
    )
    if status == "cancelled":
        raise ValueError("Cannot record a cancelled session")
    if status not in {"grading", "graded"}:
        raise ValueError("Set Session Status to grading after writing all scores, then run record")
    catalog = load_catalog(root)
    records = update_term_records(root, study_date, session_number, questions, catalog)
    update_domains(root, records, study_date)
    summary = update_history(root, study_date, session_number, questions, records, session_path)
    finalize_session(session_path, session_number, summary)
    return {**summary, "questions": len(questions), "session_path": session_path}


def rebuild_progress(root: Path) -> dict[str, int]:
    """Rebuild progress from every fully scored Session in chronological order."""
    sessions: list[tuple[date, int, Path, str, list[GradedQuestion]]] = []
    for path in session_file_paths(root):
        study_date = as_date(path.stem)
        if study_date is None:
            continue
        text = path.read_text(encoding="utf-8")
        for match in re.finditer(r"^## Session ([1-9][0-9]*)[ \t]*$", text, flags=re.MULTILINE):
            session_number = int(match.group(1))
            start, end = session_bounds(text, session_number)
            section = text[start:end]
            status_match = re.search(
                r"^- Status:[ \t]*(\S+)[ \t]*$", section, flags=re.MULTILINE
            )
            status = status_match.group(1) if status_match else ""
            if status not in {"grading", "graded"}:
                continue
            mode = session_mode_for_path(root, path, text, session_number)
            _, questions = parse_graded_session(
                text,
                session_number,
                allow_missing_mode=is_legacy_session_path(root, path),
            )
            sessions.append((study_date, session_number, path, mode, questions))

    sessions.sort(key=lambda item: (item[0], item[1], item[2].as_posix()))
    keys = [(study_date, session_number) for study_date, session_number, _, _, _ in sessions]
    if len(keys) != len(set(keys)):
        raise ValueError("Cannot rebuild progress: duplicate Date/Session combinations exist")

    # Validate all inputs before replacing any progress file.
    catalog = load_catalog(root)
    if not catalog:
        raise ValueError("Cannot rebuild progress without a concept catalog")
    domain_rows = read_table(progress_file(root, "分野別理解度.md", "domains.md"), "Domain")

    atomic_write(progress_file(root, "語句別理解度.md", "terms.md"), render_terms({}))
    atomic_write(
        progress_file(root, "分野別理解度.md", "domains.md"),
        render_domains(domain_rows, {}, [], date.today()),
    )
    atomic_write(progress_file(root, "学習履歴.md", "history.md"), render_history([]))

    for study_date, session_number, path, _, questions in sessions:
        records = update_term_records(root, study_date, session_number, questions, catalog)
        update_domains(root, records, study_date)
        summary = update_history(root, study_date, session_number, questions, records, path)
        finalize_session(path, session_number, summary)
    return {"sessions": len(sessions), "questions": sum(len(item[4]) for item in sessions)}


def tie_break(term: str, today: date) -> float:
    digest = hashlib.sha256(f"{today.isoformat()}|{term}".encode()).hexdigest()
    return int(digest[:6], 16) / 0xFFFFFF


def build_candidates(
    catalog: Iterable[CatalogItem],
    terms: dict[str, TermRecord],
    today: date,
    recent_counts: dict[str, int],
    focus: str = "",
    mode: str = "standard",
    recent_terms: Optional[dict[str, int]] = None,
) -> list[Candidate]:
    focus_tokens = [token.strip().lower() for token in re.split(r"[,/、]", focus) if token.strip()]
    weak_names = {
        name
        for name, record in terms.items()
        if record.score < 60
        or (record.recall_score is not None and record.recall_score < 60)
        or (record.explanation_score is not None and record.explanation_score < 60)
    }
    candidates: list[Candidate] = []
    recent_terms = recent_terms or {}

    for item in catalog:
        record = terms.get(item.term)
        subject_b = 15 if item.track == "B" else 10 if item.track == "A/B" else 3
        balance = max(0, 10 - 2 * recent_counts.get(item.domain, 0))
        focus_bonus = 0
        haystack = f"{item.term} {item.domain} {item.related}".lower()
        if focus_tokens and any(token in haystack for token in focus_tokens):
            focus_bonus = 30

        relation = 0
        relation_text = f"{item.related} {item.prerequisites}"
        if any(name in relation_text for name in weak_names):
            relation = 10

        if record is None:
            weakness = 0.0
            forgetting = 0.0
            unseen_bonus = 20
            mode_unseen = True
            recent_penalty = 0
            due = False
            challenge = False
            level = 1 if mode == TERM_RECALL_MODE else target_level(None, item.entry_level)
            reason = "未学習。頻出度と前提関係を見て導入"
        else:
            if mode == TERM_RECALL_MODE:
                mode_score = record.recall_score
                mode_attempts = record.recall_attempts
                mode_label = "暗記理解度"
                mode_last_studied = record.recall_last_studied
                mode_next_review = record.recall_next_review
            else:
                legacy_explanation = (
                    record.explanation_score is None
                    and record.explanation_attempts <= 0
                    and record.recall_attempts <= 0
                    and record.attempts > 0
                )
                mode_score = record.score if legacy_explanation else record.explanation_score
                mode_attempts = record.attempts if legacy_explanation else record.explanation_attempts
                mode_label = "通常説明理解度"
                mode_last_studied = record.last_studied if legacy_explanation else record.explanation_last_studied
                mode_next_review = record.next_review if legacy_explanation else record.explanation_next_review
            mode_unseen = mode_attempts <= 0 or mode_score is None
            weakness = 0.0 if mode_unseen else 0.45 * (100 - mode_score)
            elapsed = (today - mode_last_studied).days if mode_last_studied else base_interval(mode_score or record.score)
            elapsed = max(0, elapsed)
            forgetting = min(40.0, 35.0 * elapsed / base_interval(mode_score or record.score))
            unseen_bonus = 20 if mode_unseen else 0
            due = bool(mode_next_review and mode_next_review <= today) or forgetting >= 30
            challenge = not mode_unseen and mode_score >= 80
            recent_penalty = 30 if elapsed == 0 and record.last_score is not None and record.last_score >= 60 else 0
            level = (
                1
                if mode == TERM_RECALL_MODE
                else target_level(None if mode_unseen else mode_score, item.entry_level)
            )
            if mode_unseen:
                if mode == TERM_RECALL_MODE:
                    reference = (
                        record.explanation_score
                        if record.explanation_score is not None
                        else record.score
                    )
                    reason = f"暗記語句では未評価。通常説明の理解度{reference}も参照"
                else:
                    reference = (
                        record.recall_score if record.recall_score is not None else record.score
                    )
                    reason = f"通常説明では未評価。暗記理解度{reference}も参照"
            elif mode_score < 60:
                reason = f"{mode_label}{mode_score}の弱点を再構成"
            elif due:
                reason = f"最終学習から{elapsed}日。復習期限が近い/超過"
            elif challenge:
                reason = (
                    f"暗記理解度{mode_score}。定着を再確認"
                    if mode == TERM_RECALL_MODE
                    else f"通常説明理解度{mode_score}。シナリオへ難化"
                )
            else:
                reason = f"{mode_label}{mode_score}。関連知識を補強"

        term_recency_penalty = min(24, 4 * recent_terms.get(item.term, 0))
        priority = (
            weakness
            + forgetting
            + subject_b
            + unseen_bonus
            + relation
            + balance
            + focus_bonus
            - recent_penalty
            - term_recency_penalty
        )
        if term_recency_penalty:
            reason += "。直近の出題を考慮"
        if mode == "weak":
            priority += weakness * 0.5
        elif mode == "new" and record is None:
            priority += 30
        elif mode == "subject-b" and item.track == "B":
            priority += 25

        if mode == TERM_RECALL_MODE and record is not None:
            if record.explanation_score is not None:
                priority += 0.20 * (100 - record.explanation_score)
        elif record is not None and record.recall_score is not None and record.recall_score < 60:
            priority += 0.25 * (100 - record.recall_score)
            reason += f"。暗記理解度{record.recall_score}を通常説明で補強"

        # Importance is the catalog's base exam priority.  Make it strong
        # enough to order otherwise comparable new terms, while allowing a
        # genuine weak point or overdue review to take precedence.
        priority += item.importance * 4 + tie_break(item.term, today)
        # Keep priority comparisons deterministic across harmless floating-point
        # representation differences caused by the component additions above.
        priority = round(priority, 8)
        candidates.append(
            Candidate(
                item=item,
                priority=priority,
                weakness=weakness,
                forgetting=forgetting,
                unseen=mode_unseen,
                due=due,
                challenge=challenge,
                suggested_level=level,
                reason=reason,
            )
        )
    return candidates


def exclude_unanswered_candidates(
    candidates: Iterable[Candidate],
    unanswered_terms: set[str],
    include_unanswered: bool = False,
) -> list[Candidate]:
    """Avoid creating duplicate pending questions unless review was requested."""
    if include_unanswered:
        return list(candidates)
    return [candidate for candidate in candidates if candidate.item.term not in unanswered_terms]


def _take_balanced(pool: Iterable[Candidate], count: int, selected: list[tuple[str, Candidate]]) -> None:
    if count <= 0:
        return
    used_terms = {candidate.item.term for _, candidate in selected}
    domain_counts: dict[str, int] = {}
    for _, candidate in selected:
        domain_counts[candidate.item.domain] = domain_counts.get(candidate.item.domain, 0) + 1
    available = [candidate for candidate in pool if candidate.item.term not in used_terms]
    while available and count > 0:
        best = max(
            available,
            key=lambda candidate: candidate.priority - 12 * domain_counts.get(candidate.item.domain, 0),
        )
        selected.append(("", best))
        domain_counts[best.item.domain] = domain_counts.get(best.item.domain, 0) + 1
        available.remove(best)
        count -= 1


def diagnostic_plan(
    catalog: list[CatalogItem], count: int, focus: str = "", excluded_terms: Optional[set[str]] = None
) -> list[tuple[str, Candidate]]:
    excluded_terms = excluded_terms or set()
    available = [item for item in catalog if item.term not in excluded_terms]
    by_domain = {item.domain: item for item in available if item.diagnostic}
    ordered = [by_domain[domain] for domain in DIAGNOSTIC_DOMAIN_ORDER if domain in by_domain]
    ordered.extend(item for item in available if item.diagnostic and item not in ordered)
    if len(ordered) < count:
        ordered.extend(item for item in available if item not in ordered)
    focus_tokens = [token.strip().lower() for token in re.split(r"[,/、]", focus) if token.strip()]
    if focus_tokens:
        focused = [
            item
            for item in available
            if any(token in f"{item.term} {item.domain} {item.related}".lower() for token in focus_tokens)
        ]
        focus_count = max(1, round(count * 0.40))
        ordered = focused[:focus_count] + [item for item in ordered if item not in focused]
        ordered.extend(item for item in available if item not in ordered)
    result = []
    for item in ordered[:count]:
        candidate = Candidate(
            item=item,
            priority=float(item.importance),
            weakness=0,
            forgetting=0,
            unseen=True,
            due=False,
            challenge=False,
            suggested_level=max(2, min(3, item.entry_level)),
            reason="初回診断。分野横断で基礎〜中級を確認",
        )
        result.append(("診断", candidate))
    return result


def term_recall_track_counts(count: int) -> tuple[int, int]:
    """Allocate whole questions to A first, leaving every fractional remainder to B."""
    a_count = math.floor(count * 0.40)
    return a_count, count - a_count


def planned_track(candidate: Candidate, mode: str) -> str:
    if mode == TERM_RECALL_MODE:
        return "B" if candidate.item.track == "B" else "A"
    return candidate.item.track


def adaptive_plan(
    candidates: list[Candidate],
    count: int,
    mode: str = "standard",
) -> list[tuple[str, Candidate]]:
    if mode == "weak":
        weak_count, due_count, new_count = round(count * 0.60), round(count * 0.20), round(count * 0.10)
    elif mode == "new":
        weak_count, due_count, new_count = round(count * 0.25), round(count * 0.15), round(count * 0.50)
    elif mode == STANDARD_SESSION_MODE and count >= DEFAULT_NORMAL_QUESTION_COUNT:
        # The six-question default adds one new concept to the former five-question
        # mix. Every explicitly requested question beyond six expands coverage too.
        weak_count, due_count, new_count = 2, 1, count - 4
    else:
        weak_count, due_count, new_count = round(count * 0.40), round(count * 0.25), round(count * 0.20)
    challenge_count = max(0, count - weak_count - due_count - new_count)
    selected: list[tuple[str, Candidate]] = []

    challenge_label = "定着確認" if mode == TERM_RECALL_MODE else "発展"
    buckets = [
        ("弱点", (c for c in candidates if not c.unseen and c.weakness >= 13.5), weak_count),
        ("復習期", (c for c in candidates if not c.unseen and c.due), due_count),
        ("新規", (c for c in candidates if c.unseen), new_count),
        (challenge_label, (c for c in candidates if c.challenge), challenge_count),
    ]
    for label, pool, quota in buckets:
        before = len(selected)
        _take_balanced(pool, quota, selected)
        for index in range(before, len(selected)):
            selected[index] = (label, selected[index][1])

    if len(selected) < count:
        before = len(selected)
        _take_balanced(candidates, count - len(selected), selected)
        for index in range(before, len(selected)):
            selected[index] = ("優先度補完", selected[index][1])
    selected = selected[:count]
    if mode == TERM_RECALL_MODE:
        _, target_b = term_recall_track_counts(count)
        minimum_b = maximum_b = target_b
    elif count >= 4 and mode != "subject-b":
        minimum_b = math.ceil(count * 0.70)
        maximum_b = math.floor(count * 0.85)
    else:
        return selected

    if mode != "subject-b":
        used = {candidate.item.term for _, candidate in selected}

        def same_bucket(label: str, candidate: Candidate) -> bool:
            return {
                "弱点": not candidate.unseen and candidate.weakness >= 13.5,
                "復習期": not candidate.unseen and candidate.due,
                "新規": candidate.unseen,
                "発展": candidate.challenge,
                "定着確認": candidate.challenge,
            }.get(label, True)

        while sum(planned_track(candidate, mode) == "B" for _, candidate in selected) > maximum_b:
            replaceable = [
                (index, candidate)
                for index, (_, candidate) in enumerate(selected)
                if planned_track(candidate, mode) == "B"
            ]
            if not replaceable:
                break
            index, removed = min(replaceable, key=lambda pair: pair[1].priority)
            label = selected[index][0]
            replacements = [
                candidate
                for candidate in candidates
                if planned_track(candidate, mode) != "B"
                and candidate.item.term not in used
                and same_bucket(label, candidate)
            ]
            if not replacements:
                replacements = [
                    candidate
                    for candidate in candidates
                    if planned_track(candidate, mode) != "B" and candidate.item.term not in used
                ]
            if not replacements:
                break
            replacement = max(replacements, key=lambda c: c.priority)
            used.remove(removed.item.term)
            used.add(replacement.item.term)
            selected[index] = (label, replacement)

        while sum(planned_track(candidate, mode) == "B" for _, candidate in selected) < minimum_b:
            replaceable = [
                (index, candidate)
                for index, (_, candidate) in enumerate(selected)
                if planned_track(candidate, mode) != "B"
            ]
            if not replaceable:
                break
            index, removed = min(replaceable, key=lambda pair: pair[1].priority)
            label = selected[index][0]
            replacements = [
                candidate
                for candidate in candidates
                if planned_track(candidate, mode) == "B"
                and candidate.item.term not in used
                and same_bucket(label, candidate)
            ]
            if not replacements:
                replacements = [
                    candidate
                    for candidate in candidates
                    if planned_track(candidate, mode) == "B" and candidate.item.term not in used
                ]
            if not replacements:
                break
            replacement = max(replacements, key=lambda c: c.priority)
            used.remove(removed.item.term)
            used.add(replacement.item.term)
            selected[index] = (label, replacement)
    return selected


def term_recall_plan(candidates: list[Candidate], count: int) -> list[tuple[str, Candidate]]:
    return [
        (bucket, replace(candidate, suggested_level=1))
        for bucket, candidate in adaptive_plan(candidates, count, TERM_RECALL_MODE)
    ]


def suggested_form(level: int) -> str:
    return {
        1: "定義",
        2: "原理",
        3: "対策・比較",
        4: "短いシナリオ",
        5: "科目B相当のログ・設定・判断",
        6: "科目B発展・制約と残存リスク",
    }[level]


def term_recall_question(term: str) -> str:
    return f"{term}とは何ですか？"


def infer_generation_request(request: str) -> tuple[str, Optional[int]]:
    """Keep natural-language trigger behavior testable without exposing it as CLI input."""
    term_recall = bool(
        re.search(r"暗記(?:単語|語句)?問題|(?:暗記)?(?:単語|語句)問題", request)
    )
    count_match = re.search(r"(\d+)\s*問", request)
    return (
        TERM_RECALL_MODE if term_recall else "standard",
        int(count_match.group(1)) if count_match else (10 if term_recall else None),
    )


def render_plan(
    plan: list[tuple[str, Candidate]],
    phase: str,
    today: date,
    mode: str = "standard",
) -> str:
    b_count = sum(1 for _, candidate in plan if planned_track(candidate, mode) == "B")
    b_ratio = round(100 * b_count / len(plan)) if plan else 0
    lines = [
        "# Adaptive selection plan",
        "",
        f"- Date: {today.isoformat()}",
        f"- Phase: {phase}",
        f"- Questions: {len(plan)}",
    ]
    if mode == TERM_RECALL_MODE:
        lines.extend(
            [
                f"- Track allocation: A {len(plan) - b_count} / B {b_count}",
                "",
                "| Slot | Bucket | Term | Domain | Track | Level | Form | Priority | Reason | Question |",
                "|---:|---|---|---|---|---:|---|---:|---|---|",
            ]
        )
    else:
        lines.extend(
            [
                f"- Strict Track-B ratio: {b_ratio}% (A/B concepts are counted separately)",
                "",
                "| Slot | Bucket | Term | Domain | Track | Level | Form | Priority | Reason |",
                "|---:|---|---|---|---|---:|---|---:|---|",
            ]
        )
    for slot, (bucket, candidate) in enumerate(plan, 1):
        item = candidate.item
        track = planned_track(candidate, mode)
        form = "語句説明" if mode == TERM_RECALL_MODE else suggested_form(candidate.suggested_level)
        row = (
            f"| {slot} | {bucket} | {item.term} | {item.domain} | {track} | "
            f"{candidate.suggested_level} | {form} | {candidate.priority:.1f} | {candidate.reason} |"
        )
        if mode == TERM_RECALL_MODE:
            row += f" {markdown_cell(term_recall_question(item.term))} |"
        lines.append(row)
    return "\n".join(lines)


def default_root() -> Path:
    return Path(__file__).resolve().parents[3]


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Plan and record adaptive security-specialist study in Markdown."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    plan_parser = subparsers.add_parser("plan", help="Print a Markdown selection plan without changing files.")
    plan_parser.add_argument("--root", type=Path, default=default_root())
    plan_parser.add_argument("--date", type=as_date, default=date.today())
    plan_parser.add_argument("--count", type=int)
    plan_parser.add_argument("--focus", default="")
    plan_parser.add_argument(
        "--include-unanswered",
        action="store_true",
        help="Allow terms already assigned to unanswered questions; use only for an explicit review request.",
    )
    plan_parser.add_argument(
        "--mode",
        choices=["standard", "weak", "new", "subject-b", "light", TERM_RECALL_MODE],
    )
    record_parser = subparsers.add_parser(
        "record",
        help="Idempotently update Markdown progress from an already-scored Session.",
    )
    record_parser.add_argument("--root", type=Path, default=default_root())
    record_parser.add_argument("--date", type=as_date, required=True)
    record_parser.add_argument("--session", type=int, required=True)
    record_parser.add_argument(
        "--mode",
        choices=[STANDARD_SESSION_MODE, TERM_RECALL_MODE],
        help="Verify the mode-specific Session directory.",
    )
    rebuild_parser = subparsers.add_parser(
        "rebuild",
        help="Rebuild Markdown progress from all fully scored Sessions in chronological order.",
    )
    rebuild_parser.add_argument("--root", type=Path, default=default_root())
    unanswered_parser = subparsers.add_parser(
        "unanswered",
        help="Write a compact Markdown list of unanswered questions.",
    )
    unanswered_parser.add_argument("--root", type=Path, default=default_root())
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)
    root = args.root.resolve()
    if args.command == "record":
        if args.date is None:
            print("error: --date must use YYYY-MM-DD", file=sys.stderr)
            return 2
        if args.session < 1:
            print("error: --session must be positive", file=sys.stderr)
            return 2
        try:
            result = record_progress(root, args.date, args.session, args.mode)
        except ValueError as error:
            print(f"error: {error}", file=sys.stderr)
            return 2
        print(
            f"Recorded {result['questions']} questions for {args.date.isoformat()} "
            f"Session {args.session}; average={result['average']}; next_review={result['next_review']}"
        )
        return 0

    if args.command == "rebuild":
        try:
            result = rebuild_progress(root)
        except ValueError as error:
            print(f"error: {error}", file=sys.stderr)
            return 2
        print(f"Rebuilt {result['sessions']} sessions and {result['questions']} questions")
        return 0

    if args.command == "unanswered":
        path = write_unanswered_index(root)
        print(f"Wrote {len(unanswered_questions(root))} unanswered questions to {path}")
        return 0

    catalog = load_catalog(root)
    if not catalog:
        print(f"error: no concept catalog found under {root / '参照資料' / '出題分類と概念カタログ.md'}", file=sys.stderr)
        return 2
    terms = load_terms(root)
    catalog = merge_uncatalogued_terms(catalog, terms)
    today = args.date
    if today is None:
        print("error: --date must use YYYY-MM-DD", file=sys.stderr)
        return 2
    mode = args.mode or STANDARD_SESSION_MODE
    requested_count = args.count
    if requested_count is not None and not 1 <= requested_count <= 30:
        print("error: --count must be between 1 and 30", file=sys.stderr)
        return 2

    assessed = any(record.attempts > 0 for record in terms.values())
    pending_terms = set() if args.include_unanswered else unanswered_primary_terms(root)
    if mode == TERM_RECALL_MODE:
        count = requested_count if requested_count is not None else 10
        candidates = build_candidates(
            catalog,
            terms,
            today,
            recent_domain_counts(root),
            args.focus,
            TERM_RECALL_MODE,
            recent_term_counts(root, today),
        )
        plan = term_recall_plan(
            exclude_unanswered_candidates(candidates, pending_terms, args.include_unanswered), count
        )
        phase = TERM_RECALL_MODE
    elif not assessed:
        count = requested_count if requested_count is not None else (3 if mode == "light" else 8)
        plan = diagnostic_plan(catalog, count, args.focus, pending_terms)
        phase = "diagnosis"
    else:
        count = requested_count if requested_count is not None else (
            3 if mode == "light" else DEFAULT_NORMAL_QUESTION_COUNT
        )
        candidates = build_candidates(
            catalog,
            terms,
            today,
            recent_domain_counts(root),
            args.focus,
            mode,
            recent_term_counts(root, today),
        )
        plan = adaptive_plan(
            exclude_unanswered_candidates(candidates, pending_terms, args.include_unanswered), count, mode
        )
        phase = "adaptive"
    print(render_plan(plan, phase, today, mode))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
