from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[3]
SKILL = ROOT / "skills" / "security-specialist-trainer"


class コンテキスト軽量化テスト(unittest.TestCase):
    def test_通常採点は進捗計算資料を必須読込しない(self) -> None:
        text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        grade_section = text.split("### Grade answers", 1)[1].split("### Other requests", 1)[0]
        self.assertIn("採点ワークフロー.md", grade_section)
        self.assertNotIn("採点・理解度・復習ルール.md", grade_section)
        self.assertNotIn("進捗計算仕様.md", grade_section)
        self.assertIn("record", grade_section)

    def test_採点ワークフローに数値計算式を複製しない(self) -> None:
        text = (SKILL / "references" / "採点ワークフロー.md").read_text(encoding="utf-8")
        for duplicated_formula in (
            "level_cap =",
            "alpha =",
            "priority =",
            "forgetting =",
            "0〜39ならLevel",
        ):
            with self.subTest(duplicated_formula=duplicated_formula):
                self.assertNotIn(duplicated_formula, text)
        self.assertIn("grading-candidates", text)
        self.assertIn("record", text)
        self.assertIn("unreviewed", text)

    def test_出題選定ルールはbriefingを数値判断の入口にする(self) -> None:
        text = (SKILL / "references" / "出題選定ルール.md").read_text(encoding="utf-8")
        self.assertIn("study_helper.py briefing", text)
        for duplicated_formula in ("priority =", "weakness =", "forgetting ="):
            with self.subTest(duplicated_formula=duplicated_formula):
                self.assertNotIn(duplicated_formula, text)

    def test_進捗計算仕様はPython実装を正本として案内する(self) -> None:
        path = ROOT / "参照資料" / "進捗計算仕様.md"
        self.assertTrue(path.is_file())
        text = path.read_text(encoding="utf-8")
        self.assertIn("通常の採点\n→ 読まない", text)
        self.assertIn("Python実装とテスト", text)
        for module in ("common.py", "planner.py", "progress.py"):
            self.assertIn(module, text)


if __name__ == "__main__":
    unittest.main()
