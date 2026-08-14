---
name: security-specialist-trainer
description: Markdown-based adaptive trainer for Japan's Registered Information Security Specialist exam (情報処理安全確保支援士・セキスペ), covering short term-recall practice, written explanations, and Subject B scenarios. Use when the user asks to create or customize セキスペ practice questions (問題作って、今日の問題、暗記単語問題、暗記語句問題、復習、科目B、特定分野), grade or review answers (採点、答え合わせ、レビュー), or report mastery, strengths, weaknesses, and due reviews (理解度、今日の結果、弱点).
---

# Security Specialist Trainer

Build recall and explanation skill from Markdown history. Treat the repository containing this skill as the study root: from this file, resolve `../..` as the root. Keep `sessions/` and `progress/` as the source of truth; never replace them with JSON state.

## Route the request

Choose one workflow:

- Create questions: follow **Generate a session**. Requests such as「暗記単語問題作って」「暗記語句問題作って」「単語問題10問」「暗記問題20問作って」select term-recall mode.
- Grade answers: follow **Grade a session**.
- Show results or mastery: follow **Report progress**.
- Combine requests only when the user clearly asks for both; finish grading before generating later adaptive questions.

Read [session-format.md](../../references/session-format.md) before writing or grading a session. Read [scoring-rules.md](../../references/scoring-rules.md) before selecting adaptive questions or assigning scores. Read [taxonomy.md](../../references/taxonomy.md) when introducing concepts, checking prerequisites, or resolving domains and related terms.

## Generate a session

Perform these steps in order:

1. Obtain the actual local date as `YYYY-MM-DD`; do not infer it from an old session filename.
2. Read every file under `progress/`.
3. Read the latest three session files across `sessions/理解・応用問題/` and `sessions/暗記語句問題/`, including every session in those files. Also accept legacy files under `sessions/standard/`, `sessions/term-recall/`, or directly under `sessions/`. Read more only when notes or related weaknesses require it.
4. Inspect domain scores, term scores, last-study dates, attempts, averages, recent difficulty, next-review dates, and recent domain mix.
5. Estimate forgetting and priority using `../../references/scoring-rules.md`.
6. Run the deterministic planner unless it is unavailable:

   ```bash
   python3 skills/security-specialist-trainer/scripts/study_helper.py plan \
     --root . --date YYYY-MM-DD
   ```

   Add `--count N`, `--focus 'Webセキュリティ'`, or `--mode weak|new|subject-b|light|term-recall` to reflect the request. Explicit counts must be between 1 and 30 for every mode; do not clamp an out-of-range request. Use `--mode term-recall` for a term-recall request. Use the planner as a candidate plan, not as permission to ignore prerequisites or recent question wording.
7. A default normal session has six questions: two weak, one due review, two new, and one strong/challenge. When the user explicitly requests more than six normal questions, retain those six slots and make every additional slot new. Keep Subject B material around 70–85%. For term-recall sessions, follow **Generate a term-recall session** below. An explicit focus or style such as weak/new/subject-b takes precedence over this default allocation.
8. Write normal questions to `sessions/理解・応用問題/YYYY-MM-DD.md` and term-recall questions to `sessions/暗記語句問題/YYYY-MM-DD.md`. Determine the next Session number from every file for that date across both current directories and all legacy Session paths. Create the target file heading if absent; otherwise append without changing earlier sessions. Every Session must contain exactly one integer `Question Count` from 1 to 30. Keep internal metadata and CLI identifiers in English (`Mode: adaptive`, `Mode: term-recall`, `--mode standard`, and `--mode term-recall`).

Use eight cross-domain Level 2–3 questions for an unassessed first session unless the user specifies a count or asks for light practice. For the default eight, use exactly one question from each of Web, network, cryptography, authentication, PKI, DNS, email, and malware; do not substitute another domain. Use six questions normally and three for light practice.

For each question:

- Add a `### 問題` heading directly below the metadata, then write the question text as regular Markdown below that heading. Do not put question text inside an HTML comment.
- Keep Domain, Primary Terms, Related Terms, Level, and Track visible as metadata. Write Primary Terms and Related Terms as one backtick-wrapped concept per nested Markdown list item; never join terms with `/` or another delimiter. Put only independently scored concepts in Primary Terms, use exact taxonomy spelling, and put supporting context in Related Terms.
- Add an empty `### 回答` area with the standard placeholder comment.
- Ask for explanation, causality, conditions, application, or comparison. Avoid pure term-to-definition recall unless Level 1 is justified.
- Match Level 1–3 to weak concepts and Level 4–6 to demonstrated mastery.
- Move strong concepts toward short logs, traffic, settings, incident narratives, competing controls, and residual risk.
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

