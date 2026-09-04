"""Adaptive candidate ranking, planning, and authoring briefings."""
from __future__ import annotations

import hashlib
import math
import os
import re
from dataclasses import replace
from datetime import date
from pathlib import Path
from typing import Iterable, Optional

from .common import (
    Candidate,
    CatalogItem,
    DEFAULT_NORMAL_QUESTION_COUNT,
    DIAGNOSTIC_DOMAIN_ORDER,
    QUICK_REVIEW_MODE,
    STANDARD_SESSION_MODE,
    TERM_RECALL_MODE,
    TermRecord,
    base_interval,
    markdown_cell,
    target_level,
    term_recall_track_counts,
)
from .indexes import unanswered_primary_terms
from .session_parser import recent_mode_scores, recent_term_sources



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


def quick_review_plan(
    candidates: list[Candidate],
    records: dict[str, TermRecord],
    today: date,
    count: int = 8,
    incorrect_terms: Optional[set[str]] = None,
) -> list[tuple[str, Candidate]]:
    """Select a short review set: overdue 4, due today 2, low-score 2."""
    incorrect_terms = incorrect_terms or set()
    selected: list[tuple[str, Candidate]] = []
    buckets = [
        (
            "期限超過",
            (
                candidate for candidate in candidates
                if (record := records.get(candidate.item.term))
                and record.next_review and record.next_review < today
            ),
            min(4, count),
        ),
        (
            "今日の復習",
            (
                candidate for candidate in candidates
                if (record := records.get(candidate.item.term))
                and record.next_review == today
            ),
            min(2, max(0, count - 4)),
        ),
        (
            "低得点",
            (
                candidate for candidate in candidates
                if (record := records.get(candidate.item.term))
                and (record.score < 60 or candidate.item.term in incorrect_terms)
            ),
            min(2, max(0, count - 6)),
        ),
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
    return selected[:count]


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
    quick_review = bool(re.search(r"(?:今日の)?10分復習", request))
    term_recall = bool(
        re.search(r"暗記(?:単語|語句)?問題|(?:暗記)?(?:単語|語句)問題", request)
    )
    count_match = re.search(r"(\d+)\s*問", request)
    if quick_review:
        return QUICK_REVIEW_MODE, int(count_match.group(1)) if count_match else 8
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
    if mode == QUICK_REVIEW_MODE:
        lines.extend(
            [
                "- Format: 3-choice + D. わかりません",
                "- Scoring: incorrect answers are review signals; correct answers do not raise mastery scores",
                "",
                "| Slot | Bucket | Term | Domain | Track | Level | Form | Priority | Reason |",
                "|---:|---|---|---|---|---:|---|---:|---|",
            ]
        )
    elif mode == TERM_RECALL_MODE:
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
        form = "3択＋わかりません" if mode == QUICK_REVIEW_MODE else "語句説明" if mode == TERM_RECALL_MODE else suggested_form(candidate.suggested_level)
        row = (
            f"| {slot} | {bucket} | {item.term} | {item.domain} | {track} | "
            f"{candidate.suggested_level} | {form} | {candidate.priority:.1f} | {candidate.reason} |"
        )
        if mode == TERM_RECALL_MODE:
            row += f" {markdown_cell(term_recall_question(item.term))} |"
        lines.append(row)
    return "\n".join(lines)


def render_briefing(
    root: Path,
    plan: list[tuple[str, Candidate]],
    phase: str,
    today: date,
    mode: str,
) -> str:
    """Render bounded authoring context; it deliberately does not choose final wording."""
    lines = [
        "# 作問ブリーフィング",
        "",
        f"- Date: {today.isoformat()}",
        f"- Phase: {phase}",
        f"- Mode: {mode}",
        f"- Questions: {len(plan)}",
        "",
        "## 今回の候補",
        "",
    ]
    mode_scores = recent_mode_scores(root, mode)
    for bucket, candidate in plan:
        item = candidate.item
        lines.append(
            f"- [{bucket}] {item.term}（{item.domain} / Level {candidate.suggested_level}）: {candidate.reason}"
        )
        previous_score = mode_scores.get(item.term)
        if previous_score:
            study_date, session_number, score = previous_score
            lines.append(
                f"  - このモードの前回得点: {score} / 100（{study_date.isoformat()}#{session_number}）"
            )
        if item.related:
            lines.append(f"  - Related: {item.related}")
        if item.prerequisites:
            lines.append(f"  - 直接前提: {item.prerequisites}")

    domain_counts: dict[str, int] = {}
    for _, candidate in plan:
        domain = candidate.item.domain
        domain_counts[domain] = domain_counts.get(domain, 0) + 1
    lines.extend(["", "## 分野バランス", ""])
    for domain, count in sorted(domain_counts.items()):
        lines.append(f"- {domain}: {count}問")

    recent_sources = recent_term_sources(root)
    lines.extend(["", "## 注意", ""])
    repeated = False
    for _, candidate in plan:
        sources = recent_sources.get(candidate.item.term, [])
        if not sources:
            continue
        repeated = True
        rendered_sources = ", ".join(
            f"{session_day.isoformat()} Session {session_number} ({Path(os.path.relpath(path, root)).as_posix()})"
            for session_day, session_number, path in sources
        )
        lines.append(
            f"- {candidate.item.term}: 直近3 Sessionに既出（{rendered_sources}）。問題文の論点重複を元Sessionで確認する。"
        )
    if not repeated:
        lines.append("- 採用候補は直近3 SessionのPrimary Termにはありません。問題文の意味上の重複は、必要な元Sessionだけで確認する。")
    lines.extend(
        [
            "- この出力は候補と警告の集約であり、出題の自動確定ではない。採用後は候補行、必要な関連語・直接前提の行、警告に出た元Sessionだけを確認する。",
            "- `plan` と同じ選定ロジックを使うため、期限・弱点・重要度・直近出題・分野配分はここで確認する。",
        ]
    )
    return "\n".join(lines)
