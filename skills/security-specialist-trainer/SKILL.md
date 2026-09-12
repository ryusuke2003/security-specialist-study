---
name: security-specialist-trainer
description: Create, customize, grade, and review 情報処理安全確保支援士（セキスペ）practice in Markdown. Use for 問題作って、今日の問題、暗記単語・語句問題、復習、科目B、採点、答え合わせ、理解度、弱点, and security flow diagrams showing who sends or holds what（流れ図、認証フロー）.
---

# Security Specialist Trainer

Use the repository root (`../..` from this skill directory) as the study root. Keep `学習記録/` and `進捗/` as Markdown sources of truth; never replace them with JSON state. Run commands from that root.

## Keep exam scope proportional

For every generated or updated study artifact—including questions, answer explanations, grading feedback, review notes, diagrams, catalogs, and reference docs—check whether each detail is worth the learning cost for passing 情報処理安全確保支援士（SC）. Prefer the minimum depth needed to answer likely exam questions correctly and distinguish nearby concepts. Do not add exhaustive standards trivia, implementation-specific edge cases, or adjacent technologies only for completeness.

Extra depth is allowed when it materially prevents a likely misconception, explains why a core mechanism works, or makes a flow or comparison easier to understand. Keep such detail clearly supplementary; do not turn it into required answer elements, Primary Terms, or future review targets unless its exam relevance is established.

## Select one workflow

### Generate questions

1. Complete [共通開始処理.md](references/共通開始処理.md) once, then follow [問題作成ワークフロー.md](references/問題作成ワークフロー.md).
2. Read [セッション形式.md](../../参照資料/セッション形式.md) and only its matching mode detail, [出題選定ルール.md](references/出題選定ルール.md), and [カタログ部分参照.md](references/カタログ部分参照.md).
3. Start from `study_helper.py briefing`; inspect only the selected catalog rows, needed direct prerequisites, and flagged source Sessions. Do not replace adaptive candidates with random terms.

「暗記単語問題」「暗記語句問題」「単語問題」「暗記問題」select term-recall;「今日の10分復習」selects quick-review. Follow the common preflight for explicit review requests and the no-study-changes opt-out.

Inspect past papers and [カタログ拡張.md](references/カタログ拡張.md) only when the user explicitly requests catalog expansion or a past-question-informed catalog review. Routine generation must not expand the catalog.

### Grade answers

Complete the common preflight, then run `python3 skills/security-specialist-trainer/scripts/study_helper.py grading-candidates --root .` before reading answers. Honor an explicit target; otherwise process all candidates chronologically, recording each before the next.

- Quick-review only: read only [10分復習採点ワークフロー.md](references/10分復習採点ワークフロー.md).
- Normal or term-recall: read [セッション形式.md](../../参照資料/セッション形式.md), its matching mode detail, and [採点ワークフロー.md](references/採点ワークフロー.md). For mixed candidates, also read the quick-review workflow and apply it only to that mode.
- Routine grading must not load calculation formulas or reimplement progress math. `record` owns numerical mastery, review dates, and derived progress updates.

Only directly assessed Primary Terms in normal/term-recall Sessions update numerical mastery; Related Terms and quick-review results do not.

### Other requests

- Progress/results/weaknesses: read `進捗/` and only the recent Sessions needed to explain the estimate. Do not run learning preflight. Distinguish unassessed, recall-only, application-confirmed, and high-difficulty-stable evidence; never treat missing mode scores as zero.
- Exact score/review-date explanations, or changes/debugging of progress calculations: read [進捗計算仕様.md](../../参照資料/進捗計算仕様.md) and inspect only the implementation it names. Do not load it for routine grading.
- Create or update a security diagram, including during grading: follow [流れ図作成ルール.md](references/流れ図作成ルール.md).
- Update the unreviewed index: run `python3 skills/security-specialist-trainer/scripts/study_helper.py unreviewed --root .`; do not edit date-based review notes.

Combine workflows only when requested; finish grading before generating subsequent adaptive questions. Do not run learning preflight for greetings, documentation, or repository maintenance.

## Preserve assessment quality

Assess the user's explanation, not keyword overlap. Deduct only for errors or missing points explicitly requested by the question; supplementary knowledge must not reduce credit. A correct conclusion with faulty reasoning is incomplete. Ask a concise clarification only when the requested grading target genuinely remains ambiguous.
