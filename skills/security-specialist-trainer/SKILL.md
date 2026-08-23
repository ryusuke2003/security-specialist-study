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
- Do not include answers or leading hints in the question file.

After writing, verify the file, confirm that `Question Count` equals the actual number of questions, and confirm that question headings are unique and consecutive from `Q1`. Reject any heading beginning with `### Q` that does not exactly match this numbered form. Also verify metadata, one `### 問題` heading per question, visible question text, and answer placeholders. In chat, respond briefly with the absolute clickable session path, question count, and any requested emphasis. Do not duplicate all question text in chat.

### Generate a term-recall session

Use this mode only when the request asks for term/word memorization or recall. If no count is given, create exactly 10 questions; otherwise honor the explicit count from 1 to 30. Run:

```bash
python3 skills/security-specialist-trainer/scripts/study_helper.py plan \
  --root . --date YYYY-MM-DD --mode term-recall --count N
```

The planner treats the existing overall score, mode-specific scores, attempts, last-study date, last score, next review, forgetting, recent appearances, weak related terms, and unassessed terms as one adaptive history. Normal sessions use Explanation Score for their own weakness and difficulty; term-recall sessions use Recall Score for their own weakness and retention judgment. A mode with no evidence is unseen in that mode, while the other mode still contributes cross-mode priority. Do not replace the result with random selection. Use exact taxonomy terms, assign exactly one Primary Term to each question, and do not assign the same Primary Term twice in one Session.

Before creating the next term-recall Session, compare every current taxonomy term with `進捗/語句別理解度.md`. A graded `わかりません` counts as one Recall Attempt; an Explanation Attempt alone does not. Read `参照資料/過去問分析索引.md` only for a catalog review, never for a routine daily Session. When a catalog-expansion review is due (all 151 terms, then all roughly 250 terms, have `Recall Attempts >= 1`), inspect the local `過去問/` PDFs and the current official IPA SC syllabus. This directory is intentionally Git-ignored and may be absent or empty; use official online sources for missing years. Save the analysis as concise theme, candidate-term, and evidence-year entries in `参照資料/過去問分析索引.md`, then append 80〜120 previously absent high-priority terms for the first expansion or 20〜40 concrete-gap terms for later expansions. If the user explicitly asks to refer to past questions, inspect the PDFs even outside a full-lap review, then update the same index and any justified catalog relationships. Treat the candidate table as a broad collection list, not an adoption decision: also include a term that is clearly asked once in 午前II and is hard to explain with an existing term, helps read an 午後 scenario, is a reusable standard/attack/operation component, or is an older term that maps cleanly to a current mechanism. At expansion time, prioritize recurring terms, terms needed to explain Subject B scenarios, and prerequisites; set `Importance` and `Related` consistently with the existing catalog. Do not delete or rename existing terms, duplicate terms, or invent additions when official sources do not support them. Update the catalog's source/date/count note and the affected user-facing documentation, then plan from the expanded catalog.

Set `Mode: term-recall`, `Level: 1`, and `Track A/B Target: 40% / 60%`. Use `A = floor(count * 0.40)` and assign every remainder to B, so 5 questions are A2/B3 and 10 are A4/B6. For this mode, taxonomy Track `B` stays Session Track `B`; taxonomy Track `A` or `A/B` uses Session Track `A`. The progress catalog Track remains unchanged.

Use the short question emitted in the plan, normally「`用語`とは何ですか？」. The target answer is a single short sentence that states the core meaning, such as「クラウドの提供側と利用者側で責任を分担すること。」 Do not ask for purpose, features, mechanism, a scenario, comparison, countermeasure, residual-risk, or a long-form explanation. For grading, treat a correct core definition as sufficient for full credit; assess purpose and detailed features only in normal understanding/application sessions. The normal-session rule against pure definition recall does not apply here.

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

Perform these steps in order:

