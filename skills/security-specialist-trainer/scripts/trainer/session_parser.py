"""Session discovery, mode resolution, parsing, and authoring validation."""
from __future__ import annotations

import os
import re
from datetime import date
from pathlib import Path
from typing import Optional

from .common import (
    ANSWER_PLACEHOLDER,
    EXPLANATION_MODE,
    GradedQuestion,
    LEGACY_SESSION_DIRECTORIES,
    NORMAL_SESSION_MODES,
    QUICK_REVIEW_MODE,
    QUICK_REVIEW_SESSION_DIRECTORY,
    STANDARD_SESSION_DIRECTORY,
    STANDARD_SESSION_MODE,
    TERM_RECALL_MODE,
    TERM_RECALL_SESSION_DIRECTORY,
    _feedback_text,
    _first_feedback_bullet,
    as_date,
    parse_list_field,
    quick_review_checked_choices,
    sessions_directory,
    term_recall_track_counts,
)



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
        *(sessions_root / QUICK_REVIEW_SESSION_DIRECTORY).glob("*.md"),
    ]
    for directory in LEGACY_SESSION_DIRECTORIES:
        paths.extend((sessions_root / directory).glob("*.md"))
    return sorted(
        {path for path in paths if as_date(path.stem) is not None},
        key=lambda path: (as_date(path.stem) or date.min, path.as_posix()),
    )


def session_path_for_mode(root: Path, study_date: date, mode: str) -> Path:
    directory = {
        TERM_RECALL_MODE: TERM_RECALL_SESSION_DIRECTORY,
        QUICK_REVIEW_MODE: QUICK_REVIEW_SESSION_DIRECTORY,
    }.get(mode, STANDARD_SESSION_DIRECTORY)
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
    if value == QUICK_REVIEW_MODE:
        return QUICK_REVIEW_MODE
    if value in NORMAL_SESSION_MODES:
        return STANDARD_SESSION_MODE
    allowed = ", ".join(sorted((*NORMAL_SESSION_MODES, TERM_RECALL_MODE, QUICK_REVIEW_MODE)))
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
    if path.parent == sessions_root / QUICK_REVIEW_SESSION_DIRECTORY:
        return QUICK_REVIEW_MODE
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


