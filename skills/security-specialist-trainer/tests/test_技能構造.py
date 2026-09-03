from __future__ import annotations

import ast
import builtins
import importlib.util
import re
import symtable
import sys
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "study_helper.py"
SPEC = importlib.util.spec_from_file_location("study_helper_structure", SCRIPT)
assert SPEC and SPEC.loader
study_helper = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = study_helper
SPEC.loader.exec_module(study_helper)


class 技能構造テスト(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.skill = Path(__file__).resolve().parents[1]
        cls.root = cls.skill.parents[1]
        cls.grading_workflow = cls.skill / "references" / "採点ワークフロー.md"
        cls.catalog_expansion = cls.skill / "references" / "カタログ拡張.md"
        cls.catalog_lookup = cls.skill / "references" / "カタログ部分参照.md"
        cls.common_start = cls.skill / "references" / "共通開始処理.md"
        cls.question_workflow = cls.skill / "references" / "問題作成ワークフロー.md"
        cls.selection_rules = cls.skill / "references" / "出題選定ルール.md"

    def test_必須ファイルとディレクトリが揃う(self) -> None:
        files = [
            self.root / "AGENTS.md",
            self.root / ".github" / "workflows" / "python-tests.yml",
            self.skill / "SKILL.md",
            self.skill / "agents" / "openai.yaml",
            *(self.skill / "scripts" / "trainer" / name for name in (
                "__init__.py", "common.py", "session_parser.py", "indexes.py",
                "progress.py", "planner.py", "cli.py",
            )),
            *(self.root / path for path in (
                "README.md", "docs/使い方.md", "docs/リポジトリ構成.md",
                "docs/出題・採点ロジック.md", "docs/開発・テスト.md",
                "進捗/語句別理解度.md", "進捗/分野別理解度.md", "進捗/学習履歴.md",
                "学習記録/未解答一覧.md", "復習用/未復習一覧.md",
                "参照資料/出題分類と概念カタログ.md", "参照資料/採点・理解度・復習ルール.md",
                "参照資料/セッション形式.md", "参照資料/通常・暗記語句Session形式.md",
                "参照資料/10分復習Session形式.md",
            )),
            self.grading_workflow,
            self.catalog_expansion,
            self.catalog_lookup,
            self.common_start,
            self.question_workflow,
            self.selection_rules,
        ]
        directories = [
            self.root / "学習記録" / "理解・応用問題",
            self.root / "学習記録" / "暗記語句問題",
            self.root / "復習用" / "学んだこと",
            self.root / "復習用" / "明日復習するべきところ",
            self.root / "復習用" / "流れ図",
        ]
        self.assertEqual([], [str(path) for path in files if not path.is_file()])
        self.assertEqual([], [str(path) for path in directories if not path.is_dir()])

    def test_復習資料は用途別に保存される(self) -> None:
        review = self.root / "復習用"
        diagrams = sorted((review / "流れ図").glob("*.md"))
        self.assertTrue(diagrams)
        self.assertTrue(all("```mermaid" in path.read_text(encoding="utf-8") for path in diagrams))
        self.assertFalse(any(
            "```mermaid" in path.read_text(encoding="utf-8")
            for path in review.glob("*.md")
        ))
        self.assertFalse((review / "学んだこと.md").exists())

    def test_マークダウンの相対リンク先が存在する(self) -> None:
        documents = [self.root / "README.md", *(self.root / "docs").glob("*.md")]
        documents += [self.skill / "SKILL.md", *(self.skill / "references").glob("*.md")]
        missing: list[str] = []
        for document in documents:
            text = document.read_text(encoding="utf-8")
            for target in re.findall(r"\[[^]]+\]\(([^)]+\.md(?:#[^)]+)?)\)", text):
                relative = target.split("#", 1)[0]
                if relative.startswith(("http://", "https://", "/")) or "<" in relative:
                    continue
                if not (document.parent / relative).resolve().is_file():
                    missing.append(f"{document.relative_to(self.root)} -> {target}")
        self.assertEqual([], missing)

    def test_技能のフロントマターとメタデータが有効(self) -> None:
        text = (self.skill / "SKILL.md").read_text(encoding="utf-8")
        match = re.match(r"^---\n(.*?)\n---", text, flags=re.DOTALL)
        self.assertIsNotNone(match)
        assert match
        fields = [line.split(":", 1)[0] for line in match.group(1).splitlines() if ":" in line]
        self.assertEqual(["name", "description"], fields)
        self.assertRegex(match.group(1), r"(?m)^name:\s*security-specialist-trainer$")
        self.assertNotRegex(text, r"\bTODO\b")

        metadata = (self.skill / "agents" / "openai.yaml").read_text(encoding="utf-8")
        self.assertRegex(metadata, r"(?m)^\s*display_name:\s*\S")
        self.assertRegex(metadata, r"(?m)^\s*short_description:\s*\S")
        self.assertRegex(metadata, r"\$security-specialist-trainer\b")

    def test_文書化された補助コマンドを解析できる(self) -> None:
        documents = [
            self.skill / "SKILL.md",
            *(self.skill / "references").glob("*.md"),
            *(self.root / "docs").glob("*.md"),
        ]
        found: set[str] = set()
        failures: list[str] = []
        required_arguments = {
            "record": ["--date", "2026-08-22", "--session", "1"],
            "validate-session": ["--date", "2026-08-22", "--session", "1"],
        }
        for document in documents:
            for command in re.findall(
                r"(?:skills/security-specialist-trainer/scripts/)?study_helper\.py\s+([a-z][a-z-]*)",
                document.read_text(encoding="utf-8"),
            ):
                found.add(command)
                try:
                    parsed = study_helper.parse_args([command, *required_arguments.get(command, [])])
                except SystemExit as error:
                    failures.append(f"{document.relative_to(self.root)}: {command} ({error.code})")
                else:
                    if parsed.command != command:
                        failures.append(f"{document.relative_to(self.root)}: {command} -> {parsed.command}")
        expected = {
            "briefing", "record", "validate-session", "rebuild", "unanswered",
            "unreviewed", "activity-log", "grading-candidates", "quick-review-status",
            "study-date",
        }
        self.assertLessEqual(expected, found)
        self.assertEqual([], failures)

    def test_公開インターフェースは明示的に固定される(self) -> None:
        scripts = self.skill / "scripts"
        package_spec = importlib.util.spec_from_file_location(
            "trainer_public_api",
            scripts / "trainer" / "__init__.py",
            submodule_search_locations=[str(scripts / "trainer")],
        )
        assert package_spec and package_spec.loader
        package = importlib.util.module_from_spec(package_spec)
        sys.modules[package_spec.name] = package
        package_spec.loader.exec_module(package)

        self.assertEqual(package.__all__, study_helper.__all__)
        self.assertEqual(len(package.__all__), len(set(package.__all__)))
        self.assertTrue(all(hasattr(package, name) for name in package.__all__))
        self.assertTrue(all(hasattr(study_helper, name) for name in package.__all__))
        self.assertFalse({"os", "re", "Path", "Optional"} & set(package.__all__))

        wildcard_imports: list[str] = []
        for path in (scripts / "study_helper.py", scripts / "trainer" / "__init__.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            if any(
                isinstance(node, ast.ImportFrom)
                and any(alias.name == "*" for alias in node.names)
                for node in ast.walk(tree)
            ):
                wildcard_imports.append(path.name)
        self.assertEqual([], wildcard_imports)

    def test_補助スクリプトは責務別モジュールに分割される(self) -> None:
        scripts = self.skill / "scripts"
        entrypoint = (scripts / "study_helper.py").read_text(encoding="utf-8")
        tree = ast.parse(entrypoint)
        self.assertFalse(any(isinstance(node, (ast.FunctionDef, ast.ClassDef)) for node in tree.body))
        self.assertLessEqual(len(entrypoint.splitlines()), 40)

        expected_functions = {
            "session_parser.py": "parse_graded_session",
            "indexes.py": "write_unreviewed_index",
            "progress.py": "record_progress",
            "planner.py": "adaptive_plan",
            "cli.py": "main",
        }
        allowed_dependencies = {
            "session_parser.py": {"common"},
            "indexes.py": {"common", "session_parser"},
            "progress.py": {"common", "session_parser", "indexes"},
            "planner.py": {"common", "session_parser", "indexes"},
            "cli.py": {"common", "session_parser", "indexes", "progress", "planner"},
        }
        failures: list[str] = []
        for filename, function_name in expected_functions.items():
            module_tree = ast.parse((scripts / "trainer" / filename).read_text(encoding="utf-8"))
            defined = {node.name for node in module_tree.body if isinstance(node, ast.FunctionDef)}
            dependencies = {
                node.module for node in module_tree.body
                if isinstance(node, ast.ImportFrom) and node.level == 1 and node.module
            }
            if function_name not in defined:
                failures.append(f"{filename}: missing {function_name}")
            unexpected = dependencies - allowed_dependencies[filename]
            if unexpected:
                failures.append(f"{filename}: unexpected dependencies {sorted(unexpected)}")
        self.assertEqual([], failures)

    def test_責務別モジュールに未解決のグローバル参照がない(self) -> None:
        failures: dict[str, set[str]] = {}
        for path in sorted((self.skill / "scripts" / "trainer").glob("*.py")):
            table = symtable.symtable(path.read_text(encoding="utf-8"), str(path), "exec")
            module_names = {symbol.get_name() for symbol in table.get_symbols()}
            unresolved: set[str] = set()
            scopes = [table]
            while scopes:
                scope = scopes.pop()
                for symbol in scope.get_symbols():
                    if (
                        scope is not table and symbol.is_referenced() and symbol.is_global()
                        and symbol.get_name() not in module_names
                        and not hasattr(builtins, symbol.get_name())
                        and symbol.get_name() != "__file__"
                    ):
                        unresolved.add(symbol.get_name())
                scopes.extend(scope.get_children())
            if unresolved:
                failures[path.name] = unresolved
        self.assertEqual({}, failures)

    def test_学習ワークフローの意思決定契約が保たれる(self) -> None:
        documents = {
            "AGENTS.md": (self.root / "AGENTS.md").read_text(encoding="utf-8"),
            "SKILL.md": (self.skill / "SKILL.md").read_text(encoding="utf-8"),
            "共通開始処理.md": self.common_start.read_text(encoding="utf-8"),
            "問題作成ワークフロー.md": self.question_workflow.read_text(encoding="utf-8"),
            "採点ワークフロー.md": self.grading_workflow.read_text(encoding="utf-8"),
            "カタログ拡張.md": self.catalog_expansion.read_text(encoding="utf-8"),
            "カタログ部分参照.md": self.catalog_lookup.read_text(encoding="utf-8"),
        }
        contracts = {
            "AGENTS.md": ("question generation or session grading",),
            "SKILL.md": ("共通開始処理.md", "only when the user explicitly requests catalog expansion"),
            "共通開始処理.md": ("午前5時", "quick-review-status"),
            "問題作成ワークフロー.md": ("出題選定ルール.md", "validate-session"),
            "採点ワークフロー.md": (
                "grading-candidates", "Git差分、コミット履歴で絞らない",
                "Score < 100", "誤答した10分復習", "unreviewed",
            ),
            "カタログ拡張.md": ("通常の問題作成・採点・復習では読まない",),
            "カタログ部分参照.md": ("直接のPrerequisitesだけ", "再帰的に広げない"),
        }
        missing = {
            name: [phrase for phrase in phrases if phrase not in documents[name]]
            for name, phrases in contracts.items()
        }
        self.assertEqual({}, {name: phrases for name, phrases in missing.items() if phrases})

    def test_自動テストは全プッシュで実行される(self) -> None:
        workflow = (self.root / ".github" / "workflows" / "python-tests.yml").read_text(encoding="utf-8")
        self.assertRegex(workflow, r"(?m)^on:\n  push:\s*$")
        self.assertNotRegex(workflow, r"(?m)^\s+branches:")
        self.assertRegex(
            workflow,
            r"python -m unittest discover\s+\\?\s*-s skills/security-specialist-trainer/tests",
        )

    def test_テスト名は日本語で記述される(self) -> None:
        japanese = re.compile(r"[ぁ-んァ-ヶ一-龠々]")
        english_word = re.compile(r"[A-Za-z]{2,}")

        def 日本語主体の名前(name: str) -> bool:
            return japanese.search(name) is not None and english_word.search(name) is None

        failures: list[str] = []
        for path in sorted((self.skill / "tests").glob("test_*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            class_names = [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
            method_names = [
                node.name.removeprefix("test_")
                for node in ast.walk(tree)
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name.startswith("test_")
            ]
            if not 日本語主体の名前(path.stem.removeprefix("test_")):
                failures.append(path.name)
            failures.extend(f"{path.name}:{name}" for name in class_names if not 日本語主体の名前(name))
            failures.extend(f"{path.name}:{name}" for name in method_names if not 日本語主体の名前(name))
        self.assertEqual([], failures)

    def test_構造テストは文言の個別照合に偏らない(self) -> None:
        tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
        assert_in_calls = [
            node for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "assertIn"
        ]
        self.assertLessEqual(len(assert_in_calls), 10)


if __name__ == "__main__":
    unittest.main()
