"""Generated unanswered, review, activity, and motivation indexes."""
from __future__ import annotations

import os
import re
from datetime import date
from pathlib import Path

from .common import (
    GradedActivity,
    GradingCandidate,
    QUICK_REVIEW_MODE,
    STANDARD_SESSION_MODE,
    TERM_RECALL_MODE,
    TERM_RECALL_SESSION_DIRECTORY,
    UnansweredQuestion,
    UnreviewedItem,
    as_date,
    atomic_write,
    load_catalog,
    load_terms,
    parse_list_field,
    progress_directory,
    quick_review_checked_choices,
    sessions_directory,
)
from .session_parser import session_file_paths, session_mode_for_path



def unanswered_questions(root: Path) -> list[UnansweredQuestion]:
    """Find unanswered question blocks in text-answer and quick-review sessions."""
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
            session_kind = {
                TERM_RECALL_MODE: "暗記語句問題",
                QUICK_REVIEW_MODE: "10分復習",
            }.get(mode, "理解・応用問題")
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
                if mode == QUICK_REVIEW_MODE:
                    checked_choices = quick_review_checked_choices(question)
                    if len(checked_choices) == 1:
                        continue
                    # Older quick-review Sessions accepted a text answer. Keep them
                    # answerable while new Sessions use only their task-list choices.
                    answer_match = re.search(
                        r"^### 回答[ \t]*\n(?P<answer>.*?)(?=^### |\Z)",
                        question,
                        flags=re.MULTILINE | re.DOTALL,
                    )
                    if not checked_choices and answer_match is not None:
                        answer = re.sub(
                            r"<!--.*?-->", "", answer_match.group("answer"), flags=re.DOTALL
                        )
                        if answer.strip():
                            continue
                else:
                    answer_match = re.search(
                        r"^### 回答[ \t]*\n(?P<answer>.*?)(?=^### |\Z)",
                        question,
                        flags=re.MULTILINE | re.DOTALL,
                    )
                    if answer_match is None:
                        continue
                    answer = re.sub(
                        r"<!--.*?-->", "", answer_match.group("answer"), flags=re.DOTALL
                    )
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
                            os.path.relpath(path, sessions_directory(root))
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


def grading_candidates(root: Path) -> list[GradingCandidate]:
    """Find fully answered Sessions without finalized grading markers."""
    candidates: list[GradingCandidate] = []
    for path in session_file_paths(root):
        study_date = as_date(path.stem)
        if study_date is None:
            continue
        text = path.read_text(encoding="utf-8")
        headings = list(re.finditer(r"^## Session ([1-9][0-9]*)[ \t]*$", text, re.MULTILINE))
        for index, heading in enumerate(headings):
            end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
            session = text[heading.start() : end]
            if re.search(r"^- Status:[ \t]*cancelled[ \t]*$", session, re.MULTILINE):
                continue
            number = int(heading.group(1))
            try:
                mode = session_mode_for_path(root, path, text, number)
            except ValueError:
                mode = TERM_RECALL_MODE if path.parent.name == TERM_RECALL_SESSION_DIRECTORY else STANDARD_SESSION_MODE
            questions = list(re.finditer(r"^### Q[1-9][0-9]*[ \t]*$", session, re.MULTILINE))
            if not questions:
                continue
            answered = scored = True
            for q_index, q_heading in enumerate(questions):
                q_end = questions[q_index + 1].start() if q_index + 1 < len(questions) else len(session)
                question = session[q_heading.start() : q_end]
                if mode == QUICK_REVIEW_MODE:
                    answered = answered and len(quick_review_checked_choices(question)) == 1
                else:
                    answer = re.search(r"^### 回答[ \t]*\n(?P<value>.*?)(?=^### |\Z)", question, re.MULTILINE | re.DOTALL)
                    answered = answered and bool(answer and re.sub(r"<!--.*?-->", "", answer.group("value"), flags=re.DOTALL).strip())
                scored = scored and bool(re.search(r"^### 採点[ \t]*\n+Score: (?:100|[1-9]?[0-9]) / 100[ \t]*$", question, re.MULTILINE))
            finalized = "Mastery updated:" in session if mode == QUICK_REVIEW_MODE else "Progress updated:" in session
            if answered and not (scored and finalized):
                kind = {TERM_RECALL_MODE: "暗記語句問題", QUICK_REVIEW_MODE: "10分復習"}.get(mode, "理解・応用問題")
                candidates.append(GradingCandidate(study_date, number, kind, path, len(questions)))
    return sorted(candidates, key=lambda item: (item.study_date, item.session_number, item.path.as_posix()))


def render_unanswered_index(questions: list[UnansweredQuestion]) -> str:
    lines = ["# 未解答一覧", ""]
    if not questions:
        lines.append("未解答はありません。")
        return "\n".join(lines) + "\n"
    for kind in ("理解・応用問題", "暗記語句問題", "10分復習"):
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
    path = sessions_directory(root) / "未解答一覧.md"
    atomic_write(path, render_unanswered_index(unanswered_questions(root)))
    return path


