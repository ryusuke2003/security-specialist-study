---
name: security-specialist-trainer
description: Markdown-based adaptive trainer for Japan's Registered Information Security Specialist exam (情報処理安全確保支援士・セキスペ), covering short term-recall practice, written explanations, and Subject B scenarios. Use when the user asks to create or customize セキスペ practice questions (問題作って、今日の問題、暗記単語問題、暗記語句問題、復習、科目B、特定分野), grade or review answers (採点、答え合わせ、レビュー), or report mastery, strengths, weaknesses, and due reviews (理解度、今日の結果、弱点).
---

# Security Specialist Trainer

Build recall and explanation skill from Markdown history. Treat the repository containing this skill as the study root: from this file, resolve `../..` as the root. Keep `学習記録/` and `進捗/` as the source of truth; never replace them with JSON state.

## Route the request

Choose one workflow:

- Create questions: follow **Generate a session**. Requests such as「暗記単語問題作って」「暗記語句問題作って」「単語問題10問」「暗記問題20問作って」select term-recall mode.
- Requests such as「今日の10分復習」select quick-review mode.
- Grade answers: follow **Grade a session**.
- Show results or mastery: follow **Report progress**.
- Requests such as「未復習一覧を更新して」refresh the generated unreviewed index with the command below; do not edit the date-based review notes themselves.
- Combine requests only when the user clearly asks for both; finish grading before generating later adaptive questions.

Read [セッション形式.md](../../参照資料/セッション形式.md) before writing or grading a session. Read [採点・理解度・復習ルール.md](../../参照資料/採点・理解度・復習ルール.md) before selecting adaptive questions or assigning scores. Read [出題分類と概念カタログ.md](../../参照資料/出題分類と概念カタログ.md) when introducing concepts, checking prerequisites, or resolving domains and related terms.

## Generate a session

Perform these steps in order:

1. Obtain the current JST study date as `YYYY-MM-DD` with `python3 skills/security-specialist-trainer/scripts/study_helper.py study-date --root .`; do not infer it from an old session filename. The study day changes at 05:00 JST, so 00:00〜04:59 belongs to the previous calendar date.
2. Read every file under `進捗/`.
3. Read the latest three session files across `学習記録/理解・応用問題/` and `学習記録/暗記語句問題/`, including every session in those files. Also accept legacy files under `学習記録/standard/`, `学習記録/term-recall/`, or directly under `学習記録/`. Read more only when notes or related weaknesses require it.
4. Inspect domain scores, term scores, last-study dates, attempts, averages, recent difficulty, next-review dates, and recent domain mix.
   Use `参照資料/出題分類と概念カタログ.md` and `進捗/` as the learning evidence for daily selection. Read recent Sessions only to prevent materially duplicated wording; do not open past-question PDFs or `参照資料/過去問分析索引.md` during a routine daily session.
5. Estimate forgetting and priority using `../../参照資料/採点・理解度・復習ルール.md`.
6. Run the deterministic planner unless it is unavailable:

   ```bash
   python3 skills/security-specialist-trainer/scripts/study_helper.py plan \
     --root . --date YYYY-MM-DD
   ```

   Add `--count N`, `--focus 'Webセキュリティ'`, or `--mode weak|new|subject-b|light|term-recall|quick-review` to reflect the request. Explicit counts must be between 1 and 30 for every mode; do not clamp an out-of-range request. Use `--mode term-recall` for a term-recall request and `--mode quick-review` for a 10-minute review. Exclude every `Primary Term` that is already assigned to an unanswered question by default; only add `--include-unanswered` when the user explicitly asks to review or repeat unanswered material. Use the planner as a candidate plan, not as permission to ignore prerequisites or recent question wording.
