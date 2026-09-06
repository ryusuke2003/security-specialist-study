#!/usr/bin/env python3
"""Render the small, human-readable overview tables to deterministic SVGs.

Python standard library only; no network, fonts, browser or Mermaid dependency.
Detailed Mermaid diagrams remain available separately in the Markdown documents.
"""
from __future__ import annotations

import argparse
import html
import re
import sys
import unicodedata
from dataclasses import dataclass
from itertools import groupby
from pathlib import Path

START = "<!-- overview:start -->"
END = "<!-- overview:end -->"
HEADER = "| 段階 | 種類 | 主体 | 相手 | 内容 |"
KINDS = {"送信", "交換", "内部", "確認", "並行"}
WIDTH = 800
PALETTE = (
    ("#e0f2fe", "#075985"), ("#ede9fe", "#5b21b6"),
    ("#dcfce7", "#166534"), ("#fef3c7", "#92400e"),
)


@dataclass(frozen=True)
class Step:
    phase: str
    kind: str
    actor: str
    target: str
    text: str


@dataclass(frozen=True)
class Overview:
    title: str
    focus: str
    note: str
    steps: tuple[Step, ...]


def read_overview(text: str) -> Overview:
    """Reject incomplete sources rather than silently omitting diagram content."""
    if text.count(START) != 1 or text.count(END) != 1:
        raise ValueError("概要図の開始・終了マーカーを一組だけ置いてください")
    before, remaining = text.split(START, 1)
    source, _ = remaining.split(END, 1)
    heading = re.search(r"^# (.+)$", before, re.MULTILINE)
    focus = re.findall(r"^要点: (.+)$", source, re.MULTILINE)
    note = re.findall(r"^補足: (.+)$", source, re.MULTILINE)
    if not heading or len(focus) != 1 or len(note) != 1:
        raise ValueError("資料の見出し・要点・補足が必要です")
    rows = [line.strip() for line in source.splitlines() if line.strip().startswith("|")]
    if len(rows) < 3 or rows[0] != HEADER or not re.fullmatch(r"\|[\s:|\-]+\|", rows[1]):
        raise ValueError("概要図の表ヘッダ・区切り・操作行を確認してください")
    steps: list[Step] = []
    for row in rows[2:]:
        if not row.endswith("|"):
            raise ValueError(f"表の末尾が不正です: {row}")
        fields = [cell.strip() for cell in row[1:-1].split("|")]
        if len(fields) != 5 or not all(fields):
            raise ValueError(f"概要図の各行は空欄のない5列にしてください: {row}")
        step = Step(*fields)
        if step.kind not in KINDS:
            raise ValueError(f"未対応の種類: {step.kind}")
        if step.actor == "—":
            raise ValueError("主体を省略しないでください")
        if step.kind in {"内部", "確認"}:
            if step.target != "—":
                raise ValueError("内部処理・確認は相手を『—』とし、架空の通信にしないでください")
        elif step.target == "—" or step.actor == step.target:
            raise ValueError("受渡し・交換・並行作業は異なる主体と相手を明記してください")
        steps.append(step)
    if not 1 <= len(steps) <= 12:
        raise ValueError("概要図は1〜12操作に絞り、細部は詳細図に残してください")
    return Overview(heading.group(1), focus[0], note[0], tuple(steps))


def units(text: str) -> int:
    """Conservative width estimate: CJK/ambiguous characters occupy two units."""
    return sum(2 if unicodedata.east_asian_width(char) in "WFA" else 1 for char in text)


def wrap(text: str, limit: int) -> list[str]:
    """Prefer word boundaries; still split an unusually long protocol identifier."""
    lines: list[str] = []
    current = ""
    tokens = re.findall(r"[A-Za-z0-9_./=:+\-]+|.", text.replace("\n", " "))
    for token in tokens:
        pieces = list(token) if units(token) > limit else [token]
        for piece in pieces:
            if current and units(current + piece) > limit:
                lines.append(current.rstrip())
                current = ""
            current += piece
    if current:
        lines.append(current.rstrip())
    return lines or [""]


