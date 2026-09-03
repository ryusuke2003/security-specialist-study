"""Command-line interface for the security-specialist trainer helpers."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Optional

from .common import (
    DEFAULT_NORMAL_QUESTION_COUNT,
    QUICK_REVIEW_MODE,
    STANDARD_SESSION_MODE,
    TERM_RECALL_MODE,
    as_date,
    current_study_date,
    load_catalog,
    load_terms,
    merge_uncatalogued_terms,
)
from .indexes import (
    graded_activities,
    grading_candidates,
    unanswered_primary_terms,
    unanswered_questions,
    unreviewed_items,
    write_activity_log,
    write_motivation,
    write_unanswered_index,
    write_unreviewed_index,
)
from .planner import (
    adaptive_plan,
    build_candidates,
    diagnostic_plan,
    exclude_unanswered_candidates,
    quick_review_plan,
    render_briefing,
    render_plan,
    term_recall_plan,
)
from .progress import rebuild_progress, record_progress
from .session_parser import (
    quick_review_exists,
    quick_review_incorrect_terms,
    recent_domain_counts,
    recent_term_counts,
    validate_authored_session,
)



def default_root() -> Path:
    return Path(__file__).resolve().parents[4]


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Plan and record adaptive security-specialist study in Markdown."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    plan_parser = subparsers.add_parser("plan", help="Print a Markdown selection plan without changing files.")
    plan_parser.add_argument("--root", type=Path, default=default_root())
    plan_parser.add_argument("--date", type=as_date)
    plan_parser.add_argument("--count", type=int)
    plan_parser.add_argument("--focus", default="")
    plan_parser.add_argument(
        "--include-unanswered",
        action="store_true",
        help="Allow terms already assigned to unanswered questions; use only for an explicit review request.",
    )
    plan_parser.add_argument(
        "--mode",
        choices=["standard", "weak", "new", "subject-b", "light", TERM_RECALL_MODE, QUICK_REVIEW_MODE],
    )
    briefing_parser = subparsers.add_parser(
        "briefing",
        help="Print bounded authoring context from progress and recent Sessions without changing files.",
    )
    briefing_parser.add_argument("--root", type=Path, default=default_root())
    briefing_parser.add_argument("--date", type=as_date)
    briefing_parser.add_argument("--count", type=int)
    briefing_parser.add_argument("--focus", default="")
    briefing_parser.add_argument(
        "--include-unanswered",
        action="store_true",
        help="Allow terms already assigned to unanswered questions; use only for an explicit review request.",
    )
    briefing_parser.add_argument(
        "--mode",
        choices=["standard", "weak", "new", "subject-b", "light", TERM_RECALL_MODE, QUICK_REVIEW_MODE],
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
        choices=[STANDARD_SESSION_MODE, TERM_RECALL_MODE, QUICK_REVIEW_MODE],
        help="Verify the mode-specific Session directory.",
    )
    validate_parser = subparsers.add_parser(
        "validate-session",
        help="Validate a newly authored Session before answers or progress updates.",
    )
    validate_parser.add_argument("--root", type=Path, default=default_root())
    validate_parser.add_argument("--date", type=as_date, required=True)
    validate_parser.add_argument("--session", type=int, required=True)
    validate_parser.add_argument(
        "--mode",
        choices=[STANDARD_SESSION_MODE, TERM_RECALL_MODE, QUICK_REVIEW_MODE],
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
    unreviewed_parser = subparsers.add_parser(
        "unreviewed",
        help="Write a compact Markdown list of unchecked review entries.",
    )
    unreviewed_parser.add_argument("--root", type=Path, default=default_root())
    activity_parser = subparsers.add_parser(
        "activity-log", help="Append a source-linked list of Sessions graded on a study date."
    )
    activity_parser.add_argument("--root", type=Path, default=default_root())
    activity_parser.add_argument("--date", type=as_date)
    motivation_parser = subparsers.add_parser(
        "motivation", help="Write the derived vocabulary-coverage dashboard."
    )
    motivation_parser.add_argument("--root", type=Path, default=default_root())
    candidates_parser = subparsers.add_parser(
        "grading-candidates", help="List fully answered Sessions that need grading.")
    candidates_parser.add_argument("--root", type=Path, default=default_root())
    quick_status_parser = subparsers.add_parser(
        "quick-review-status",
        help="Report whether today's quick-review Session already exists.",
    )
    quick_status_parser.add_argument("--root", type=Path, default=default_root())
    quick_status_parser.add_argument("--date", type=as_date)
    study_date_parser = subparsers.add_parser(
        "study-date",
        help="Print the current JST study date; the study day starts at 05:00.",
    )
    study_date_parser.add_argument("--root", type=Path, default=default_root())
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)
    root = args.root.resolve()
    if args.command == "study-date":
        print(current_study_date().isoformat())
        return 0
    if args.command == "validate-session":
        if args.date is None:
            print("error: --date must use YYYY-MM-DD", file=sys.stderr)
            return 2
        if args.session < 1:
            print("error: --session must be positive", file=sys.stderr)
            return 2
        try:
            result = validate_authored_session(
                root, args.date, args.session, args.mode
            )
        except ValueError as error:
            print(f"error: {error}", file=sys.stderr)
            return 2
        print(
            f"Validated {result['questions']} questions for {args.date.isoformat()} "
            f"Session {args.session}; mode={result['mode']}; path={result['path']}"
        )
        return 0
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

    if args.command == "unreviewed":
        path = write_unreviewed_index(root)
        print(f"Wrote {len(unreviewed_items(root))} unreviewed items to {path}")
        return 0

    if args.command == "activity-log":
        graded_date = args.date or current_study_date()
        path = write_activity_log(root, graded_date)
        print(
            f"Wrote {len(graded_activities(root, graded_date))} graded Sessions to {path}"
        )
        return 0

    if args.command == "motivation":
        path = write_motivation(root)
        print(f"Wrote motivation dashboard to {path}")
        return 0

    if args.command == "grading-candidates":
        candidates = grading_candidates(root)
        if not candidates:
            print("採点候補はありません。")
            return 0
        print("# 採点候補")
        for candidate in candidates:
            relative = Path(os.path.relpath(candidate.path, root)).as_posix()
            print(f"- {candidate.study_date} / Session {candidate.session_number} / {candidate.session_kind} / {candidate.question_count}問 / {relative}")
        return 0

    if args.command == "quick-review-status":
        study_date = args.date or current_study_date()
        state = "exists" if quick_review_exists(root, study_date) else "missing"
        print(f"Quick review for {study_date.isoformat()}: {state}")
        return 0

    catalog = load_catalog(root)
    if not catalog:
        print(f"error: no concept catalog found under {root / '参照資料' / '出題分類と概念カタログ.md'}", file=sys.stderr)
        return 2
    terms = load_terms(root)
    catalog = merge_uncatalogued_terms(catalog, terms)
    today = args.date or current_study_date()
    mode = args.mode or STANDARD_SESSION_MODE
    requested_count = args.count
    if requested_count is not None and not 1 <= requested_count <= 30:
        print("error: --count must be between 1 and 30", file=sys.stderr)
        return 2

    assessed = any(record.attempts > 0 for record in terms.values())
    pending_terms = set() if args.include_unanswered else unanswered_primary_terms(root)
    if mode == QUICK_REVIEW_MODE:
        count = requested_count if requested_count is not None else 8
        candidates = build_candidates(
            catalog, terms, today, recent_domain_counts(root), args.focus,
            STANDARD_SESSION_MODE, recent_term_counts(root, today),
        )
        plan = quick_review_plan(
            exclude_unanswered_candidates(candidates, pending_terms, args.include_unanswered),
            terms, today, count, quick_review_incorrect_terms(root),
        )
        phase = QUICK_REVIEW_MODE
    elif mode == TERM_RECALL_MODE:
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
    if args.command == "briefing":
        print(render_briefing(root, plan, phase, today, mode))
    else:
        print(render_plan(plan, phase, today, mode))
    return 0