Before creating the next term-recall Session, compare every current taxonomy term with `progress/terms.md`. A graded `わかりません` counts as one Recall Attempt; an Explanation Attempt alone does not. When a catalog-expansion review is due, first inspect every file under the local `過去問/` directory. Use any local IPA problem booklets, answer examples, and grading commentary as the primary source; this directory is intentionally Git-ignored and may be absent or empty, so create it if necessary and then use official online sources for any missing years. When every initial catalog term has `Recall Attempts >= 1` (all 151 terms), use the current official IPA SC syllabus and the latest available official past-question years, then append 80〜120 previously absent high-priority terms to reach about 250 terms before planning that Session. When every term in that expanded, roughly 250-term catalog has at least one Recall Attempt, repeat the official-source review; thereafter append 20〜40 terms only when past questions reveal a concrete gap. Prioritize recurring terms, terms needed to explain Subject B scenarios, and prerequisites; set `Importance` and `Related` consistently with the existing catalog. Do not delete or rename existing terms, duplicate terms, or invent additions when official sources do not support them. Update the catalog's source/date/count note and the affected user-facing documentation, then plan from the expanded catalog. Repeat the targeted gap review after each later full lap.

Set `Mode: term-recall`, `Level: 1`, and `Track A/B Target: 40% / 60%`. Use `A = floor(count * 0.40)` and assign every remainder to B, so 5 questions are A2/B3 and 10 are A4/B6. For this mode, taxonomy Track `B` stays Session Track `B`; taxonomy Track `A` or `A/B` uses Session Track `A`. The progress catalog Track remains unchanged.

Use the short question emitted in the plan, normally「`用語`とは何ですか？意味・目的・重要な特徴を簡潔に説明してください。」 Do not turn either Track into a scenario, comparison, countermeasure, residual-risk, or long-form question. One concise explanation is enough. The normal-session rule against pure definition recall does not apply here.

## Grade a session

Perform these steps in order:

1. Search every Session location below before selecting a grading target:
   - Current normal sessions: `sessions/理解・応用問題/`
   - Current term-recall sessions: `sessions/暗記語句問題/`
   - Legacy normal sessions: `sessions/standard/`
   - Legacy term-recall sessions: `sessions/term-recall/`
   - Legacy root-level sessions: `sessions/YYYY-MM-DD.md`
   For every Session, inspect the questions, answers, grading blocks, and Session Summary. Do **not** select by `Status`: `awaiting_answers` often remains after a user fills every answer. Ignore the standard HTML placeholder when deciding whether an answer is blank. A Session is a grading candidate when every answer is nonblank and either a question lacks a valid `### 採点` block or its Session Summary does not confirm `Progress updated`. Skip a Session with a user-requested `cancelled` Status.
2. Unless the user names a date or Session number, select **all** grading candidates and sort them in chronological order: date ascending, then Session number ascending. If a date or Session number is named, limit the selection to that Session. An incomplete Session is not a candidate: list its unanswered question numbers, but do not let it block other completed Sessions.
3. Process the full sorted candidate list sequentially. Finish scoring and recording the earlier Session before changing progress for the next one; this preserves chronological updates for overlapping Primary Terms. In both normal (understanding/application) and `term-recall` sessions, an explicit response such as `わかりません` is nonblank and must be scored `0 / 100` with a compact model explanation and next-review focus.
4. For each selected Session, read every question, its metadata, and the user's full answer, then score each answer from 0 to 100 for conceptual meaning. In a normal session, select only applicable rubric dimensions: definition, principle, conditions, scenario/application, countermeasures with reasons, comparison/limits, and normalize applicable weights to 100. In `term-recall`, evaluate what the term is, its purpose or role, and its essential characteristics or mechanism. Do not deduct for omitted scenarios, advanced countermeasures, residual risk, or long comparisons that the short question did not ask for.
5. Change the Session Status to `grading`. Upsert concise feedback under each answer: score, good points, missing or mistaken points, a short model explanation, and one next-review focus. On recovery, replace an existing grading block instead of appending a duplicate.
6. For each graded answer, decide whether a Mermaid diagram would make a difficult flow materially easier to review. Create one only for concepts involving multiple actors, ordered processing steps, branching conditions, trust/key/data movement, or incident/control sequences; do not create diagrams for isolated definitions or relationships that a short sentence makes clear.
   - Before creating anything, inspect every Markdown file under `復習用/流れ図/`. If an existing diagram already covers the same learning goal and flow (including a more detailed version), reuse it and do not create a duplicate.
   - For a genuinely new diagram, create `復習用/流れ図/<topic>.md` with a descriptive, stable topic name and a fenced `mermaid` diagram. Never place a Mermaid review diagram directly under `復習用/`; keep `復習用/学んだこと.md` at that level. Use the diagram type that best fits the flow (`flowchart`, `sequenceDiagram`, or `stateDiagram-v2`), label actors, inputs, conditions, and outcomes clearly, and keep it compact enough for review.
   - When a flow involves actors, make the subject, recipient, and object explicit. Prefer `sequenceDiagram` for exchanges between actors; otherwise write edge labels as “who does what to whom/what,” such as “ブラウザがWebサーバへサーバ証明書を要求する.” Do not use ambiguous labels such as “送付” or “接続” by themselves. Use short labels and avoid HTML line-break tags when a renderer may not support them.
   - Treat these diagrams as durable review notes: make them technically correct and standalone, and do not alter an existing diagram merely to cover an unrelated question.