def render_svg(item: Overview) -> str:
    """Draw information handoffs horizontally and reading order vertically.

    Internal checks have no communication arrow. Different phases have no
    connecting line: comparison routes are not depicted as sequential execution.
    """
    elements: list[str] = []
    actor_names = dict.fromkeys(
        name for step in item.steps for name in (step.actor, step.target) if name != "—"
    )
    colors = {name: PALETTE[index % len(PALETTE)] for index, name in enumerate(actor_names)}

    def rect(x: int, y: int, width: int, height: int, fill: str, radius: int = 12) -> None:
        elements.append(f'<rect x="{x}" y="{y}" width="{width}" height="{height}" rx="{radius}" fill="{fill}"/>')

    def label(x: int, y: int, value: str, size: int = 20, fill: str = "#172e46", weight: int = 400) -> None:
        elements.append(f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" fill="{fill}">{html.escape(value)}</text>')

    def paragraph(x: int, y: int, value: str, limit: int, size: int = 22, line: int = 32, **kwargs: object) -> int:
        lines = wrap(value, limit)
        for index, value_line in enumerate(lines):
            label(x, y + index * line, value_line, size, **kwargs)
        return len(lines) * line

    def actor(x: int, y: int, name: str, width: int, height: int) -> None:
        background, foreground = colors[name]
        rect(x, y, width, height, background, 8)
        lines = wrap(name, (width - 28) // 10)
        for index, value_line in enumerate(lines):
            label(x + 14, y + 25 + index * 26, value_line, 19, foreground, 600)

    title_lines = wrap(item.title, 52)
    label(32, 34, "全体像  /  段階ごとに、上から読む", 16, "#52657b", 600)
    y = 74
    for value_line in title_lines:
        label(32, y, value_line, 28, weight=700)
        y += 38
    focus_height = len(wrap(item.focus, 62)) * 30 + 28
    rect(32, y - 9, 736, focus_height, "#e6eff8")
    paragraph(50, y + 20, item.focus, 62, 21, 30, weight=600)
    y += focus_height + 19
    label(32, y, "矢印：情報の受渡し　｜　内部・確認：通信なし　｜　並行：担当を分けて調整", 15, "#52657b")
    y += 26

    number = 0
    for phase, phase_steps in groupby(item.steps, key=lambda step: step.phase):
        steps = list(phase_steps)
        phase_lines = wrap(phase, 62)
        phase_height = len(phase_lines) * 29 + 18
        rect(72, y, 696, phase_height, "#dfe8f1", 8)
        paragraph(88, y + 29, phase, 62, 20, 29, weight=700)
        y += phase_height + 14
        for position, step in enumerate(steps, 1):
            number += 1
            handoff = step.kind in {"送信", "交換", "並行"}
            box_width = 306 if handoff else 502
            names = (step.actor, step.target) if handoff else (step.actor,)
            actor_height = max(len(wrap(name, (box_width - 28) // 10)) for name in names) * 26 + 14
            body_lines = wrap(step.text, 55)
            card_height = actor_height + len(body_lines) * 32 + 32
            rect(72, y, 696, card_height, "#ffffff")
            elements.append(f'<circle cx="36" cy="{y + 23}" r="18" fill="#203b59"/>')
            label(30 if number < 10 else 24, y + 29, str(number), 19, "#ffffff", 600)
            if position < len(steps):
                elements.append(f'<path d="M36 {y + 44}V{y + card_height + 8}" stroke="#bac9d8" stroke-width="2"/>')
            actor(88, y + 12, step.actor, box_width, actor_height)
            if handoff:
                actor(446, y + 12, step.target, 306, actor_height)
                middle = y + 12 + actor_height // 2
                if step.kind == "並行":
                    label(408, middle + 7, "+", 26, "#52657b", 700)
                else:
                    elements.append(f'<path d="M402 {middle}H435l-7 -6m7 6l-7 6" fill="none" stroke="#52657b" stroke-width="2"/>')
                    if step.kind == "交換":
                        elements.append(f'<path d="M402 {middle}l7 -6m-7 6l7 6" fill="none" stroke="#52657b" stroke-width="2"/>')
            else:
                label(632, y + 12 + actor_height // 2 + 7, step.kind + "処理" if step.kind == "内部" else "確認・判断", 17, "#52657b", 600)
            for index, value_line in enumerate(body_lines):
                label(94, y + actor_height + 40 + index * 32, value_line, 22)
            y += card_height + 14
        y += 14
    note_height = len(wrap(item.note, 62)) * 28 + 54
    rect(32, y, 736, note_height, "#fff1d7")
    label(48, y + 27, "前提・読み違えないポイント", 17, "#764a0b", 700)
    paragraph(48, y + 57, item.note, 62, 19, 28, fill="#764a0b")
    height = y + note_height + 28
    description = " ".join(
        [item.focus, item.note] + [
            f"{step.phase}。{step.kind}。{step.actor}" +
            (f"から{step.target}。" if step.kind == "送信" else
             f"と{step.target}。" if step.kind in {"交換", "並行"} else "。") + step.text
            for step in item.steps
        ]
    )
    opening = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{height}" '
        f'viewBox="0 0 {WIDTH} {height}" role="img" aria-labelledby="title desc">\n'
        f'<title id="title">{html.escape(item.title)}の全体像</title>\n'
        f'<desc id="desc">{html.escape(description)}</desc>\n'
        f'<rect width="{WIDTH}" height="{height}" fill="#f3f6fa"/>\n'
        '<g font-family="Noto Sans CJK JP, Hiragino Kaku Gothic ProN, Meiryo, sans-serif">\n'
    )
    return opening + "\n".join(elements) + "\n</g>\n</svg>\n"


def expected_images(root: Path) -> dict[Path, str]:
    directory = root / "復習用" / "流れ図"
    documents = sorted(directory.glob("*.md"))
    if not documents:
        raise ValueError(f"流れ図の資料がありません: {directory}")
    result = {}
    for document in documents:
        try:
            overview = read_overview(document.read_text(encoding="utf-8"))
        except ValueError as error:
            raise ValueError(f"{document.name}: {error}") from error
        result[directory / "画像" / f"{document.stem}.svg"] = render_svg(overview)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument("--check", action="store_true", help="Detect missing, changed or orphaned images without writing.")
    args = parser.parse_args(argv)
    try:
        root = args.root.resolve()
        images = expected_images(root)
        extras = set((root / "復習用" / "流れ図" / "画像").glob("*.svg")) - set(images)
        if extras:
            raise ValueError("対応する資料がないSVGがあります。削除は明示的に判断してください: " + ", ".join(str(path) for path in sorted(extras)))
        stale = [path for path, text in images.items() if not path.is_file() or path.read_text(encoding="utf-8") != text]
        if args.check and stale:
            raise ValueError("未生成または更新されていないSVG: " + ", ".join(path.name for path in stale))
        if not args.check:
            for path in stale:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(images[path], encoding="utf-8")
        print(f"{'Checked' if args.check else 'Rendered'} {len(images)} overview SVGs.")
        return 0
    except (ValueError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