def validate_authored_session(
    root: Path,
    study_date: date,
    session_number: int,
    mode: Optional[str] = None,
) -> dict[str, object]:
    """Validate a newly authored Session before the learner starts answering it."""
    path = resolve_session_path(root, study_date, session_number, mode)
    text = path.read_text(encoding="utf-8")
    actual_mode = session_mode_for_path(root, path, text, session_number)
    start, end = session_bounds(text, session_number)
    session = text[start:end]

    created_values = re.findall(
        r"^- Created:[ \t]*(.*?)[ \t]*$", session, flags=re.MULTILINE
    )
    if len(created_values) != 1 or as_date(created_values[0]) != study_date:
        raise ValueError(
            f"Session {session_number} must have exactly one Created date matching "
            f"{study_date.isoformat()}"
        )

    status_values = re.findall(
        r"^- Status:[ \t]*(\S+)[ \t]*$", session, flags=re.MULTILINE
    )
    if len(status_values) != 1 or status_values[0] != "awaiting_answers":
        raise ValueError(
            f"Session {session_number} must have exactly one awaiting_answers Status"
        )

    question_count_values = re.findall(
        r"^- Question Count:[ \t]*(.*?)[ \t]*$", session, flags=re.MULTILINE
    )
    if len(question_count_values) != 1:
        raise ValueError(
            f"Session {session_number} must have exactly one Question Count"
        )
    if not re.fullmatch(r"\d+", question_count_values[0]):
        raise ValueError(f"Session {session_number} Question Count must be an integer")
    question_count = int(question_count_values[0])
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
        raise ValueError(
            f"Session {session_number} has invalid question headings: "
            + ", ".join(invalid_question_headings)
        )
    question_headings = list(
        re.finditer(r"^### Q([1-9][0-9]*)[ \t]*$", session, flags=re.MULTILINE)
    )
    if len(question_headings) != question_count:
        raise ValueError(
            f"Session {session_number} Question Count is {question_count}, "
            f"but found {len(question_headings)} question headings"
        )
    actual_numbers = [int(heading.group(1)) for heading in question_headings]
    expected_numbers = list(range(1, question_count + 1))
    if actual_numbers != expected_numbers:
        raise ValueError(
            f"Session {session_number} question headings must be consecutive and unique "
            f"from Q1; expected {expected_numbers}, got {actual_numbers}"
        )

    seen_primary: set[str] = set()
    tracks: list[str] = []
    for index, heading in enumerate(question_headings):
        question_end = (
            question_headings[index + 1].start()
            if index + 1 < len(question_headings)
            else len(session)
        )
        block = session[heading.start() : question_end]
        number = int(heading.group(1))

        domain_values = re.findall(
            r"^- Domain:[ \t]*(.+?)[ \t]*$", block, flags=re.MULTILINE
        )
        track_values = re.findall(
            r"^- Track:[ \t]*(A/B|A|B)[ \t]*$", block, flags=re.MULTILINE
        )
        level_values = re.findall(
            r"^- Level:[ \t]*([1-6])[ \t]*$", block, flags=re.MULTILINE
        )
        if len(domain_values) != 1 or len(track_values) != 1 or len(level_values) != 1:
            raise ValueError(
                f"Q{number} must have exactly one Domain, Track, and Level"
            )
        if len(re.findall(r"^- Primary Terms:[ \t]*$", block, re.MULTILINE)) != 1:
            raise ValueError(f"Q{number} must have exactly one Primary Terms field")
        if len(re.findall(r"^- Related Terms:[ \t]*$", block, re.MULTILINE)) != 1:
            raise ValueError(f"Q{number} must have exactly one Related Terms field")
        primary = parse_list_field(block, "Primary Terms")
        if not primary:
            raise ValueError(f"Q{number} must have at least one Primary Term")
        duplicates = seen_primary.intersection(primary)
        if duplicates:
            raise ValueError(
                "Primary Terms repeated in one session: "
                + ", ".join(sorted(duplicates))
            )
        seen_primary.update(primary)
        tracks.append(track_values[0])

        problem_headings = list(
            re.finditer(r"^### 問題[ \t]*$", block, flags=re.MULTILINE)
        )
        if len(problem_headings) != 1:
            raise ValueError(f"Q{number} must have exactly one 問題 heading")
        problem_start = problem_headings[0].end()
        next_heading = re.search(r"^### ", block[problem_start:], flags=re.MULTILINE)
        problem_end = (
            problem_start + next_heading.start() if next_heading else len(block)
        )
        problem_text = block[problem_start:problem_end].strip()
        if not problem_text:
            raise ValueError(f"Q{number} 問題 must not be empty")

        answer_matches = list(
            re.finditer(r"^### 回答[ \t]*$", block, flags=re.MULTILINE)
        )
        if actual_mode == QUICK_REVIEW_MODE:
            if answer_matches:
                raise ValueError(f"Q{number} quick-review must not have a 回答 heading")
            checkbox_lines = re.findall(
                r"^- \[[^\]]*\] [A-Z]\.[ \t]+\S.*$",
                problem_text,
                flags=re.MULTILINE,
            )
            choices = re.findall(
                r"^- \[ \] ([ABCD])\.[ \t]+\S.*$",
                problem_text,
                flags=re.MULTILINE,
            )
            unknown_choice = re.search(
                r"^- \[ \] D\.[ \t]+わかりません[ \t]*$",
                problem_text,
                flags=re.MULTILINE,
            )
            if (
                len(checkbox_lines) != 4
                or choices != ["A", "B", "C", "D"]
                or unknown_choice is None
            ):
                raise ValueError(
                    f"Q{number} quick-review must have exactly four unchecked "
                    "A/B/C/D checkbox choices ending with D. わかりません"
                )
        else:
            if len(answer_matches) != 1:
                raise ValueError(f"Q{number} must have exactly one 回答 heading")
            answer_start = answer_matches[0].end()
            next_heading = re.search(
                r"^### ", block[answer_start:], flags=re.MULTILINE
            )
            answer_end = (
                answer_start + next_heading.start()
                if next_heading
                else len(block)
            )
            answer_text = block[answer_start:answer_end].strip()
            if answer_text != ANSWER_PLACEHOLDER:
                raise ValueError(
                    f"Q{number} 回答 must contain only the standard answer placeholder"
                )

        if re.search(r"^### 採点[ \t]*$", block, flags=re.MULTILINE):
            raise ValueError(f"Q{number} must not have grading before the learner answers")

        if actual_mode == TERM_RECALL_MODE:
            if len(primary) != 1:
                raise ValueError(
                    "term-recall questions must have exactly one Primary Term each"
                )
            if int(level_values[0]) != 1:
                raise ValueError("term-recall questions must use Level 1")
            if track_values[0] not in {"A", "B"}:
                raise ValueError("term-recall questions must use Track A or B")

    if actual_mode == TERM_RECALL_MODE:
        expected_a, expected_b = term_recall_track_counts(question_count)
        actual_a = tracks.count("A")
        actual_b = tracks.count("B")
        if (actual_a, actual_b) != (expected_a, expected_b):
            raise ValueError(
                "term-recall Track allocation must be "
                f"A {expected_a} / B {expected_b}; got A {actual_a} / B {actual_b}"
            )

    return {
        "path": path,
        "mode": actual_mode,
        "questions": question_count,
        "status": status_values[0],
    }


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
    question_mode = (
        TERM_RECALL_MODE if parsed_mode == TERM_RECALL_MODE
        else QUICK_REVIEW_MODE if parsed_mode == QUICK_REVIEW_MODE
        else EXPLANATION_MODE
    )
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
        if question_mode == QUICK_REVIEW_MODE:
            checked_choices = quick_review_checked_choices(block)
            has_checkbox_choices = re.search(
                r"^- \[[ xX]\][ \t]+[ABCD]\.[ \t]+",
                block,
                flags=re.MULTILINE,
            )
            if has_checkbox_choices and len(checked_choices) != 1:
                raise ValueError(
                    f"Q{heading.group(1)} quick-review must have exactly one checked choice"
                )
            if checked_choices == ("D",) and score != 0:
                raise ValueError(
                    f"Q{heading.group(1)} selected D. わかりません but Score is not 0"
                )
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
                explanation=(
                    _feedback_text(block, "解説")
                    if question_mode == QUICK_REVIEW_MODE
                    else ""
                ),
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