1. Before reading question prose, run `python3 skills/security-specialist-trainer/scripts/study_helper.py grading-candidates --root .`. This lightweight check scans only Session structure and answer/grade completion markers. Treat its complete chronological output as the worklist; do not narrow it by visual inspection, `Status`, Git state, or recent-file guesses.
2. Search every Session location below before scoring the listed candidates:
   - Current normal sessions: `学習記録/理解・応用問題/`
   - Current term-recall sessions: `学習記録/暗記語句問題/`
   - Current quick-review sessions: `学習記録/10分復習/`
   - Legacy normal sessions: `学習記録/standard/`
   - Legacy term-recall sessions: `学習記録/term-recall/`
   - Legacy root-level sessions: `学習記録/YYYY-MM-DD.md`
   For every Session, inspect the questions, answers, grading blocks, and Session Summary in the Session Markdown itself. Do **not** select by `Status`, or use `git diff`, commit history, or working-tree state to infer whether an answer exists: answers may already be committed, and `awaiting_answers` often remains after a user fills every answer. Ignore the standard HTML placeholder when deciding whether an answer is blank. A Session is a grading candidate when every answer is nonblank and either a question lacks a valid `### 採点` block or its Session Summary does not confirm `Progress updated`. Skip a Session with a user-requested `cancelled` Status.
3. Unless the user names a date or Session number, select **all** grading candidates and sort them in chronological order: date ascending, then Session number ascending. If a date or Session number is named, limit the selection to that Session. An incomplete Session is not a candidate: list its unanswered question numbers, but do not let it block other completed Sessions.
4. Process the full sorted candidate list sequentially. Finish scoring and recording the earlier Session before changing progress for the next one; this preserves chronological updates for overlapping Primary Terms. In both normal (understanding/application) and `term-recall` sessions, an explicit response such as `わかりません` is nonblank and must be scored `0 / 100` with a compact model explanation and next-review focus.
   For `quick-review`, identify the one checked `A` / `B` / `C` task-list choice and grade it as `100 / 100` or `0 / 100`. A question with zero or multiple checked choices is incomplete. Add every incorrect quick-review answer to the next-study-day review file under the `10分復習` group, following step 6. Use `record --mode quick-review` to mark only that Session complete; it must not change mastery progress.
