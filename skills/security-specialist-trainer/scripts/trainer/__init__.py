"""Stable public API for the security-specialist trainer."""

from . import cli as _cli
from . import common as _common
from . import indexes as _indexes
from . import planner as _planner
from . import progress as _progress
from . import session_parser as _session_parser

__all__ = (
    "CatalogItem", "TermRecord", "Candidate", "GradedQuestion",
    "UnansweredQuestion", "UnreviewedItem", "GradingCandidate", "GradedActivity",
    "DIAGNOSTIC_DOMAIN_ORDER", "TERM_RECALL_MODE", "QUICK_REVIEW_MODE",
    "EXPLANATION_MODE", "STANDARD_SESSION_MODE", "DEFAULT_NORMAL_QUESTION_COUNT",
    "NORMAL_SESSION_MODES", "STANDARD_SESSION_DIRECTORY",
    "TERM_RECALL_SESSION_DIRECTORY", "QUICK_REVIEW_SESSION_DIRECTORY",
    "LEGACY_SESSION_DIRECTORIES", "CURRENT_SESSIONS_DIRECTORY",
    "CURRENT_PROGRESS_DIRECTORY", "CURRENT_REFERENCES_DIRECTORY",
    "STUDY_TIMEZONE", "STUDY_DAY_START_HOUR", "ANSWER_PLACEHOLDER",
    "current_study_date", "study_directory", "sessions_directory",
    "progress_directory", "references_directory", "localized_file", "progress_file",
    "reference_file", "split_markdown_row", "read_table", "as_int", "as_date",
    "optional_score", "load_catalog", "load_terms", "merge_uncatalogued_terms",
    "base_interval", "target_level", "level_cap", "blend_mastery", "updated_mastery",
    "updated_recall_mastery", "next_interval", "markdown_cell", "atomic_write",
    "parse_list_field", "quick_review_checked_choices", "term_recall_track_counts",
    "session_bounds", "session_file_paths", "session_path_for_mode", "session_mode",
    "is_legacy_session_path", "expected_mode_for_current_path", "session_mode_for_path",
    "next_session_number", "resolve_session_path", "validate_authored_session",
    "parse_graded_session", "recent_domain_counts", "recent_term_counts",
    "recent_term_sources", "all_scored_questions", "quick_review_incorrect_terms",
    "quick_review_exists", "unanswered_questions", "unanswered_primary_terms",
    "grading_candidates", "render_unanswered_index", "write_unanswered_index",
    "graded_activities", "render_activity_section", "write_activity_log",
    "render_motivation", "write_motivation", "unreviewed_items",
    "render_unreviewed_index", "write_unreviewed_index", "render_terms",
    "update_term_records", "domain_level", "domain_coverage", "render_domains",
    "update_domains", "render_history", "update_history", "finalize_session",
    "finalize_quick_review_session", "record_progress", "rebuild_progress",
    "tie_break", "build_candidates", "exclude_unanswered_candidates",
    "diagnostic_plan", "planned_track", "adaptive_plan", "term_recall_plan",
    "quick_review_plan", "suggested_form", "term_recall_question",
    "infer_generation_request", "render_plan", "render_briefing", "parse_args", "main",
)

_PUBLIC_MODULES = (_common, _session_parser, _indexes, _progress, _planner, _cli)
for _name in __all__:
    for _module in _PUBLIC_MODULES:
        if hasattr(_module, _name):
            globals()[_name] = getattr(_module, _name)
            break
    else:  # pragma: no cover - import itself fails if the declared API drifts.
        raise ImportError(f"trainer public API name is missing: {_name}")

del _name, _module