7. A default normal session has six questions: two weak, one due review, two new, and one strong/challenge. When the user explicitly requests more than six normal questions, retain those six slots and make every additional slot new. Keep Subject B material around 70–85%; for the default six questions, make five Subject B-style. A Subject B-style question must present a short situation such as a log, configuration, system structure, operational procedure, or attack path and ask the learner to identify what to check, explain the cause or impact, or prioritize a countermeasure. Do not count a bare 「説明してください」 question as Subject B material. Keep pure explanation questions to at most one per normal session unless the user explicitly asks for them, a first-session diagnosis requires them, or the concept is too weak for even a short scenario. For term-recall sessions, follow **Generate a term-recall session** below. An explicit focus or style such as weak/new/subject-b takes precedence over this default allocation.
8. Write normal questions to `学習記録/理解・応用問題/YYYY-MM-DD.md` and term-recall questions to `学習記録/暗記語句問題/YYYY-MM-DD.md`. Determine the next Session number from every file for that date across both current directories and all legacy Session paths. Create the target file heading if absent; otherwise append without changing earlier sessions. Every Session must contain exactly one integer `Question Count` from 1 to 30. Keep internal metadata and CLI identifiers in English (`Mode: adaptive`, `Mode: term-recall`, `--mode standard`, and `--mode term-recall`). After creating the Session, run `python3 skills/security-specialist-trainer/scripts/study_helper.py unanswered --root .` to refresh `学習記録/未解答一覧.md`, then run `python3 skills/security-specialist-trainer/scripts/study_helper.py unreviewed --root .` to refresh `復習用/未復習一覧.md`. Render the unanswered index with its title followed directly by problem-type headings or `未解答はありません。`; do not add explanatory prose. Verify that each complete list entry links to its source Session file.

Use eight cross-domain Level 2–3 questions for an unassessed first session unless the user specifies a count or asks for light practice. For the default eight, use exactly one question from each of Web, network, cryptography, authentication, PKI, DNS, email, and malware; do not substitute another domain. Use six questions normally and three for light practice.

For each question:

- Add a `### 問題` heading directly below the metadata, then write the question text as regular Markdown below that heading. Do not put question text inside an HTML comment.
- Keep Domain, Primary Terms, Related Terms, Level, and Track visible as metadata. Write Primary Terms and Related Terms as one backtick-wrapped concept per nested Markdown list item; never join terms with `/` or another delimiter. Put only independently scored concepts in Primary Terms, use exact taxonomy spelling, and put supporting context in Related Terms.
- For normal and term-recall Sessions, add an empty `### 回答` area with the standard placeholder comment.
- Ask for explanation, causality, conditions, application, or comparison. Avoid pure term-to-definition recall unless Level 1 is justified.
- Match Level 1–3 to weak concepts and Level 4–6 to demonstrated mastery.
- Prefer short logs, traffic, settings, system structures, operational procedures, and incident narratives. Ask a concrete decision such as the investigation point, likely cause or impact, countermeasure priority, or residual risk; do not turn these into an abstract explanation request after adding a scenario.
- Move strong concepts toward competing controls and residual risk. Even weak concepts should normally use a one-step scenario before falling back to a pure explanation question.
- Avoid repeating materially identical wording from recent sessions.
- In SSRF explanations, state that the dangerous attacker-supplied destination is an internal-facing URL (localhost, private network, or cloud metadata service), rather than leaving the target URL generic. External URLs can also be supplied, but distinguish them from the principal SSRF risk.
- For hostname-verification scenarios, treat SAN (`dNSName` for FQDNs and `iPAddress` for IP literals) as the matching source. Do not present a CN-only certificate as valid under modern TLS verification; CN fallback may be mentioned only as a legacy compatibility exception.
- Do not include answers or leading hints in the question file.

After writing, verify the file, confirm that `Question Count` equals the actual number of questions, and confirm that question headings are unique and consecutive from `Q1`. Reject any heading beginning with `### Q` that does not exactly match this numbered form. Also verify metadata, one `### 問題` heading per question, visible question text, and answer placeholders. In chat, respond briefly with the absolute clickable session path, question count, and any requested emphasis. Do not duplicate all question text in chat.

### Generate a term-recall session

Use this mode only when the request asks for term/word memorization or recall. If no count is given, create exactly 10 questions; otherwise honor the explicit count from 1 to 30. Run:

```bash
python3 skills/security-specialist-trainer/scripts/study_helper.py plan \
  --root . --date YYYY-MM-DD --mode term-recall --count N
```

The planner treats the existing overall score, mode-specific scores, attempts, last-study date, last score, next review, forgetting, recent appearances, weak related terms, and unassessed terms as one adaptive history. Normal sessions use Explanation Score for their own weakness and difficulty; term-recall sessions use Recall Score for their own weakness and retention judgment. A mode with no evidence is unseen in that mode, while the other mode still contributes cross-mode priority. Do not replace the result with random selection. Use exact taxonomy terms, assign exactly one Primary Term to each question, and do not assign the same Primary Term twice in one Session. A graded `わかりません` counts as one Recall Attempt; an Explanation Attempt alone does not.

