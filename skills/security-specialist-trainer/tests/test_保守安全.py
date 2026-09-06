from __future__ import annotations

import io
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from datetime import date
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "skills/security-specialist-trainer/scripts"))
from trainer import cli, common, progress, session_parser


def session(term: str = "TLS", score: int = 80, mode: str = "adaptive",
            status: str = "grading", number: int = 1) -> str:
    return (
        f"## Session {number}\n\n- Status: {status}\n- Mode: {mode}\n"
        "- Question Count: 1\n\n### Q1\n\n- Domain: Web\n"
        f"- Track: B\n- Level: 1\n- Primary Terms:\n  - `{term}`\n\n"
        "### \u56de\u7b54\n\nanswer\n\n"
        f"### \u63a1\u70b9\n\nScore: {score} / 100\n"
    )


def write_session(root: Path, day: str, content: str, quick: bool = False) -> Path:
    directory = common.QUICK_REVIEW_SESSION_DIRECTORY if quick else common.STANDARD_SESSION_DIRECTORY
    path = root / common.CURRENT_SESSIONS_DIRECTORY / directory / f"{day}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def files_snapshot(root: Path) -> dict[str, bytes]:
    return {str(path.relative_to(root)): path.read_bytes()
            for path in root.rglob("*") if path.is_file()}


def copy_study(destination: Path) -> Path:
    return Path(shutil.copytree(ROOT, destination / "study", ignore=shutil.ignore_patterns(
        ".git", "__pycache__", "*.pyc")))


