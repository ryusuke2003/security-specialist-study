# Repository instructions

When starting question generation or session grading in this repository, complete `skills/security-specialist-trainer/references/共通開始処理.md` before the requested workflow. It defines the non-cancelled daily quick-review check, the 05:00 JST study-date boundary, explicit quick-review requests, and the opt-out for requests that prohibit study changes. Do not perform this preflight for greetings, documentation questions, progress reports, or other requests that do not generate or grade questions.

For requests to create, customize, grade, review, or report progress on 情報処理安全確保支援士（セキスペ）practice, read and follow `skills/security-specialist-trainer/SKILL.md` completely before acting. This includes natural requests such as「問題作って」「今日の問題」「復習したい」「採点して」「答え合わせ」「理解度見せて」「今の弱点」and close paraphrases.

Treat this repository root as the study root. Keep `学習記録/` and `進捗/` in human-readable Markdown and preserve the schemas documented under `参照資料/`.

Only push changes to a remote when the user explicitly asks to push (for example, 「プッシュして」). Do not infer permission to push from requests to edit, commit, or finish work.

Write commit messages in Japanese.

Write Python test file names after the required `test_` prefix, test class names, and `test_` method names in Japanese so verbose local and CI logs describe the verified behavior in Japanese. Keep the `test_` prefix required by `unittest` discovery.

When implementation changes affect documented behavior, commands, configuration, directory structure, or workflows, update every affected document (including `README.md`, `参照資料/`, and review notes) in the same change.

When work reveals a reusable lesson that improves future accuracy, safety, clarity, or efficiency, update the relevant skill, instruction, reference, or documentation in the same change. Do not turn one-off task details or temporary circumstances into permanent rules.

When a change may leave obsolete files, generated artifacts, duplicate notes, or other remnants, do not delete them automatically. Identify the concrete candidates, explain why they may be unnecessary and any impact of removal, then ask the user whether to remove them.