def graded_activities(root: Path, graded_date: date) -> list[GradedActivity]:
    """Return Sessions explicitly recorded as graded on the requested study date."""
    activities: list[GradedActivity] = []
    for path in session_file_paths(root):
        study_date = as_date(path.stem)
        if study_date is None:
            continue
        text = path.read_text(encoding="utf-8")
        headings = list(re.finditer(r"^## Session ([1-9][0-9]*)[ \t]*$", text, re.MULTILINE))
        for index, heading in enumerate(headings):
            end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
            session = text[heading.start() : end]
            if not re.search(r"^- Status:[ \t]*graded[ \t]*$", session, re.MULTILINE):
                continue
            recorded_date = re.search(
                r"^- Graded:[ \t]*(\d{4}-\d{2}-\d{2})[ \t]*$", session, re.MULTILINE
            )
            if not recorded_date or as_date(recorded_date.group(1)) != graded_date:
                continue
            session_number = int(heading.group(1))
            try:
                mode = session_mode_for_path(root, path, text, session_number)
            except ValueError:
                mode = (
                    TERM_RECALL_MODE
                    if path.parent.name == TERM_RECALL_SESSION_DIRECTORY
                    else STANDARD_SESSION_MODE
                )
            session_kind = {
                TERM_RECALL_MODE: "暗記語句問題",
                QUICK_REVIEW_MODE: "10分復習",
            }.get(mode, "理解・応用問題")
            count_match = re.search(
                r"^- Question Count:[ \t]*([1-9][0-9]*)[ \t]*$", session, re.MULTILINE
            )
            if count_match is None:
                continue
            activities.append(
                GradedActivity(
                    study_date=study_date,
                    session_number=session_number,
                    session_kind=session_kind,
                    question_count=int(count_match.group(1)),
                    session_link_path=Path(
                        os.path.relpath(path, sessions_directory(root))
                    ).as_posix(),
                )
            )
    return sorted(
        activities,
        key=lambda item: (item.study_date, item.session_number, item.session_link_path),
    )


def render_activity_section(graded_date: date, activities: list[GradedActivity]) -> str:
    """Render one date section for the source-linked activity log."""
    lines = [f"## {graded_date.isoformat()}", ""]
    if not activities:
        lines.append("採点したファイルはありません。")
        return "\n".join(lines) + "\n"
    for kind in ("理解・応用問題", "暗記語句問題", "10分復習"):
        entries = [activity for activity in activities if activity.session_kind == kind]
        if not entries:
            continue
        lines.extend([f"### {kind}", ""])
        for activity in entries:
            lines.append(
                f"- [{activity.study_date.isoformat()} / Session {activity.session_number} / "
                f"{activity.question_count}問]({activity.session_link_path})"
            )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_activity_log(
    root: Path,
    graded_date: date,
    pending_activity: GradedActivity | None = None,
) -> Path:
    """Write one study-date section, optionally including a Session not finalized yet."""
    path = sessions_directory(root) / "行ったこと.md"
    activities = graded_activities(root, graded_date)
    if pending_activity is not None:
        pending_key = (
            pending_activity.study_date,
            pending_activity.session_number,
            pending_activity.session_link_path,
        )
        activities = [
            activity
            for activity in activities
            if (
                activity.study_date,
                activity.session_number,
                activity.session_link_path,
            )
            != pending_key
        ]
        activities.append(pending_activity)
        activities.sort(
            key=lambda item: (
                item.study_date,
                item.session_number,
                item.session_link_path,
            )
        )
    section = render_activity_section(graded_date, activities)
    if not path.exists():
        atomic_write(path, "# 行ったこと\n\n" + section)
        return path

    text = path.read_text(encoding="utf-8")
    heading = re.compile(rf"^## {re.escape(graded_date.isoformat())}[ \t]*$", re.MULTILINE)
    match = heading.search(text)
    if match is None:
        date_headings = list(re.finditer(r"^## (\d{4}-\d{2}-\d{2})[ \t]*$", text, re.MULTILINE))
        earlier_heading = next(
            (
                item
                for item in date_headings
                if as_date(item.group(1)) is not None and as_date(item.group(1)) < graded_date
            ),
            None,
        )
        if earlier_heading is None:
            atomic_write(path, text.rstrip() + "\n\n" + section)
        else:
            atomic_write(
                path,
                text[: earlier_heading.start()] + section.rstrip() + "\n\n" + text[earlier_heading.start() :],
            )
        return path
    next_heading = re.search(r"^## ", text[match.end() :], re.MULTILINE)
    end = match.end() + next_heading.start() if next_heading else len(text)
    tail = text[end:].lstrip("\n")
    suffix = "\n\n" + tail if tail else "\n"
    atomic_write(path, text[: match.start()] + section.rstrip() + suffix)
    return path


