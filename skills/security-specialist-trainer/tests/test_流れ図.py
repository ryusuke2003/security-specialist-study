"""学習用図の構造契約を検査する。Mermaid構文・技術内容・表示は別途検証する。"""
from __future__ import annotations

import re
import unittest
from pathlib import Path
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[3]
DIAGRAMS = ROOT / "復習用" / "流れ図"
BLOCK = re.compile(r"^```mermaid[^\n]*\n(.*?)^```[ \t]*$", re.MULTILINE | re.DOTALL)
DECLARATION = re.compile(r"^\s*(?:participant|actor)\s+(\w+)\s+as\s+(.+)$", re.MULTILINE)
MESSAGE = re.compile(r"^\s*(\w+)\s*(?:--?>>|--?>)\s*(\w+)\s*:\s*(.+)$", re.MULTILINE)
NODE = re.compile(r'^\s*(\w+)\s*[\[{]"([^"\n]+)"[\]}]', re.MULTILINE)


def sequence_errors(block: str) -> list[str]:
    """この資料で使う基本記法を検査する。汎用Mermaidパーサではない。"""
    errors: list[str] = []
    declarations = DECLARATION.findall(block)
    ids = [identifier for identifier, _ in declarations]
    if not ids:
        errors.append("明示的な登場人物がない")
    if len(ids) != len(set(ids)):
        errors.append("登場人物IDが重複している")
    if not re.search(r"^\s*autonumber\s*$", block, re.MULTILINE):
        errors.append("操作番号がない")
    messages = MESSAGE.findall(block)
    if not messages:
        errors.append("対応する操作矢印がない")
    for source, target, label in messages:
        if source not in ids or target not in ids:
            errors.append(f"未宣言の主体: {source} -> {target}")
        if "が" not in label and "は" not in label:
            errors.append(f"主語を確認できない操作: {label}")
    return errors


class 流れ図テスト(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.documents = {path: path.read_text(encoding="utf-8") for path in sorted(DIAGRAMS.glob("*.md"))}

    def test_全資料に前提と保持者と注意点と根拠がある(self) -> None:
        self.assertTrue(self.documents)
        for path, text in self.documents.items():
            with self.subTest(file=path.name):
                for heading in ("前提と登場人物", "処理後に残るもの", "注意点", "参照資料"):
                    self.assertRegex(text, rf"(?m)^## {re.escape(heading)}$")
                self.assertRegex(text.split("## 参照資料", 1)[1], r"\]\(https://[^)]+\)")
                self.assertTrue(BLOCK.findall(text))
                self.assertEqual(text.count("```mermaid"), len(BLOCK.findall(text)))

    def test_全シーケンス図で登場人物と操作の主語と番号が明示される(self) -> None:
        for path, text in self.documents.items():
            for index, block in enumerate(BLOCK.findall(text), 1):
                if block.lstrip().startswith("sequenceDiagram"):
                    with self.subTest(file=path.name, diagram=index):
                        self.assertEqual([], sequence_errors(block))

    def test_フローチャートの処理と判断に主語がある(self) -> None:
        for path, text in self.documents.items():
            for index, block in enumerate(BLOCK.findall(text), 1):
                if block.lstrip().startswith("flowchart"):
                    with self.subTest(file=path.name, diagram=index):
                        nodes = NODE.findall(block)
                        self.assertTrue(nodes)
                        for _, label in nodes:
                            self.assertRegex(label, "が|は")

    def test_資料間リンクとガイドの網羅性を保つ(self) -> None:
        guide_path = ROOT / "docs" / "流れ図ガイド.md"
        guide = guide_path.read_text(encoding="utf-8")
        targets: set[Path] = set()
        for path, text in [*self.documents.items(), (guide_path, guide)]:
            for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", text):
                parts = urlsplit(target)
                if parts.scheme or not parts.path or not parts.path.endswith(".md"):
                    continue
                resolved = (path.parent / unquote(parts.path)).resolve()
                with self.subTest(file=path.name, link=target):
                    self.assertTrue(resolved.is_file())
                if path == guide_path:
                    targets.add(resolved)
        self.assertEqual(set(self.documents), targets.intersection(self.documents))

    def test_検査が未宣言の主体と主語なしの処理を検出する(self) -> None:
        invalid = "sequenceDiagram\n    participant A as ブラウザ\n    A->>B: 認証\n"
        errors = sequence_errors(invalid)
        self.assertEqual(3, len(errors))
        self.assertTrue(any("未宣言" in error for error in errors))
        self.assertTrue(any("主語" in error for error in errors))
        self.assertTrue(any("番号" in error for error in errors))

    def test_検査が明示的な通信と自己処理を受け入れる(self) -> None:
        valid = "\n".join((
            "sequenceDiagram", "    autonumber",
            "    participant A as ブラウザ", "    participant B as サーバ",
            "    A->>B: ブラウザがコードを送る",
            "    B->>B: サーバがコードを保存済みの値と照合する",
        ))
        self.assertEqual([], sequence_errors(valid))

    def test_検査が登場人物の重複を検出する(self) -> None:
        invalid = "\n".join((
            "sequenceDiagram", "    autonumber", "    participant A as ブラウザ",
            "    participant A as サーバ", "    A->>A: サーバが応答を作る",
        ))
        self.assertEqual(["登場人物IDが重複している"], sequence_errors(invalid))


if __name__ == "__main__":
    unittest.main()
