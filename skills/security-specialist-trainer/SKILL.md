---
name: security-specialist-trainer
description: Markdown-based adaptive trainer for Japan's Registered Information Security Specialist exam (情報処理安全確保支援士・セキスペ), covering short term-recall practice, written explanations, Subject B scenarios, and concrete security process diagrams. Use when the user asks to create or customize セキスペ practice questions (問題作って、今日の問題、暗記単語問題、暗記語句問題、復習、科目B、特定分野), grade or review answers (採点、答え合わせ、レビュー), create a flow diagram that identifies who sends or holds what (流れ図、認証フロー、誰が何を送る), or report mastery, strengths, weaknesses, and due reviews (理解度、今日の結果、弱点).
---

# Security Specialist Trainer

Build recall and explanation skill from Markdown history. Treat the repository containing this skill as the study root: from this file, resolve `../..` as the root. Keep `学習記録/` and `進捗/` as the source of truth; never replace them with JSON state.

## Route the request

Choose one workflow:

- Create questions: follow **Generate a session**. Requests such as「暗記単語問題作って」「暗記語句問題作って」「単語問題10問」「暗記問題20問作って」select term-recall mode.
- Requests such as「今日の10分復習」select quick-review mode.
- Grade answers: follow **Grade a session**.
- Show results or mastery: follow **Report progress**.
- Create or update a security flow diagram: read and follow [流れ図作成ルール.md](references/流れ図作成ルール.md). Apply it both to direct diagram requests and diagrams added during grading.
- Requests such as「未復習一覧を更新して」run `python3 skills/security-specialist-trainer/scripts/study_helper.py unreviewed --root .`; do not edit the date-based review notes themselves.
- Combine requests only when the user clearly asks for both; finish grading before generating later adaptive questions.

Read [セッション形式.md](../../参照資料/セッション形式.md) before writing a session, then read only the matching mode detail it links to. For grading, use the mode-specific route below. Before selecting adaptive questions, read [出題選定ルール.md](references/出題選定ルール.md) and [カタログ部分参照.md](references/カタログ部分参照.md). During routine generation, retrieve only the selected candidates' catalog rows and the needed direct related or prerequisite rows; do not read [出題分類と概念カタログ.md](../../参照資料/出題分類と概念カタログ.md) in full. Read it in full only for catalog expansion, broad unfocused cross-domain generation, or catalog-consistency investigation.

Before either question generation or grading, read and complete [共通開始処理.md](references/共通開始処理.md). It owns the JST study-date and daily quick-review preflight used by both workflows. Do not run it for progress reports or other non-learning requests.

## Generate a session

After the common preflight, read [問題作成ワークフロー.md](references/問題作成ワークフロー.md) before writing. It defines planning and selection, each Session mode, and post-creation validation.

For routine generation, start from `study_helper.py briefing`; it aggregates progress and recent-session warnings. Read source progress files or Session files only when the briefing identifies a specific need for verification.

During routine generation, do **not** inspect past-question materials or expand the concept catalog. Do so only when the user explicitly requests catalog expansion or a past-question-informed catalog review; then read [カタログ拡張.md](references/カタログ拡張.md).

Keep questions adaptive, scenario-oriented where appropriate, and free of answers or leading hints. For hostname verification, use SAN (`dNSName` for FQDNs and `iPAddress` for IP literals), not CN-only validation. For SSRF, identify the dangerous attacker-supplied destination as an internal-facing URL (localhost, private network, or cloud metadata service).

## Grade a session

After the common preflight, run `python3 skills/security-specialist-trainer/scripts/study_helper.py grading-candidates --root .` before reading answer prose. Use every candidate in date and Session order.

- If every candidate is `10分復習`, read only [10分復習採点ワークフロー.md](references/10分復習採点ワークフロー.md).
- If any candidate is a normal or term-recall Session, read [セッション形式.md](../../参照資料/セッション形式.md), its matching mode detail, [採点ワークフロー.md](references/採点ワークフロー.md), and [採点・理解度・復習ルール.md](../../参照資料/採点・理解度・復習ルール.md). For a mixed worklist, also read the quick-review workflow and use it only for quick-review Sessions.

Only normal and term-recall Sessions update Primary Terms numerically; Related Terms remain context until directly assessed. Quick-review results never update mastery numerically.

## Report progress

Read all files under `進捗/` and enough recent sessions to explain the current estimates. Report concisely:

1. Overall weighted picture and whether evidence is still provisional.
2. Domain scores and levels.
3. Especially weak terms.
4. Especially strong terms, including the highest level actually demonstrated.
5. Terms due now or soon and the reason.
6. For each domain, distinguish unassessed, recall-only, application-confirmed, and high-difficulty-stable coverage. Use the displayed evidence counts and unassessed important-term count so a high score based on too little or too-easy evidence is not described as stable.

When both mode scores exist, call out meaningful gaps such as strong term recall with weak explanation/application, or the reverse. Do not treat a missing mode-specific score in old data as zero.

Never calculate an overall score by treating `Unassessed` domains as zero. Distinguish current mastery from lifetime average. For “today's result,” summarize today's latest graded session and mention whether progress files were updated.

## Preserve learning quality

- Assess the user's own explanation, not keyword overlap with a model answer.
- Deduct only for an error or a missing point that the question explicitly requires. Keep optional supplementary knowledge separate from scored feedback; never treat it as a reason to withhold full credit.
- Treat a correct conclusion with faulty reasoning as incomplete.
- Require why a countermeasure works and note its limits when the question asks for them.
- Do not permanently retire a 100-point concept. Schedule it later and raise its problem form.
- Introduce related terms through prerequisites and clusters, not random novelty.
- Keep model explanations compact enough that the next attempt still requires retrieval.
- Ask a concise clarification only when multiple ungraded sessions make the target genuinely ambiguous and the user's wording does not select one.