4. For each selected Session, read every question, its metadata, and the user's full answer, then score each answer from 0 to 100 for conceptual meaning. In a normal session, select only applicable rubric dimensions that the question explicitly asks for: definition, principle, conditions, scenario/application, countermeasures with reasons, comparison/limits, and normalize applicable weights to 100. Award full credit when every requested point is conceptually correct. Do not lower a correct answer to 95 or another partial score merely because it omits an unasked detail, even if that detail would improve a model answer; mention such details only as optional enrichment, not as a missing point or next-review requirement. In `term-recall`, evaluate only whether the core definition is correct. Do not deduct for omitted purpose, features, mechanism, scenarios, advanced countermeasures, residual risk, comparisons, or length beyond the one short sentence expected.
5. Change the Session Status to `grading`. Upsert concise feedback under each answer: score, good points, missing or mistaken points, a short model explanation, and one next-review focus. On recovery, replace an existing grading block instead of appending a duplicate.
6. For each graded answer, decide whether a Mermaid diagram would make a difficult flow materially easier to review. Create one only for concepts involving multiple actors, ordered processing steps, branching conditions, trust/key/data movement, or incident/control sequences; do not create diagrams for isolated definitions or relationships that a short sentence makes clear.
   - Before creating anything, inspect every Markdown file under `復習用/流れ図/`. If an existing diagram already covers the same learning goal and flow (including a more detailed version), reuse it and do not create a duplicate.
   - For a genuinely new diagram, create `復習用/流れ図/<topic>.md` with a descriptive, stable topic name and a fenced `mermaid` diagram. Never place a Mermaid review diagram directly under `復習用/`; prose notes belong under `復習用/学んだこと/<分野>.md`. Use the diagram type that best fits the flow (`flowchart`, `sequenceDiagram`, or `stateDiagram-v2`), label actors, inputs, conditions, and outcomes clearly, and keep it compact enough for review.
   - When a flow involves actors, make the subject, recipient, and object explicit. Prefer `sequenceDiagram` for exchanges between actors; otherwise write edge labels as “who does what to whom/what,” such as “ブラウザがWebサーバへサーバ証明書を要求する.” Do not use ambiguous labels such as “送付” or “接続” by themselves. Use short labels and avoid HTML line-break tags when a renderer may not support them.
   - Treat these diagrams as durable review notes: make them technically correct and standalone, and do not alter an existing diagram merely to cover an unrelated question.
   - In both normal and `term-recall` sessions, decide for each graded answer whether the feedback reveals a reusable prose learning point worth retaining as「学んだこと」. If it does, inspect `復習用/学んだこと/README.md` and the closest existing domain note before adding it. Keep the note concise and avoid duplicating an existing explanation.
   - Record each new prose learning point under a level-2 date heading in the relevant `復習用/学んだこと/<分野>.md`, using the current JST study date as `## YYYY-MM-DD`. If that file already has a heading for the same date, append beneath it without adding a second date heading. Do not recreate the old single-file `復習用/学んだこと.md`.
   - Choose the most useful domain file rather than forcing an unrelated note into an existing category. When a new category is warranted, create `復習用/学んだこと/<分野>.md` and add it to `README.md`. You may also reorganize the domain notes when their boundaries or amount of content make retrieval harder: move retained content into clearer files, update the index and links in `README.md`, and preserve all learning points and their date headings. Do not leave duplicate copies after a reorganization.
   - Also update the next-day review file for **every** graded answer in normal and `term-recall` sessions with `Score < 100`, and for every incorrect `quick-review` answer. Use the next JST study date as `YYYY-MM-DD` (the study day changes at 05:00 JST) and aggregate all answers graded in the same study day into the single file `復習用/明日復習するべきところ/YYYY-MM-DD.md`. Create the directory and file when needed; use a title that identifies the review date and record the grading date. For each entry, after inspecting `復習用/流れ図/`, add a `流れ図` bullet when either an existing diagram or a newly created/materially expanded diagram directly supports the entry's question or explanation. Reuse the existing diagram instead of creating a duplicate, but still add the link. Use a relative Markdown link such as `[SAMLによるSSO](../流れ図/SAMLによるSSO.md)`. The next-day review directory and flow-diagram directory are siblings under `復習用/`, so use exactly one `..`; verify that the target file exists. Do not link an unrelated diagram; when reprocessing, retain or update the matching link without duplicating it.
   - Include every normal or `term-recall` answer with `Score < 100`, including answers that are mostly correct or only miss a small detail, and every incorrect `quick-review` answer (`Score: 0 / 100`). Do not add 100-point answers. Do not group entries by problem type or score range: place every entry in one list, sorted by score ascending. Break ties by source date, then Session number, then Q number ascending. Render each entry as a level-4 title such as `#### AEAD — 0点`, followed immediately by the Markdown task-list item `- [ ] 復習済み`, a separate `出典: YYYY-MM-DD / Session N / QN` line, and a bold `復習の要点` paragraph. Do not put `[ ]` inside a heading: it must be a list item so the checkbox is interactive. Put flow-diagram links and related terms in separate bullets below the paragraph; never place the metadata, explanation, and supplementary information in one long list item. Keep every entry regardless of score; the ascending order makes the highest-priority items appear first.
   - For each entry, write a standalone short explanation that restates the core question or situation and gives the correct principle, condition, distinction, or countermeasure. The reader must be able to understand what to review without reopening the source Session; do not leave only a term name or a terse reminder. Render the source identifiers as a link to the exact source question, for example `出典: [2026-08-23 / Session 2 / Q4](../../学習記録/理解・応用問題/2026-08-23.md#q4)`. From `復習用/明日復習するべきところ/`, use `../../学習記録/` and the lowercase GitHub-style question anchor. If the same `### QN` heading has appeared earlier in the source file, use the duplicate-heading suffix (`#q4-1` for its second occurrence, then `#q4-2`). Verify the target file and exact Session/question heading exist. Keep the score as navigation metadata, but make the explanation the main review content.
   - Add one `関連する新語` to each entry: a closely related term with a one-sentence definition or role. Choose an exact **concept-catalog row** from `参照資料/出題分類と概念カタログ.md`, normally with `Importance >= 4`; this ensures the extra word is likely to be useful for the SC exam rather than merely adjacent technical jargon. Prefer `Track B` or `A/B`, terms supported by the past-question index, and then terms with no Recall Attempts and no Explanation Attempts in `進捗/語句別理解度.md`, in that order. Do not reuse the entry's Primary Term or add an unrelated term merely to satisfy the count. A lower-importance term is allowed only when it is essential to explain the entry and should be labeled as a supplementary detail; if the catalog has no genuinely related new term, state that no new term is added and explain why.
   - The next-day review file is a short-term checklist, so it may intentionally overlap with `復習用/学んだこと/`. When reprocessing a Session, update its existing entry identified by Session and Q number instead of adding a duplicate. Do not remove entries from other Sessions that were graded on the same day.