def render_motivation(root: Path) -> str:
    """Render a compact, derived study-coverage dashboard."""
    catalog = load_catalog(root)
    records = load_terms(root)
    total = len(catalog)
    assessed = {term for term, record in records.items() if record.attempts > 0}
    categories = {
        "未評価": 0,
        "暗記のみ": 0,
        "応用のみ": 0,
        "両方確認": 0,
    }
    for item in catalog:
        record = records.get(item.term)
        if record is None or record.attempts == 0:
            categories["未評価"] += 1
        elif record.recall_attempts > 0 and record.explanation_attempts > 0:
            categories["両方確認"] += 1
        elif record.recall_attempts > 0:
            categories["暗記のみ"] += 1
        else:
            categories["応用のみ"] += 1
    completed = total - categories["未評価"]
    lines = [
        "# モチベーション",
        "",
        "カタログ語句を、未評価・暗記のみ・応用のみ・両方確認の重複しない4区分で表示します。採点時に自動更新します。",
        "",
        "```mermaid",
        "pie showData",
        '    title 全体の語彙カバレッジと学習形式の内訳',
        f'    "未評価" : {categories["未評価"]}',
        f'    "暗記のみ" : {categories["暗記のみ"]}',
        f'    "応用のみ" : {categories["応用のみ"]}',
        f'    "両方確認" : {categories["両方確認"]}',
        "```",
        "",
        f"**全体**: {completed} / {total} 語（{round(100 * completed / total) if total else 0}%）",
        f"内訳: 暗記のみ {categories['暗記のみ']}語 / 応用のみ {categories['応用のみ']}語 / 両方確認 {categories['両方確認']}語",
        "",
        "| 分野 | 暗記のみ | 応用のみ | 両方確認 | 未評価 | 全語彙 | カバレッジ |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    domains: list[str] = []
    for item in catalog:
        if item.domain not in domains:
            domains.append(item.domain)
    for domain in domains:
        domain_items = [item for item in catalog if item.domain == domain]
        recall_only = sum(
            bool(records.get(item.term) and records[item.term].recall_attempts > 0 and records[item.term].explanation_attempts == 0)
            for item in domain_items
        )
        explanation_only = sum(
            bool(records.get(item.term) and records[item.term].recall_attempts == 0 and records[item.term].explanation_attempts > 0)
            for item in domain_items
        )
        both = sum(
            bool(records.get(item.term) and records[item.term].recall_attempts > 0 and records[item.term].explanation_attempts > 0)
            for item in domain_items
        )
        count = len(domain_items)
        coverage = round(100 * (recall_only + explanation_only + both) / count) if count else 0
        lines.append(
            f"| {domain} | {recall_only} | {explanation_only} | {both} | {count - recall_only - explanation_only - both} | {count} | {coverage}% |"
        )
    return "\n".join(lines) + "\n"


def write_motivation(root: Path) -> Path:
    path = progress_directory(root) / "モチベ.md"
    atomic_write(path, render_motivation(root))
    return path


def unreviewed_items(root: Path) -> list[UnreviewedItem]:
    """Find unchecked entries in the daily review checklists."""
    review_directory = root / "復習用" / "明日復習するべきところ"
    items: list[UnreviewedItem] = []
    for path in sorted(review_directory.glob("*.md")):
        review_date = as_date(path.stem)
        if review_date is None:
            continue
        text = path.read_text(encoding="utf-8")
        headings = list(
            re.finditer(r"^#### (.+?) — ([0-9]{1,3})点[ \t]*$", text, re.MULTILINE)
        )
        for order, heading in enumerate(headings):
            end = headings[order + 1].start() if order + 1 < len(headings) else len(text)
            entry = text[heading.start() : end]
            # The checkbox state is the source of truth.  Do not silently drop an
            # unfinished review merely because the human-readable label was
            # paraphrased (for example, "復習する" instead of "復習済み").
            if not re.search(r"^- \[ \][ \t]+\S.*$", entry, re.MULTILINE):
                continue
            items.append(
                UnreviewedItem(
                    review_date=review_date,
                    term=heading.group(1),
                    score=int(heading.group(2)),
                    review_link_path=Path(
                        os.path.relpath(path, root / "復習用")
                    ).as_posix(),
                    order=order,
                )
            )
    return sorted(items, key=lambda item: (item.score, item.review_date, item.order))


def render_unreviewed_index(items: list[UnreviewedItem]) -> str:
    lines = ["# 未復習一覧", ""]
    if not items:
        lines.append("未復習はありません。")
    else:
        for item in items:
            lines.append(
                f"- [{item.review_date.isoformat()} / {item.term} — {item.score}点]"
                f"({item.review_link_path})"
            )
    return "\n".join(lines) + "\n"


def write_unreviewed_index(root: Path) -> Path:
    path = root / "復習用" / "未復習一覧.md"
    atomic_write(path, render_unreviewed_index(unreviewed_items(root)))
    return path