Do **not** inspect past-question materials or expand the concept catalog during routine question generation, even if coverage milestones have been reached. Do so only when the user explicitly asks for catalog expansion or a past-question-informed catalog review; then read [カタログ拡張.md](references/カタログ拡張.md).

Set `Mode: term-recall`, `Level: 1`, and `Track A/B Target: 40% / 60%`. Use `A = floor(count * 0.40)` and assign every remainder to B, so 5 questions are A2/B3 and 10 are A4/B6. For this mode, taxonomy Track `B` stays Session Track `B`; taxonomy Track `A` or `A/B` uses Session Track `A`. The progress catalog Track remains unchanged.

Use the short question emitted in the plan, normally「`用語`とは何ですか？」. The target answer is a single short sentence that states the core meaning, such as「クラウドの提供側と利用者側で責任を分担すること。」 Do not ask for purpose, features, mechanism, a scenario, comparison, countermeasure, residual-risk, or a long-form explanation. For grading, treat a correct core definition as sufficient for full credit; assess purpose and detailed features only in normal understanding/application sessions. Determine the minimal essential elements that distinguish the term from adjacent concepts, and award full credit only when the answer expresses all of them (accept semantically equivalent wording). If an essential element is omitted, whether it is visibly blank such as `〇〇` or simply absent, award partial credit and record that element as a gap. The normal-session rule against pure definition recall does not apply here.

### Generate a quick-review session

Use this mode only for a request such as「今日の10分復習」. Create exactly eight questions unless the user explicitly requests 1〜30. Select four overdue terms, two terms due today, and two low-score terms; the planner fills any unavailable slots by priority. Save it to `学習記録/10分復習/YYYY-MM-DD.md` and use `Mode: quick-review`.

Every question has exactly three plausible choices labeled `A` / `B` / `C`, with one correct choice. Render every choice as a Markdown task-list item such as `- [ ] A. ...`; the learner selects exactly one by checking its box. Do not add a `### 回答` section or instructions telling the learner to use the checkboxes. When grading, read the one checked choice; zero or multiple checked choices are unanswered and must not be graded. Keep the correct choice out of the Session Markdown until grading.

Write distractors as realistic near-misses, not absurdly unrelated statements. Prefer a related mechanism with a different role, a control that is useful but insufficient for the stated condition, or an explanation that is correct except for one material condition, actor, scope, or order. The correct choice alone must satisfy every condition in the question; do not make two defensible choices or use obscure trivia to force a distinction. Avoid choices that can be rejected solely because they are clearly destructive, impossible, or from an unrelated domain. This is a short-start review, not evidence of mastery: grade an answer as correct or incorrect with a compact explanation. For every incorrect answer, add a next-study-day entry to `復習用/明日復習するべきところ/YYYY-MM-DD.md` when grading; do not update Score, Attempts, either mode-specific score, review dates, or coverage.

### Automatically create today's quick review for learning workflows

At the start of every question-generation or session-grading workflow, obtain the current JST study date (the study day changes at 05:00 JST) and run:

```bash
python3 skills/security-specialist-trainer/scripts/study_helper.py quick-review-status \
  --root . --date YYYY-MM-DD
```

If the result is `missing`, immediately generate one default eight-question quick-review Session using the procedure above, before the requested generation or grading. A non-cancelled Session makes the status `exists`, so later learning workflows on the same day do not create duplicates. Do not run this check for greetings, documentation questions, or other non-learning requests. If the user explicitly asks「今日の10分復習」or「復習問題作って」, always create the requested quick-review Session even when the status is `exists`; when it is `missing`, this requested Session satisfies the daily one-session requirement rather than creating a second automatic Session. Skip only when the user explicitly asks to avoid study changes.

## Grade a session

Use [採点ワークフロー.md](references/採点ワークフロー.md) in this order:

1. Read **採点前チェック** before inspecting answer prose. It determines the complete worklist and order.
2. For each selected Session, read **採点・記録**. It covers scoring, progress updates, recovery, and verification.
3. Read **復習ノート作成** before creating or updating diagrams, learned notes, or next-day review entries.

Use `../../参照資料/採点・理解度・復習ルール.md` as the arithmetic authority. Update only Primary Terms numerically; Related Terms remain context until directly assessed.

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