7. For each selected Session, run the idempotent recorder only after every question has one valid score. In the current Japanese Session directories, the recorder requires exactly one supported `Mode` (`diagnosis`, `adaptive`, or `term-recall`) and requires the directory to match that Mode: `学習記録/理解・応用問題/` accepts normal modes and `学習記録/暗記語句問題/` accepts only `term-recall`. Only legacy root-level and English-directory Sessions may omit Mode or ignore directory-to-Mode correspondence. For every mode, the recorder rejects a Session unless it has exactly one integer `Question Count` from 1 to 30, the declared count equals the actual question count, and question headings are unique and consecutive from `Q1`. It also rejects any heading beginning with `### Q` that is not an exact positive-integer question heading. For `term-recall`, it additionally requires exactly one Primary Term per question and rejects any non-Level-1 question, any Track value other than the literal `A` or `B` (including the literal `A/B`), or Track allocation that differs from `A = floor(count * 0.40)` and `B = remainder`. All validation happens before changing progress:

   ```bash
   python3 skills/security-specialist-trainer/scripts/study_helper.py record \
     --root . --date YYYY-MM-DD --session N --mode standard|term-recall
   ```

8. Let the recorder update `語句別理解度.md`, recompute `分野別理解度.md`, upsert `学習履歴.md`, append or replace the Session Summary, and change Status to `graded` last. It records the current JST study date in `Graded` and appends or refreshes that date's section in `学習記録/行ったこと.md`, a source-linked log of graded Sessions that preserves prior dates. It uses `Applied Sessions` to avoid double-counting after interruption. It updates overall Score for every mode and the matching Recall or Explanation score separately, including that mode's Last Studied and Next Review. Domain recency uses level-capped evidence, while Session averages and Recall Score retain the raw 0–100 score. The shared Next Review is only the earlier of the two mode-specific deadlines. Record overlapping Primary Terms in chronological Session order. Then run `python3 skills/security-specialist-trainer/scripts/study_helper.py unanswered --root .` to remove answered items from `学習記録/未解答一覧.md`, retaining one link from each remaining entry to its source Session file, and `python3 skills/security-specialist-trainer/scripts/study_helper.py unreviewed --root .` to refresh `復習用/未復習一覧.md`.
9. If the recorder reports that a completed Session is older than already-recorded evidence, leave that Session's Status as `grading` and rebuild all fully scored Sessions in chronological order before retrying later work:

   ```bash
   python3 skills/security-specialist-trainer/scripts/study_helper.py rebuild --root .
   ```

   This recovery replaces only derived progress files from the scored Session history and preserves the original Session Markdown. For other recorder failures, leave that Session's Status as `grading`, report the error, and stop before processing a later candidate. Never claim progress was updated and never set `graded` manually before all three progress files succeed.

Use `../../参照資料/採点・理解度・復習ルール.md` as the arithmetic authority. Update only Primary Terms numerically; Related Terms remain context until directly assessed. Keep all three progress files mutually consistent: the same date, domain name, question count, average, and next-review conclusions must agree. If the recorder is unavailable, reproduce its ordering and idempotency rules manually and mark `graded` only as the final write.

After each Session, reread the graded Session and the three progress files. Confirm one score per question, a correct arithmetic average, no duplicate term row, and no duplicate history row. If a new review diagram was created, render or otherwise verify that its Mermaid syntax is valid before reporting it. In chat, list every processed Session with its average, strongest point, most important gap, next review date, and links to any newly created review diagrams; link each session file.

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
