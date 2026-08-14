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
            self.root / "progress" / "terms.md",
            self.root / "progress" / "domains.md",
            self.root / "progress" / "history.md",
            self.root / "references" / "taxonomy.md",
            self.root / "references" / "scoring-rules.md",
            self.root / "references" / "session-format.md",
        ]
        self.assertEqual([], [str(path) for path in expected if not path.is_file()])
        self.assertTrue((self.root / "sessions" / "理解・応用問題").is_dir())
        self.assertTrue((self.root / "sessions" / "暗記語句問題").is_dir())

    def test_復習用の流れ図を専用ディレクトリへ保存する(self) -> None:
        review_dir = self.root / "復習用"
        diagram_dir = review_dir / "流れ図"
        self.assertTrue((review_dir / "学んだこと.md").is_file())
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
        self.assertIn("復習用/流れ図/<topic>.md", skill_text)

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
        skill_text = (self.skill / "SKILL.md").read_text(encoding="utf-8")
        session_text = (self.root / "references" / "session-format.md").read_text(encoding="utf-8")
        scoring_text = (self.root / "references" / "scoring-rules.md").read_text(encoding="utf-8")
        self.assertIn("--mode term-recall", skill_text)
        self.assertIn("create exactly 10 questions", skill_text)
        self.assertIn("- Mode: term-recall", session_text)
        self.assertIn("Recall Score", scoring_text)
        self.assertIn("Explanation Score", scoring_text)
        self.assertIn("sessions/理解・応用問題/YYYY-MM-DD.md", session_text)
        self.assertIn("sessions/暗記語句問題/YYYY-MM-DD.md", session_text)
        self.assertIn("--mode standard", session_text)
        self.assertIn("--mode term-recall", session_text)
        self.assertIn("1〜30問", session_text)

    def test_暗記語句を一周した後にカタログを拡張する(self) -> None:
        skill_text = (self.skill / "SKILL.md").read_text(encoding="utf-8")
        logic_text = (self.root / "docs" / "出題・採点ロジック.md").read_text(
            encoding="utf-8"
        )
        taxonomy_text = (self.root / "references" / "taxonomy.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("every initial catalog term has `Recall Attempts >= 1`", skill_text)
        self.assertIn("80〜120 previously absent high-priority terms", skill_text)
        self.assertIn("thereafter append 20〜40 terms", skill_text)
        self.assertIn("初回の151語すべてに`Recall Attempts`が1回以上", logic_text)
        self.assertIn("全151語に暗記語句問題として1回以上回答した後", taxonomy_text)

    def test_ローカル過去問を版管理外で優先参照する(self) -> None:
        skill_text = (self.skill / "SKILL.md").read_text(encoding="utf-8")
        gitignore_text = (self.root / ".gitignore").read_text(encoding="utf-8")
        structure_text = (self.root / "docs" / "リポジトリ構成.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("every file under the local `過去問/` directory", skill_text)
        self.assertIn("local IPA problem booklets", skill_text)
        self.assertIn("/過去問/", gitignore_text)
        self.assertIn("カタログ拡張時は、このディレクトリにある資料をオンライン資料より先に参照", structure_text)
        self.assertIn("以後追加する未追跡ファイルはリモートへ送られません", structure_text)

    def test_わかりませんは回答済みとして採点するルールが文書化される(self) -> None:
        skill_text = (self.skill / "SKILL.md").read_text(encoding="utf-8")
        session_text = (self.root / "references" / "session-format.md").read_text(
            encoding="utf-8"
        )
        scoring_text = (self.root / "references" / "scoring-rules.md").read_text(
            encoding="utf-8"
        )
        usage_text = (self.root / "docs" / "使い方.md").read_text(encoding="utf-8")
        for text in (skill_text, session_text, scoring_text, usage_text):
            with self.subTest(text=text[:30]):
                self.assertIn("わかりません", text)
                self.assertIn("0 / 100", text)
        self.assertIn("normal (understanding/application)", skill_text)
        self.assertIn("理解・応用問題", session_text)
        self.assertIn("理解・応用問題", scoring_text)
        self.assertIn("理解・応用問題", usage_text)

    def test_採点手順は現在と旧セッション保存先を全て明記する(self) -> None:
        skill_text = (self.skill / "SKILL.md").read_text(encoding="utf-8")
        grade_section_match = re.search(
            r"^## Grade a session\n(?P<body>.*?)(?=^## |\Z)",
            skill_text,
            flags=re.MULTILINE | re.DOTALL,
        )
        self.assertIsNotNone(grade_section_match)
        assert grade_section_match
        grade_section = grade_section_match.group("body")
        for session_path in (
            "sessions/理解・応用問題/",
            "sessions/暗記語句問題/",
            "sessions/standard/",
            "sessions/term-recall/",
            "sessions/YYYY-MM-DD.md",
        ):
            with self.subTest(session_path=session_path):
                self.assertIn(session_path, grade_section)
        self.assertIn(
            "the literal `A` or `B` (including the literal `A/B`)",
            grade_section,
        )
        self.assertIn("exactly one integer `Question Count` from 1 to 30", grade_section)
        self.assertIn("unique and consecutive from `Q1`", grade_section)

    def test_採点対象は回答内容で選び全件を時系列で処理する(self) -> None:
        skill_text = (self.skill / "SKILL.md").read_text(encoding="utf-8")
        session_text = (self.root / "references" / "session-format.md").read_text(
            encoding="utf-8"
        )
        usage_text = (self.root / "docs" / "使い方.md").read_text(encoding="utf-8")
        logic_text = (self.root / "docs" / "出題・採点ロジック.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("Do **not** select by `Status`", skill_text)
        self.assertIn("select **all** grading candidates", skill_text)
        self.assertIn("chronological order", skill_text)
        self.assertIn("全回答が記入済みで、かつ採点とprogress更新が完了していないSessionをすべて", session_text)
        self.assertIn("Status`の値で対象を選ばない", session_text)
        self.assertIn("空欄を含むSessionは飛ばされ", usage_text)
        self.assertIn("新しい未回答Sessionが古い回答済みSessionの採点を妨げません", logic_text)

    def test_時系列が逆転した進捗を再構築できる(self) -> None:
        script_text = (self.skill / "scripts" / "study_helper.py").read_text(
            encoding="utf-8"
        )
        skill_text = (self.skill / "SKILL.md").read_text(encoding="utf-8")
        session_text = (self.root / "references" / "session-format.md").read_text(
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