class 保守安全テスト(unittest.TestCase):
    def test_不正な明示日付を今日へ置き換えない(self) -> None:
        for command in ("plan", "briefing", "quick-review-status", "activity-log", "record", "validate-session"):
            for value in ("2026-02-30", "2026-9-1", "bad", "", "2026-09-07T01:00:00"):
                with self.subTest(command=command, value=value), redirect_stderr(io.StringIO()):
                    args = [command, "--date", value]
                    if command in {"record", "validate-session"}:
                        args += ["--session", "1"]
                    with self.assertRaises(SystemExit) as error:
                        cli.parse_args(args)
                    self.assertEqual(2, error.exception.code)

    def test_日付の省略と正しい閤日を受理する(self) -> None:
        self.assertIsNone(cli.parse_args(["plan"]).date)
        self.assertEqual(date(2024, 2, 29), cli.parse_args(["plan", "--date", "2024-02-29"]).date)

    def test_存在しない学習ルートに書き込まない(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "typo"
            with redirect_stderr(io.StringIO()):
                self.assertEqual(2, cli.main(["unanswered", "--root", str(root)]))
            self.assertFalse(root.exists())

    def test_表の列数不正を黙って読み飛ばさない(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "table.md"
            for row in ("| TLS |", "| TLS | 80 | ignored |"):
                with self.subTest(row=row):
                    path.write_text("| Term | Score |\n|---|---|\n" + row + "\n", encoding="utf-8")
                    with self.assertRaises(ValueError):
                        common.read_table(path, "Term")

    def test_表の列名重複と区切り行不正を拒否する(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "table.md"
            for text in ("| Term | Score | Score |\n|---|---|---|\n|TLS|1|2|\n",
                         "| Term | Score |\n| TLS | 80 |\n"):
                with self.subTest(text=text):
                    path.write_text(text, encoding="utf-8")
                    with self.assertRaises(ValueError):
                        common.read_table(path, "Term")

    def test_新規の表とエスケープを維持する(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "table.md"
            self.assertEqual([], common.read_table(path, "Term"))
            path.write_text("| Term | Notes |\n|:---|---:|\n| TLS | a\\|b |\n", encoding="utf-8")
            self.assertEqual([{"Term": "TLS", "Notes": "a|b"}], common.read_table(path, "Term"))

    def test_理解度の重複語句を上書きしない(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / "progress" / "terms.md"
            path.parent.mkdir()
            path.write_text("| Term | Domain | Score |\n|---|---|---|\n| TLS | Web | 70 |\n| TLS | Web | 90 |\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                common.load_terms(root)

    def test_カタログの重複語句を拒否する(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / "references" / "taxonomy.md"
            path.parent.mkdir()
            path.write_text("| Term | Domain | Track | Importance | Entry Level | Diagnostic | Prerequisites | Related |\n"
                            "|---|---|---|---|---|---|---|---|\n" +
                            "|TLS|Web|B|5|2|no|||\n" * 2, encoding="utf-8")
            with self.assertRaises(ValueError):
                common.load_catalog(root)

    def test_回答中の点数表記を採点結果にしない(self) -> None:
        text = session(score=0).replace("answer", "Score: 100 / 100")
        _, questions = session_parser.parse_graded_session(text, 1)
        self.assertEqual(0, questions[0].score)

    def test_重複した点数と採点欄を拒否する(self) -> None:
        for extra in ("Score: 90 / 100\n", "### \u63a1\u70b9\n\nScore: 90 / 100\n"):
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                session_parser.parse_graded_session(session() + extra, 1)

    def test_採点欄のない点数を記録しない(self) -> None:
        with self.assertRaises(ValueError):
            session_parser.parse_graded_session(session().replace("### \u63a1\u70b9", "### other"), 1)

    def test_十分復習の点数を零点か百点に限る(self) -> None:
        with self.assertRaises(ValueError):
            session_parser.parse_graded_session(session(mode="quick-review", score=50), 1)

    def test_同一ファイルの問題集番号重複を拒否する(self) -> None:
        with self.assertRaises(ValueError):
            session_parser.session_bounds(session() + "\n" + session(), 1)

    def test_同じ問題の中心語句重複を拒否する(self) -> None:
        text = session().replace("  - `TLS`", "  - `TLS`\n  - `TLS`")
        with self.assertRaises(ValueError):
            session_parser.parse_graded_session(text, 1)

    def test_取消済み問題を直近出題へ含めない(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_session(root, "2026-09-05", session(term="active"))
            write_session(root, "2026-09-06", session(term="cancelled", status="cancelled"))
            self.assertEqual({"Web": 1}, session_parser.recent_domain_counts(root, 1))
            self.assertEqual({"active": 1}, session_parser.recent_term_counts(root, date(2026,9,6), 1))
            self.assertEqual({"active"}, set(session_parser.recent_term_sources(root, 1)))

    def test_直近の十分復習正解で誤答シグナルを解除する(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_session(root, "2026-09-05", session(mode="quick-review", score=0), quick=True)
            write_session(root, "2026-09-06", session(mode="quick-review", score=100), quick=True)
            self.assertEqual(set(), session_parser.quick_review_incorrect_terms(root))

    def test_見出しの物理順でなく日付番号順で誤答を判断する(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            # Physical heading order must not decide the latest evidence.
            write_session(root, "2026-09-06", session(mode="quick-review", score=0, number=2) + "\n" +
                          session(mode="quick-review", score=100, number=1), quick=True)
            self.assertEqual({"TLS"}, session_parser.quick_review_incorrect_terms(root))

    def test_取消済み正解で誤答シグナルを消さない(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_session(root, "2026-09-05", session(mode="quick-review", score=0), quick=True)
            write_session(root, "2026-09-06", session(mode="quick-review", score=100, status="cancelled"), quick=True)
            self.assertEqual({"TLS"}, session_parser.quick_review_incorrect_terms(root))

    def test_書込失敗で一時ファイルを残さない(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / "progress.md"
            path.write_bytes(b"original\r\n")
            with patch.object(common.os, "replace", side_effect=OSError("simulated failure")):
                with self.assertRaises(OSError):
                    common.atomic_write(path, "new")
            self.assertEqual(b"original\r\n", path.read_bytes())
            self.assertEqual([path], list(root.iterdir()))

    def test_再構築の途中失敗で全ファイルを戻す(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = copy_study(Path(temporary))
            before = files_snapshot(root)
            original = progress.update_history
            calls = []
            def fail_later(*args, **kwargs):
                calls.append(True)
                if len(calls) == 2:
                    raise OSError("simulated second-session failure")
                return original(*args, **kwargs)
            with patch.object(progress, "update_history", side_effect=fail_later):
                with self.assertRaises(OSError):
                    progress.rebuild_progress(root)
            self.assertEqual(2, len(calls))
            self.assertEqual(before, files_snapshot(root))

    def test_再構築失敗で新規出力も取り消す(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = copy_study(Path(temporary))
            for path in common.progress_directory(root).glob("*.md"):
                path.unlink()
            before = files_snapshot(root)
            with patch.object(progress, "update_history", side_effect=RuntimeError("failure")):
                with self.assertRaises(RuntimeError):
                    progress.rebuild_progress(root)
            self.assertEqual(before, files_snapshot(root))

    def test_再構築で派生一覧も更新し再実行で二重反映しない(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = copy_study(Path(temporary))
            dashboard = common.progress_directory(root) / "\u30e2\u30c1\u30d9.md"
            index = common.sessions_directory(root) / "\u672a\u89e3\u7b54\u4e00\u89a7.md"
            dashboard.write_text("stale", encoding="utf-8")
            index.write_text("stale", encoding="utf-8")
            progress.rebuild_progress(root)
            self.assertNotEqual("stale", dashboard.read_text(encoding="utf-8"))
            self.assertNotEqual("stale", index.read_text(encoding="utf-8"))
            before = files_snapshot(root)
            progress.rebuild_progress(root)
            self.assertEqual(before, files_snapshot(root))

    def test_プルリクの統合結果も読取り権限でテストする(self) -> None:
        workflow = (ROOT / ".github/workflows/python-tests.yml").read_text(encoding="utf-8")
        self.assertRegex(workflow, r"(?m)^  pull_request:")
        self.assertRegex(workflow, r"(?m)^  contents: read$")
        self.assertNotIn("pull_request_target", workflow)


    def test_状態行の重複を拒否する(self) -> None:
        with self.assertRaises(ValueError):
            session_parser.parse_graded_session(session().replace("- Status: grading", "- Status: grading\n- Status: graded"), 1)

    def test_補足内の点数は採点結果と別に扱う(self) -> None:
        _, questions = session_parser.parse_graded_session(session(score=80) + "\n#### note\nScore: 100 / 100\n", 1)
        self.assertEqual(80, questions[0].score)

    def test_表末尾の空欄も列として保持する(self) -> None:
        self.assertEqual(["TLS", "", ""], common.split_markdown_row("|TLS|||"))

    def test_ロールバックで改行と権限も保持する(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "data.md"
            path.write_bytes(b"original\r\n")
            path.chmod(0o600)
            with self.assertRaises(ValueError):
                with progress._restore_record_files_on_error([path]):
                    common.atomic_write(path, "changed\n")
                    path.chmod(0o644)
                    raise ValueError("failure")
            self.assertEqual(b"original\r\n", path.read_bytes())
            self.assertEqual(0o600, path.stat().st_mode & 0o777)

    def test_権限設定失敗でも一時ファイルを残さない(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with patch.object(common.os, "chmod", side_effect=PermissionError("failure")):
                with self.assertRaises(PermissionError):
                    common.atomic_write(root / "new.md", "new")
            self.assertEqual([], list(root.iterdir()))

    def test_直近件数が零以下なら空にする(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_session(root, "2026-09-05", session())
            self.assertEqual({}, session_parser.recent_term_sources(root, -1))
            self.assertEqual({}, session_parser.recent_domain_counts(root, 0))

    def test_不正な表で記録を更新しない(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = copy_study(Path(temporary))
            table = common.progress_file(root, "\u8a9e\u53e5\u5225\u7406\u89e3\u5ea6.md", "terms.md")
            lines = table.read_text(encoding="utf-8").splitlines()
            row_numbers = [i for i, line in enumerate(lines) if line.startswith("|")]
            lines[row_numbers[2]] += "extra |"
            table.write_text("\n".join(lines) + "\n", encoding="utf-8")
            before = files_snapshot(root)
            error_output = io.StringIO()
            with redirect_stderr(error_output):
                result = cli.main(["record", "--root", str(root), "--date", "2026-08-09", "--session", "1"])
            self.assertEqual(2, result)
            self.assertIn("columns", error_output.getvalue())
            self.assertEqual(before, files_snapshot(root))


if __name__ == "__main__":
    unittest.main()
