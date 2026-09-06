"""概要図の原稿・生成物・表示リンクを標準ライブラリで検査する。"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import re
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / 'skills/security-specialist-trainer/scripts/render_overviews.py'
SPEC = importlib.util.spec_from_file_location('diagram_overviews', SCRIPT)
assert SPEC and SPEC.loader
renderer = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = renderer
SPEC.loader.exec_module(renderer)
NS = '{http://www.w3.org/2000/svg}'


def sample(row: str = '| 検証 | 確認 | サーバ | — | 保存した公開鍵で署名を検証する。 |') -> str:
    return '\n'.join((
        '# 検証の図', '', renderer.START, '要点: 誰が何を確認するか。',
        '補足: 不正なら停止する。', renderer.HEADER,
        '|---|---|---|---|---|', row, renderer.END,
    ))


class 概要画像テスト(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.folder = ROOT / '復習用/流れ図'
        cls.documents = {p: p.read_text(encoding='utf-8') for p in cls.folder.glob('*.md')}

    def test_全資料の概要画像が原稿と一致する(self) -> None:
        expected = renderer.expected_images(ROOT)
        self.assertTrue(expected)
        self.assertEqual(set(expected), set((self.folder / '画像').glob('*.svg')))
        for path, image in expected.items():
            with self.subTest(file=path.name):
                self.assertEqual(image, path.read_text(encoding='utf-8'))

    def test_全資料で主図とテキストと折り畳みの詳細へ到達できる(self) -> None:
        for path, text in self.documents.items():
            with self.subTest(file=path.name):
                overview = renderer.read_overview(text)
                images = re.findall(r'!\[([^\]]+)\]\(([^)]+\.svg)\)', text)
                self.assertEqual(1, len(images))
                alt, target = images[0]
                self.assertEqual(overview.focus, alt)
                self.assertEqual(self.folder / '画像' / (path.stem + '.svg'), path.parent / unquote(target))
                self.assertEqual(2, text.count('<details>'))
                self.assertEqual(2, text.count('</details>'))
                source_panel = re.search(r'<details>\s*<summary>図の内容を文字で読む</summary>(.*?)</details>', text, re.S)
                detail_panel = re.search(r'<details>\s*<summary>詳しい手順・分岐を開く（Mermaid）</summary>(.*?)</details>', text, re.S)
                self.assertIsNotNone(source_panel)
                self.assertIsNotNone(detail_panel)
                assert source_panel and detail_panel
                self.assertTrue(renderer.START in source_panel.group(1))
                self.assertEqual(text.count('```mermaid'), detail_panel.group(1).count('```mermaid'))
                self.assertGreater(text.count('```mermaid'), 0)
                self.assertLess(text.index('!['), text.index('<details>'))
                self.assertGreater(text.index('## 処理後に残るもの'), detail_panel.end())

    def test_画像は説明付きの静的な図形と文字だけで構成する(self) -> None:
        allowed = {'svg', 'title', 'desc', 'rect', 'g', 'text', 'circle', 'path'}
        for path, image in renderer.expected_images(ROOT).items():
            with self.subTest(file=path.name):
                svg = ET.fromstring(image)
                self.assertEqual('800', svg.attrib['width'])
                self.assertEqual('img', svg.attrib['role'])
                self.assertTrue(svg.find(NS + 'title').text)
                self.assertTrue(svg.find(NS + 'desc').text)
                for element in svg.iter():
                    self.assertTrue(element.tag.startswith(NS))
                    self.assertTrue(element.tag.removeprefix(NS) in allowed)
                    self.assertFalse(any(key.lower().startswith('on') or key.endswith('href') for key in element.attrib))
                    self.assertFalse(any('url(' in value.lower() for value in element.attrib.values()))

    def test_主体や表の列が欠けた原稿を拒否する(self) -> None:
        for row in (
            '| 検証 | 確認 | | — | 本文 |',
            '| 検証 | 確認 | — | — | 本文 |',
            '| 検証 | 確認 | サーバ | — |',
            '| 検証 | 未知の種類 | サーバ | — | 本文 |',
            '| 検証 | 確認 | サーバ | — | 本文',
        ):
            with self.subTest(row=row), self.assertRaises(ValueError):
                renderer.read_overview(sample(row))

    def test_内部処理の架空の送信先と受渡しの欠損を拒否する(self) -> None:
        for kind, actor, target in (('内部', 'サーバ', 'ブラウザ'), ('確認', 'サーバ', 'サーバ'), ('送信', 'サーバ', '—'), ('交換', 'サーバ', 'サーバ'), ('並行', '担当者', '—')):
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                renderer.read_overview(sample(f'| 段階 | {kind} | {actor} | {target} | 内容 |'))

    def test_原稿マーカーや要点が重複したら拒否する(self) -> None:
        for text in (sample() + '\n' + renderer.START, sample().replace(renderer.END, ''), sample().replace('要点: 誰が何を確認するか。', '要点: 一つ目\n要点: 二つ目')):
            with self.subTest(text=text), self.assertRaises(ValueError):
                renderer.read_overview(text)

    def test_原稿中の特殊文字を図形やスクリプトにしない(self) -> None:
        source = sample('| 検証 | 確認 | A<& | — | <script>alert(1)</script> & "値"を検証する。 |')
        image = renderer.render_svg(renderer.read_overview(source))
        svg = ET.fromstring(image)
        self.assertFalse(svg.findall('.//' + NS + 'script'))
        self.assertTrue('<script>alert(1)</script>' in ''.join(svg.itertext()))

    def test_確認コマンドは書き込まず原稿とのずれを検出する(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            folder = root / '復習用/流れ図'
            folder.mkdir(parents=True)
            (folder / '例.md').write_text(sample(), encoding='utf-8')
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(2, renderer.main(['--root', str(root), '--check']))
                self.assertFalse((folder / '画像').exists())
                self.assertEqual(0, renderer.main(['--root', str(root)]))
                before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in root.rglob('*') if p.is_file()}
                self.assertEqual(0, renderer.main(['--root', str(root), '--check']))
                self.assertEqual(before, {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in root.rglob('*') if p.is_file()})
                image = folder / '画像/例.svg'
                image.write_text('stale', encoding='utf-8')
                self.assertEqual(2, renderer.main(['--root', str(root), '--check']))
                self.assertEqual('stale', image.read_text())

    def test_孤立画像を黙って削除しない(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            folder = root / '復習用/流れ図'
            (folder / '画像').mkdir(parents=True)
            (folder / '例.md').write_text(sample(), encoding='utf-8')
            orphan = folder / '画像/古い図.svg'
            orphan.write_text('keep', encoding='utf-8')
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(2, renderer.main(['--root', str(root)]))
            self.assertEqual('keep', orphan.read_text())

    def test_折り返しが長い英字や日本語を欠落させない(self) -> None:
        for text in ('DNSKEY-RRset-' * 20, '公開鍵と秘密鍵を混同せずに検証する。' * 20):
            lines = renderer.wrap(text, 55)
            self.assertEqual(text, ''.join(lines))
            self.assertTrue(all(renderer.units(line) <= 55 for line in lines))

    def test_概要図を巨大な手順書へ膨らませない(self) -> None:
        rows = '\n'.join('| 検証 | 確認 | サーバ | — | 本文 |' for _ in range(13))
        with self.assertRaises(ValueError):
            renderer.read_overview(sample(rows))

    def test_存在しない学習ルートを成功扱いしない(self) -> None:
        with tempfile.TemporaryDirectory() as temporary, contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(2, renderer.main(['--root', temporary, '--check']))


if __name__ == '__main__':
    unittest.main()
