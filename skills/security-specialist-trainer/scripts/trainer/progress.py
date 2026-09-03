"""Mastery updates, progress rendering, Session finalization, and rebuilds."""
from __future__ import annotations

import os
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

from .common import (
    CatalogItem,
    GradedActivity,
    GradedQuestion,
    QUICK_REVIEW_MODE,
    TERM_RECALL_MODE,
    TermRecord,
    as_date,
    as_int,
    atomic_write,
    current_study_date,
    level_cap,
    load_catalog,
    load_terms,
    markdown_cell,
    next_interval,
    progress_directory,
    progress_file,
    read_table,
    sessions_directory,
    updated_mastery,
    updated_recall_mastery,
)
from .indexes import write_activity_log, write_motivation, write_unanswered_index
from .session_parser import (
    all_scored_questions,
    is_legacy_session_path,
    parse_graded_session,
    resolve_session_path,
    session_bounds,
    session_file_paths,
    session_mode_for_path,
)



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


def domain_level(score: int) -> str:
    if score < 40:
        return "Beginner"
    if score < 70:
        return "Intermediate"
    if score < 85:
        return "Proficient"
    return "Advanced"


def domain_coverage(
    questions: list[GradedQuestion],
) -> tuple[str, str]:
    """Return the highest demonstrated coverage stage and its evidence summary."""
    recall_count = sum(question.question_mode == TERM_RECALL_MODE for question in questions)
    explanation_questions = [
        question for question in questions if question.question_mode != TERM_RECALL_MODE
    ]
    high_difficulty_successes = sum(
        question.level >= 5 and question.score >= 90 for question in explanation_questions
    )
    evidence = (
        f"暗記 {recall_count}問 / 応用 {len(explanation_questions)}問"
        f" / 高難度成功 {high_difficulty_successes}問"
    )
    if not questions:
        return "未評価", "—"
    if len(explanation_questions) == 0:
        return "用語想起のみ", evidence
    if high_difficulty_successes >= 2:
        return "高難度で安定", evidence
    return "応用まで確認", evidence


def render_domains(
    existing_rows: list[dict[str, str]],
    records: dict[str, TermRecord],
    scored: list[tuple[date, int, GradedQuestion]],
    today: date,
    catalog: Optional[list[CatalogItem]] = None,
) -> str:
    domain_order = [row["Domain"] for row in existing_rows]
    for item in catalog or []:
        if item.domain not in domain_order:
            domain_order.append(item.domain)
    for record in records.values():
        if record.domain not in domain_order:
            domain_order.append(record.domain)
    lines = [
        "# 分野ごとの理解度",
        "",
        "語句の現在スコアと直近セッションの成績から推定します。履歴がない分野は `Unassessed` とし、0点とは扱いません。`Coverage` は、暗記だけなら「用語想起のみ」、通常説明を1問以上確認すると「応用まで確認」、通常説明のLevel 5以上・90点以上を2問以上確認すると「高難度で安定」です。`Unassessed Important Terms` は、カタログのImportance 4〜5で一度も採点されていない語句数です。",
        "",
        "| Domain | Score | Level | Coverage | Evidence | Last Studied | Questions | Unassessed Important Terms | Due Terms | Notes |",
        "|---|---:|---|---|---|---|---:|---:|---:|---|",
    ]
    existing_by_domain = {row["Domain"]: row for row in existing_rows}
    for domain in domain_order:
        term_records = [record for record in records.values() if record.domain == domain]
        domain_questions = [(day, question) for day, _, question in scored if question.domain == domain]
        questions = [question for _, question in domain_questions]
        coverage, evidence = domain_coverage(questions)
        unassessed_important = sum(
            item.importance >= 4
            and (item.term not in records or records[item.term].attempts == 0)
            for item in (catalog or [])
            if item.domain == domain
        )
        if not term_records and not domain_questions:
            row = existing_by_domain.get(domain, {})
            values = [
                domain,
                "—",
                "Unassessed",
                coverage,
                evidence,
                "—",
                0,
                unassessed_important,
                0,
                row.get("Notes", "未評価"),
            ]
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
            values = [
                domain,
                score,
                domain_level(score),
                coverage,
                evidence,
                last_studied,
                len(domain_questions),
                unassessed_important,
                due,
                notes,
            ]
        lines.append("| " + " | ".join(markdown_cell(value) for value in values) + " |")
    return "\n".join(lines) + "\n"


def update_domains(
    root: Path,
    records: dict[str, TermRecord],
    study_date: date,
    catalog: Optional[list[CatalogItem]] = None,
) -> dict[str, int]:
    existing = read_table(progress_file(root, "分野別理解度.md", "domains.md"), "Domain")
    scored = all_scored_questions(root)
    atomic_write(
        progress_file(root, "分野別理解度.md", "domains.md"),
        render_domains(existing, records, scored, study_date, catalog or load_catalog(root)),
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
    mode: Optional[str] = None,
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
        (
            records[term].recall_next_review
            if mode == TERM_RECALL_MODE
            else records[term].explanation_next_review
            if mode is not None
            else records[term].next_review
        )
        for question in questions
        for term in question.primary_terms
        if term in records
    ]
    review_dates = [review_date for review_date in review_dates if review_date]
    earliest_review_date = min(review_dates) if review_dates else None
    next_review = earliest_review_date.isoformat() if earliest_review_date else "—"
    next_review_interval_days = (
        max(0, (earliest_review_date - study_date).days)
        if earliest_review_date
        else None
    )
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
        "Next Focus": (
            f"{focus}を次の学習時に優先（目安: {next_review_interval_days}日後）"
            if next_review_interval_days is not None
            else f"{focus}を次の学習時に確認"
        ),
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
    rows.sort(key=lambda item: (item.get("Date", ""), as_int(item.get("Session", ""), 0)))
    atomic_write(progress_file(root, "学習履歴.md", "history.md"), render_history(rows))
    return {
        "average": average,
        "weak": weak,
        "strong": strong,
        "next_review": next_review,
        "next_review_interval_days": next_review_interval_days,
    }