def recent_term_sources(
    root: Path,
    limit_sessions: int = 3,
) -> dict[str, list[tuple[date, int, Path]]]:
    """Return recent Session sources for each primary term without judging prose overlap."""
    sections: list[tuple[date, int, Path, str]] = []
    for path in session_file_paths(root):
        session_day = as_date(path.stem)
        if session_day is None:
            continue
        text = path.read_text(encoding="utf-8")
        for match in re.finditer(r"^## Session (\d+)[ \t]*$", text, flags=re.MULTILINE):
            session_number = int(match.group(1))
            try:
                session_mode_for_path(root, path, text, session_number)
            except ValueError:
                continue
            start, end = session_bounds(text, session_number)
            sections.append((session_day, session_number, path, text[start:end]))

    sources: dict[str, list[tuple[date, int, Path]]] = {}
    ordered_sections = sorted(
        sections,
        key=lambda section: (section[0], section[1], str(section[2])),
        reverse=True,
    )
    for session_day, session_number, path, section in ordered_sections[:limit_sessions]:
        for question in re.split(r"(?=^### Q\d+[ \t]*$)", section, flags=re.MULTILINE)[1:]:
            terms = parse_list_field(question, "Primary Terms")
            if not terms:
                terms = parse_list_field(question, "Terms")
            for term in terms:
                sources.setdefault(term, []).append((session_day, session_number, path))
    return sources


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
                mode = session_mode_for_path(root, path, text, number)
                if mode == QUICK_REVIEW_MODE:
                    continue
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


def recent_mode_scores(
    root: Path,
    mode: str,
) -> dict[str, tuple[date, int, int]]:
    """Return the latest scored evidence for the mode used by an authoring plan."""
    question_mode = TERM_RECALL_MODE if mode == TERM_RECALL_MODE else EXPLANATION_MODE
    latest: dict[str, tuple[date, int, int]] = {}
    for study_date, session_number, question in all_scored_questions(root):
        if question.question_mode != question_mode:
            continue
        for term in question.primary_terms:
            latest[term] = (study_date, session_number, question.score)
    return latest


def quick_review_incorrect_terms(root: Path) -> set[str]:
    """Return missed quick-review terms without changing mastery evidence."""
    incorrect: set[str] = set()
    for path in session_file_paths(root):
        if path.parent.name != QUICK_REVIEW_SESSION_DIRECTORY:
            continue
        text = path.read_text(encoding="utf-8")
        for match in re.finditer(r"^## Session ([1-9][0-9]*)[ \t]*$", text, flags=re.MULTILINE):
            try:
                status, questions = parse_graded_session(
                    text, int(match.group(1)), allow_missing_mode=False
                )
            except ValueError:
                continue
            if status in {"grading", "graded"}:
                incorrect.update(
                    term
                    for question in questions
                    if question.score < 100
                    for term in question.primary_terms
                )
    return incorrect


def quick_review_exists(root: Path, study_date: date) -> bool:
    """Return whether a non-cancelled quick-review Session exists for a JST study date."""
    for path in session_file_paths(root):
        if path.parent.name != QUICK_REVIEW_SESSION_DIRECTORY or as_date(path.stem) != study_date:
            continue
        text = path.read_text(encoding="utf-8")
        for match in re.finditer(r"^## Session ([1-9][0-9]*)[ \t]*$", text, flags=re.MULTILINE):
            number = int(match.group(1))
            try:
                if session_mode_for_path(root, path, text, number) != QUICK_REVIEW_MODE:
                    continue
            except ValueError:
                continue
            start, end = session_bounds(text, number)
            if not re.search(r"^- Status:[ \t]*cancelled[ \t]*$", text[start:end], flags=re.MULTILINE):
                return True
    return False
