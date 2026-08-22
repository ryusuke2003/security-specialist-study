# Repository instructions

When starting question generation or session grading in this repository, check whether a non-cancelled `学習記録/10分復習/YYYY-MM-DD.md` Session exists for the current JST study date. The study day changes at 05:00 JST; from 00:00 through 04:59, use the previous calendar date. If it does not, create exactly one default `quick-review` Session before the requested generation or grading, following `skills/security-specialist-trainer/SKILL.md`. Do not perform this check for greetings, documentation questions, or other non-learning requests. An explicit request such as「今日の10分復習」or「復習問題作って」always creates the requested quick-review Session even if one exists; that requested Session also satisfies the daily check. Do not create it only when the user explicitly asks to avoid study changes.

For requests to create, customize, grade, review, or report progress on 情報処理安全確保支援士（セキスペ）practice, read and follow `skills/security-specialist-trainer/SKILL.md` completely before acting. This includes natural requests such as「問題作って」「今日の問題」「復習したい」「採点して」「答え合わせ」「理解度見せて」「今の弱点」and close paraphrases.

Treat this repository root as the study root. Keep `学習記録/` and `進捗/` in human-readable Markdown and preserve the schemas documented under `参照資料/`.

Only push changes to a remote when the user explicitly asks to push (for example, 「プッシュして」). Do not infer permission to push from requests to edit, commit, or finish work.

Write commit messages in Japanese.

Write Python test file names after the required `test_` prefix, test class names, and `test_` method names in Japanese so verbose local and CI logs describe the verified behavior in Japanese. Keep the `test_` prefix required by `unittest` discovery.

When implementation changes affect documented behavior, commands, configuration, directory structure, or workflows, update every affected document (including `README.md`, `参照資料/`, and review notes) in the same change.

When work reveals a reusable lesson that improves future accuracy, safety, clarity, or efficiency, update the relevant skill, instruction, reference, or documentation in the same change. Do not turn one-off task details or temporary circumstances into permanent rules.

When a change may leave obsolete files, generated artifacts, duplicate notes, or other remnants, do not delete them automatically. Identify the concrete candidates, explain why they may be unnecessary and any impact of removal, then ask the user whether to remove them.