def finalize_session(
    path: Path,
    session_number: int,
    summary: dict[str, object],
    graded_date: Optional[date] = None,
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
    if graded_date is not None:
        graded_line = f"- Graded: {graded_date.isoformat()}"
        if re.search(r"^- Graded:[ \t]*\d{4}-\d{2}-\d{2}[ \t]*$", session, re.MULTILINE):
            session = re.sub(
                r"^- Graded:[ \t]*\d{4}-\d{2}-\d{2}[ \t]*$",
                graded_line,
                session,
                count=1,
                flags=re.MULTILINE,
            )
        else:
            session = re.sub(
                r"(^- Status:[ \t]*graded[ \t]*$)",
                rf"\1\n{graded_line}",
                session,
                count=1,
                flags=re.MULTILINE,
            )
    strong = "、".join(summary["strong"]) if summary["strong"] else "—"
    weak = "、".join(summary["weak"]) if summary["weak"] else "—"
    review_interval_days = summary.get("next_review_interval_days")
    review_guidance = "次の学習時に優先"
    if isinstance(review_interval_days, int):
        review_guidance += f"（目安: {review_interval_days}日後）"
    summary_text = (
        f"## Session {session_number} Summary\n\n"
        f"- Average: {summary['average']} / 100\n"
        f"- Strong points: {strong}\n"
        f"- Weak points: {weak}\n"
        f"- 次回復習: {review_guidance}\n"
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


def finalize_quick_review_session(
    path: Path,
    session_number: int,
    correct: int,
    question_count: int,
    graded_date: Optional[date] = None,
) -> None:
    """Mark a quick review complete without writing mastery or coverage progress."""
    text = path.read_text(encoding="utf-8")
    start, end = session_bounds(text, session_number)
    session = text[start:end]
    session = re.sub(
        r"^- Status:[ \t]*\S+[ \t]*$", "- Status: graded", session, count=1, flags=re.MULTILINE
    )
    if graded_date is not None:
        graded_line = f"- Graded: {graded_date.isoformat()}"
        if re.search(r"^- Graded:[ \t]*\d{4}-\d{2}-\d{2}[ \t]*$", session, re.MULTILINE):
            session = re.sub(
                r"^- Graded:[ \t]*\d{4}-\d{2}-\d{2}[ \t]*$",
                graded_line,
                session,
                count=1,
                flags=re.MULTILINE,
            )
        else:
            session = re.sub(
                r"(^- Status:[ \t]*graded[ \t]*$)",
                rf"\1\n{graded_line}",
                session,
                count=1,
                flags=re.MULTILINE,
            )
    summary = (
        f"## Session {session_number} Summary\n\n"
        f"- Correct: {correct} / {question_count}\n"
        "- Mastery updated: いいえ（3択の正答は理解度・復習期限・カバレッジへ反映しない）\n"
        "- Incorrect answers remain candidates for the next quick review.\n"
    )
    pattern = re.compile(rf"^## Session {session_number} Summary[ \t]*$.*\Z", re.MULTILINE | re.DOTALL)
    session = pattern.sub(summary, session) if pattern.search(session) else session.rstrip() + "\n\n" + summary
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
    session_mode = session_mode_for_path(root, session_path, text, session_number)
    graded_date = current_study_date()
    pending_activity = GradedActivity(
        study_date=study_date,
        session_number=session_number,
        session_kind={
            TERM_RECALL_MODE: "暗記語句問題",
            QUICK_REVIEW_MODE: "10分復習",
        }.get(session_mode, "理解・応用問題"),
        question_count=len(questions),
        session_link_path=Path(
            os.path.relpath(session_path, sessions_directory(root))
        ).as_posix(),
    )
    if session_mode == QUICK_REVIEW_MODE:
        if status not in {"grading", "graded"}:
            raise ValueError("Set Session Status to grading after writing all scores, then run record")
        correct = sum(question.score == 100 for question in questions)
        write_motivation(root)
        write_unanswered_index(root)
        write_activity_log(root, graded_date, pending_activity)
        finalize_quick_review_session(
            session_path, session_number, correct, len(questions), graded_date
        )
        return {
            "average": round(100 * correct / len(questions)),
            "weak": [],
            "strong": [],
            "next_review": "—",
            "questions": len(questions),
            "session_path": session_path,
        }
    if status not in {"grading", "graded"}:
        raise ValueError("Set Session Status to grading after writing all scores, then run record")
    catalog = load_catalog(root)
    records = update_term_records(root, study_date, session_number, questions, catalog)
    update_domains(root, records, study_date, catalog)
    summary = update_history(
        root, study_date, session_number, questions, records, session_path, session_mode
    )
    write_motivation(root)
    write_unanswered_index(root)
    write_activity_log(root, graded_date, pending_activity)
    finalize_session(session_path, session_number, summary, graded_date)
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
            if mode == QUICK_REVIEW_MODE:
                continue
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
        render_domains(domain_rows, {}, [], current_study_date(), catalog),
    )
    atomic_write(progress_file(root, "学習履歴.md", "history.md"), render_history([]))

    for study_date, session_number, path, mode, questions in sessions:
        records = update_term_records(root, study_date, session_number, questions, catalog)
        update_domains(root, records, study_date, catalog)
        summary = update_history(
            root, study_date, session_number, questions, records, path, mode
        )
        finalize_session(path, session_number, summary)
    return {"sessions": len(sessions), "questions": sum(len(item[4]) for item in sessions)}
