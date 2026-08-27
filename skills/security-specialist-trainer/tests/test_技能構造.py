from __future__ import annotations

import ast
import re
import unittest
from pathlib import Path


class 技能構造テスト(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.skill = Path(__file__).resolve().parents[1]
        cls.root = cls.skill.parents[1]
        cls.grading_workflow = (
            cls.skill / "references" / "採点ワークフロー.md"
        )
        cls.catalog_expansion = cls.skill / "references" / "カタログ拡張.md"
        cls.question_workflow = cls.skill / "references" / "問題作成ワークフロー.md"

    def test_必須ファイルが存在する(self) -> None:
        expected = [
            self.root / "AGENTS.md",
            self.root / ".github" / "workflows" / "python-tests.yml",
            self.skill / "SKILL.md",
            self.skill / "agents" / "openai.yaml",
            self.root / "README.md",
            self.root / "docs" / "使い方.md",
            self.root / "docs" / "リポジトリ構成.md",
            self.root / "docs" / "出題・採点ロジック.md",
            self.root / "docs" / "開発・テスト.md",
            self.root / "進捗" / "語句別理解度.md",
            self.root / "進捗" / "分野別理解度.md",
            self.root / "進捗" / "学習履歴.md",
            self.root / "学習記録" / "未解答一覧.md",
            self.root / "復習用" / "未復習一覧.md",
            self.root / "参照資料" / "出題分類と概念カタログ.md",
            self.root / "参照資料" / "採点・理解度・復習ルール.md",
            self.root / "参照資料" / "セッション形式.md",
            self.grading_workflow,
            self.catalog_expansion,
            self.question_workflow,
        ]
        self.assertEqual([], [str(path) for path in expected if not path.is_file()])
        self.assertTrue((self.root / "学習記録" / "理解・応用問題").is_dir())
        self.assertTrue((self.root / "学習記録" / "暗記語句問題").is_dir())

    def test_復習メモと流れ図を専用ディレクトリへ保存する(self) -> None:
        review_dir = self.root / "復習用"
        notes_dir = review_dir / "学んだこと"
        next_day_dir = review_dir / "明日復習するべきところ"
        diagram_dir = review_dir / "流れ図"
        self.assertTrue(notes_dir.is_dir())
        self.assertTrue((notes_dir / "README.md").is_file())
        self.assertTrue(any(notes_dir.glob("*.md")))
        self.assertFalse((review_dir / "学んだこと.md").exists())
        self.assertTrue(next_day_dir.is_dir())
        self.assertTrue((next_day_dir / "README.md").is_file())
        self.assertTrue(diagram_dir.is_dir())

        diagram_files = sorted(diagram_dir.glob("*.md"))
        self.assertTrue(diagram_files)
        self.assertTrue(
            all("```mermaid" in path.read_text(encoding="utf-8") for path in diagram_files)
        )
        self.assertFalse(
            any(
                "```mermaid" in path.read_text(encoding="utf-8")
                for path in review_dir.glob("*.md")
            )
        )

        skill_text = (self.skill / "SKILL.md").read_text(encoding="utf-8")
        workflow_text = self.grading_workflow.read_text(encoding="utf-8")
        self.assertIn("復習ノート作成", skill_text)
        for expected in (
            "復習用/流れ図/<topic>.md",
            "復習用/学んだこと/<分野>.md",
            "## YYYY-MM-DD",
            "Score < 100",
            "誤答した10分復習",
            "復習用/明日復習するべきところ/YYYY-MM-DD.md",
            "関連する新語",
            "Importance 4以上",
        ):
            self.assertIn(expected, workflow_text)

    def test_翌日復習に全件掲載と点数順表示の規則がある(self) -> None:
        skill_text = self.grading_workflow.read_text(encoding="utf-8")
        review_readme = (
            self.root / "復習用" / "明日復習するべきところ" / "README.md"
        ).read_text(encoding="utf-8")
        self.assertIn("通常・暗記語句の `Score < 100`", skill_text)
        self.assertIn("誤答した10分復習", skill_text)
        self.assertIn("10分復習で不正解だった問題", review_readme)
        self.assertIn("点数・日付・Session・Q番号の順", skill_text)
        self.assertIn("100点未満なら必ず掲載", review_readme)
        self.assertIn("問題形式を区別せず点数の低い順", review_readme)
        self.assertIn("同点は出典の日付・Session番号・Q番号の順", review_readme)
        self.assertIn("流れ図", review_readme)
        self.assertIn("既存図を再利用", skill_text)

    def test_翌日復習から流れ図へのリンクは兄弟ディレクトリを参照する(self) -> None:
        skill_text = self.grading_workflow.read_text(encoding="utf-8")
        review_files = sorted(
            (self.root / "復習用" / "明日復習するべきところ").glob("*.md")
        )

        self.assertIn("元Qへの正確な相対リンク", skill_text)
        self.assertNotIn("../" * 2 + "流れ図/", skill_text)
        for review_file in review_files:
            links = re.findall(r"\]\((\.\./流れ図/[^)]+\.md)\)", review_file.read_text(encoding="utf-8"))
            for link in links:
                with self.subTest(review_file=review_file, link=link):
                    self.assertTrue((review_file.parent / link).is_file())

    def test_十分復習の自動作成は学習操作に限定する(self) -> None:
        agents_text = (self.root / "AGENTS.md").read_text(encoding="utf-8")
        skill_text = (self.skill / "SKILL.md").read_text(encoding="utf-8")
        workflow_text = self.question_workflow.read_text(encoding="utf-8")
        readme_text = (self.root / "README.md").read_text(encoding="utf-8")

        self.assertIn("When starting question generation or session grading", agents_text)
        self.assertNotIn("On every user interaction", agents_text)
        self.assertIn("問題作成ワークフロー", skill_text)
        self.assertIn("問題作成または採点では", workflow_text)
        self.assertNotIn("毎回のユーザー操作", workflow_text)
        self.assertIn("問題作成または採点を始めるとき", readme_text)

    def test_ルート説明書から詳細文書を参照できる(self) -> None:
        readme = (self.root / "README.md").read_text(encoding="utf-8")
        document_paths = (
            "docs/使い方.md",
            "docs/リポジトリ構成.md",
            "docs/出題・採点ロジック.md",
            "docs/開発・テスト.md",
        )
        for relative_path in document_paths:
            with self.subTest(relative_path=relative_path):
                self.assertIn(f"]({relative_path})", readme)
                self.assertTrue((self.root / relative_path).is_file())

    def test_技能のフロントマターは必要項目だけを持つ(self) -> None:
        text = (self.skill / "SKILL.md").read_text(encoding="utf-8")
        match = re.match(r"^---\n(.*?)\n---", text, flags=re.DOTALL)
        self.assertIsNotNone(match)
        assert match
        fields = [line.split(":", 1)[0] for line in match.group(1).splitlines() if ":" in line]
        self.assertEqual(["name", "description"], fields)
        self.assertIn("name: security-specialist-trainer", match.group(1))
        self.assertNotIn("TODO", text)

    def test_エージェントメタデータに技能呼出しが明記される(self) -> None:
        text = (self.skill / "agents" / "openai.yaml").read_text(encoding="utf-8")
        self.assertIn("display_name:", text)
        self.assertIn("short_description:", text)
        self.assertIn("$security-specialist-trainer", text)

    def test_暗記語句の手順と形式が文書化される(self) -> None:
        skill_text = self.question_workflow.read_text(encoding="utf-8")
        session_text = (self.root / "参照資料" / "セッション形式.md").read_text(encoding="utf-8")
        scoring_text = (self.root / "参照資料" / "採点・理解度・復習ルール.md").read_text(encoding="utf-8")
        self.assertIn("--mode term-recall", skill_text)
        self.assertIn("指定がなければ10問", skill_text)
        self.assertIn("- Mode: term-recall", session_text)
        self.assertIn("Recall Score", scoring_text)
        self.assertIn("Explanation Score", scoring_text)
        self.assertIn("学習記録/理解・応用問題/YYYY-MM-DD.md", session_text)
        self.assertIn("学習記録/暗記語句問題/YYYY-MM-DD.md", session_text)
        self.assertIn("--mode standard", session_text)
        self.assertIn("--mode term-recall", session_text)
        self.assertIn("1〜30問", session_text)

    def test_未解答一覧を問題作成と採点の後に更新する(self) -> None:
        script_text = (self.skill / "scripts" / "study_helper.py").read_text(
            encoding="utf-8"
        )
        skill_text = self.question_workflow.read_text(encoding="utf-8")
        session_text = (self.root / "参照資料" / "セッション形式.md").read_text(
            encoding="utf-8"
        )
        self.assertIn('subparsers.add_parser(\n        "unanswered"', script_text)
        self.assertIn("学習記録/未解答一覧.md", skill_text)
        self.assertIn("study_helper.py unanswered --root .", skill_text)
        self.assertIn("study_helper.py unanswered --root .", session_text)

    def test_未復習一覧を問題作成と採点の後に更新する(self) -> None:
        script_text = (self.skill / "scripts" / "study_helper.py").read_text(
            encoding="utf-8"
        )
        skill_text = self.question_workflow.read_text(encoding="utf-8")
        session_text = (self.root / "参照資料" / "セッション形式.md").read_text(
            encoding="utf-8"
        )
        self.assertIn('subparsers.add_parser(\n        "unreviewed"', script_text)
        self.assertIn("復習用/未復習一覧.md", skill_text)
        self.assertIn("study_helper.py unreviewed --root .", skill_text)
        self.assertIn("study_helper.py unreviewed --root .", session_text)

    def test_カタログ拡張は明示依頼時だけ行う(self) -> None:
        skill_text = (self.skill / "SKILL.md").read_text(encoding="utf-8")
        catalog_text = self.catalog_expansion.read_text(encoding="utf-8")
        logic_text = (self.root / "docs" / "出題・採点ロジック.md").read_text(
            encoding="utf-8"
        )
        taxonomy_text = (self.root / "参照資料" / "出題分類と概念カタログ.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("only when the user explicitly requests catalog expansion", skill_text)
        self.assertIn("通常の問題作成・採点・復習では読まない", catalog_text)
        self.assertIn("根拠がある語句だけ", catalog_text)
        self.assertIn("自動では実行しません", logic_text)
        self.assertIn("明示した場合だけ行う", taxonomy_text)

    def test_ローカル過去問は明示指示時だけ参照する(self) -> None:
        skill_text = (self.skill / "SKILL.md").read_text(encoding="utf-8")
        catalog_text = self.catalog_expansion.read_text(encoding="utf-8")
        gitignore_text = (self.root / ".gitignore").read_text(encoding="utf-8")
        structure_text = (self.root / "docs" / "リポジトリ構成.md").read_text(
            encoding="utf-8"
        )
        index_text = (self.root / "参照資料" / "過去問分析索引.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("do **not** inspect past-question materials", skill_text)
        self.assertIn("利用者が明示的に", catalog_text)
        self.assertIn("During routine generation", skill_text)
        self.assertIn("/過去問/", gitignore_text)
        self.assertIn("利用者がカタログ拡張", structure_text)
        self.assertIn("日々の出題ではPDFも索引も読まず", structure_text)
        self.assertIn("根拠年度", index_text)

    def test_わかりませんは回答済みとして採点するルールが文書化される(self) -> None:
        skill_text = (self.skill / "SKILL.md").read_text(encoding="utf-8")
        workflow_text = self.grading_workflow.read_text(encoding="utf-8")
        session_text = (self.root / "参照資料" / "セッション形式.md").read_text(
            encoding="utf-8"
        )
        scoring_text = (self.root / "参照資料" / "採点・理解度・復習ルール.md").read_text(
            encoding="utf-8"
        )
        usage_text = (self.root / "docs" / "使い方.md").read_text(encoding="utf-8")
        for text in (workflow_text, session_text, scoring_text, usage_text):
            with self.subTest(text=text[:30]):
                self.assertIn("わかりません", text)
                self.assertIn("0 / 100", text)
        self.assertIn("採点前チェック", skill_text)
        self.assertIn("理解・応用問題", session_text)
        self.assertIn("理解・応用問題", scoring_text)
        self.assertIn("理解・応用問題", usage_text)

    def test_設問外の補足不足で減点しない採点規則が文書化される(self) -> None:
        workflow_text = self.grading_workflow.read_text(encoding="utf-8")
        scoring_text = (self.root / "参照資料" / "採点・理解度・復習ルール.md").read_text(
            encoding="utf-8"
        )
        logic_text = (self.root / "docs" / "出題・採点ロジック.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("問題文が求めた観点だけ", workflow_text)
        self.assertIn("未要求の補足知識を理由に減点しない", workflow_text)
        self.assertIn("問題文で明示していない観点", scoring_text)
        self.assertIn("満点とし", scoring_text)
        self.assertIn("補足知識がないことを理由に部分点へ下げません", logic_text)

    def test_採点手順は現在と旧セッション保存先を全て明記する(self) -> None:
        grade_section = self.grading_workflow.read_text(encoding="utf-8")
        for session_path in (
            "学習記録/理解・応用問題/",
            "学習記録/暗記語句問題/",
            "学習記録/standard/",
            "学習記録/term-recall/",
            "学習記録/YYYY-MM-DD.md",
        ):
            with self.subTest(session_path=session_path):
                self.assertIn(session_path, grade_section)
        self.assertIn("Track A/Bの配分", grade_section)
        self.assertIn("問題数", grade_section)
        self.assertIn("Q1からの連番", grade_section)

    def test_採点対象は回答内容で選び全件を時系列で処理する(self) -> None:
        skill_text = self.grading_workflow.read_text(encoding="utf-8")
        session_text = (self.root / "参照資料" / "セッション形式.md").read_text(
            encoding="utf-8"
        )
        usage_text = (self.root / "docs" / "使い方.md").read_text(encoding="utf-8")
        logic_text = (self.root / "docs" / "出題・採点ロジック.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("Git差分、コミット履歴で絞らない", skill_text)
        self.assertIn("候補全件", skill_text)
        self.assertIn("日付、Session番号の昇順", skill_text)
        self.assertIn("全回答が記入済みで、かつ採点とprogress更新が完了していないSessionをすべて", session_text)
        self.assertIn("Status`の値で対象を選ばない", session_text)
        self.assertIn("コミット履歴、作業ツリーの状態を判定材料にしない", session_text)
        self.assertIn("空欄を含むSessionは飛ばされ", usage_text)
        self.assertIn("新しい未回答Sessionが古い回答済みSessionの採点を妨げません", logic_text)

    def test_時系列が逆転した進捗を再構築できる(self) -> None:
        script_text = (self.skill / "scripts" / "study_helper.py").read_text(
            encoding="utf-8"
        )
        skill_text = self.grading_workflow.read_text(encoding="utf-8")
        session_text = (self.root / "参照資料" / "セッション形式.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("def rebuild_progress", script_text)
        self.assertIn('subparsers.add_parser(\n        "rebuild"', script_text)
        self.assertIn("study_helper.py rebuild --root .", skill_text)
        self.assertIn("study_helper.py rebuild --root .", session_text)

    def test_自動テストが全てのプッシュで実行される(self) -> None:
        workflow = (
            self.root / ".github" / "workflows" / "python-tests.yml"
        ).read_text(encoding="utf-8")
        self.assertRegex(workflow, r"(?m)^on:\n  push:\s*$")
        self.assertNotIn("branches:", workflow)
        self.assertIn("python -m unittest discover", workflow)
        self.assertIn("-s skills/security-specialist-trainer/tests", workflow)

    def test_テスト名は日本語で記述される(self) -> None:
        japanese = re.compile(r"[ぁ-んァ-ヶ一-龠々]")
        english_word = re.compile(r"[A-Za-z]{2,}")

        def 日本語主体の名前(name: str) -> bool:
            return japanese.search(name) is not None and english_word.search(name) is None

        def 検査対象の名前(source: str) -> tuple[list[str], list[str]]:
            tree = ast.parse(source)
            class_names = [
                node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)
            ]
            method_names = [
                node.name
                for node in ast.walk(tree)
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name.startswith("test_")
            ]
            return class_names, method_names

        self.assertTrue(日本語主体の名前("科目Bの比率を検証する"))
        self.assertFalse(日本語主体の名前("should_work_日本語"))
        bypass_classes, bypass_methods = 検査対象の名前(
            """class should_work_日本語(基底テスト):
    def test_should_work_日本語(self, value=None):
        pass
"""
        )
        self.assertEqual(["should_work_日本語"], bypass_classes)
        self.assertEqual(["test_should_work_日本語"], bypass_methods)
        self.assertFalse(all(日本語主体の名前(name) for name in bypass_classes))
        self.assertFalse(
            all(
                日本語主体の名前(name.removeprefix("test_"))
                for name in bypass_methods
            )
        )

        for path in sorted((self.skill / "tests").glob("test_*.py")):
            text = path.read_text(encoding="utf-8")
            class_names, method_names = 検査対象の名前(text)
            with self.subTest(path=path.name):
                self.assertTrue(class_names)
                self.assertTrue(method_names)
                self.assertTrue(
                    日本語主体の名前(path.stem.removeprefix("test_")), path.name
                )
                self.assertTrue(
                    all(日本語主体の名前(name) for name in class_names), path.name
                )
                self.assertTrue(
                    all(
                        日本語主体の名前(name.removeprefix("test_"))
                        for name in method_names
                    ),
                    path.name,
                )

        agents = (self.root / "AGENTS.md").read_text(encoding="utf-8")
        development_guide = (
            self.root / "docs" / "開発・テスト.md"
        ).read_text(encoding="utf-8")
        self.assertIn("test file names", agents)
        self.assertIn("テストファイル名", development_guide)


if __name__ == "__main__":
    unittest.main()