7. For each selected Session, run the idempotent recorder only after every question has one valid score. In the current Japanese Session directories, the recorder requires exactly one supported `Mode` (`diagnosis`, `adaptive`, or `term-recall`) and requires the directory to match that Mode: `sessions/理解・応用問題/` accepts normal modes and `sessions/暗記語句問題/` accepts only `term-recall`. Only legacy root-level and English-directory Sessions may omit Mode or ignore directory-to-Mode correspondence. For every mode, the recorder rejects a Session unless it has exactly one integer `Question Count` from 1 to 30, the declared count equals the actual question count, and question headings are unique and consecutive from `Q1`. It also rejects any heading beginning with `### Q` that is not an exact positive-integer question heading. For `term-recall`, it additionally requires exactly one Primary Term per question and rejects any non-Level-1 question, any Track value other than the literal `A` or `B` (including the literal `A/B`), or Track allocation that differs from `A = floor(count * 0.40)` and `B = remainder`. All validation happens before changing progress:

   ```bash
   python3 skills/security-specialist-trainer/scripts/study_helper.py record \
     --root . --date YYYY-MM-DD --session N --mode standard|term-recall
   ```

8. Let the recorder update `terms.md`, recompute `domains.md`, upsert `history.md`, append or replace the Session Summary, and change Status to `graded` last. It uses `Applied Sessions` to avoid double-counting after interruption. It updates overall Score for every mode and the matching Recall or Explanation score separately. Domain recency uses level-capped evidence, while Session averages and Recall Score retain the raw 0–100 score. Next Review remains shared across modes. Record overlapping Primary Terms in chronological Session order.
9. If the recorder reports that a completed Session is older than already-recorded evidence, leave that Session's Status as `grading` and rebuild all fully scored Sessions in chronological order before retrying later work:

   ```bash
   python3 skills/security-specialist-trainer/scripts/study_helper.py rebuild --root .
   ```

   This recovery replaces only derived progress files from the scored Session history and preserves the original Session Markdown. For other recorder failures, leave that Session's Status as `grading`, report the error, and stop before processing a later candidate. Never claim progress was updated and never set `graded` manually before all three progress files succeed.

Use `../../references/scoring-rules.md` as the arithmetic authority. Update only Primary Terms numerically; Related Terms remain context until directly assessed. Keep all three progress files mutually consistent: the same date, domain name, question count, average, and next-review conclusions must agree. If the recorder is unavailable, reproduce its ordering and idempotency rules manually and mark `graded` only as the final write.

After each Session, reread the graded Session and the three progress files. Confirm one score per question, a correct arithmetic average, no duplicate term row, and no duplicate history row. If a new review diagram was created, render or otherwise verify that its Mermaid syntax is valid before reporting it. In chat, list every processed Session with its average, strongest point, most important gap, next review date, and links to any newly created review diagrams; link each session file.

## Report progress

Read all files under `progress/` and enough recent sessions to explain the current estimates. Report concisely:

1. Overall weighted picture and whether evidence is still provisional.
2. Domain scores and levels.
3. Especially weak terms.
4. Especially strong terms, including the highest level actually demonstrated.
5. Terms due now or soon and the reason.

When both mode scores exist, call out meaningful gaps such as strong term recall with weak explanation/application, or the reverse. Do not treat a missing mode-specific score in old data as zero.

Never calculate an overall score by treating `Unassessed` domains as zero. Distinguish current mastery from lifetime average. For “today's result,” summarize today's latest graded session and mention whether progress files were updated.

## Preserve learning quality

- Assess the user's own explanation, not keyword overlap with a model answer.
- Treat a correct conclusion with faulty reasoning as incomplete.
- Require why a countermeasure works and note its limits when the question asks for them.
- Do not permanently retire a 100-point concept. Schedule it later and raise its problem form.
- Introduce related terms through prerequisites and clusters, not random novelty.
- Keep model explanations compact enough that the next attempt still requires retrieval.
- Ask a concise clarification only when multiple ungraded sessions make the target genuinely ambiguous and the user's wording does not select one.
