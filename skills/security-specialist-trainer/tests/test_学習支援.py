from __future__ import annotations

import importlib.util
import io
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import date, datetime, timedelta
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "study_helper.py"
SPEC = importlib.util.spec_from_file_location("study_helper", SCRIPT)
assert SPEC and SPEC.loader
study_helper = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = study_helper
SPEC.loader.exec_module(study_helper)


def 採点済みセッション(
    question_count_values: tuple[str, ...],
    question_numbers: tuple[str, ...],
) -> str:
    count_metadata = "\n".join(
        f"- Question Count: {value}" for value in question_count_values
    )
    question_blocks = []
    for index, number in enumerate(question_numbers, 1):
        question_blocks.append(
            f"""### Q{number}

- Domain: Webセキュリティ
- Primary Terms:
  - `試験語句{index}`
- Related Terms:
  - `関連語句{index}`
- Level: 2
- Track: B

### 採点

Score: 80 / 100
"""
        )
    return (
        "## Session 1\n\n"
        "- Status: grading\n"
        "- Mode: adaptive\n"
        f"{count_metadata}\n\n"
        + "\n".join(question_blocks)
    )


class 学習支援テスト(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.root = Path(__file__).resolve().parents[3]
        cls.catalog = study_helper.load_catalog(cls.root)

    def test_初回計画は八分野の診断になる(self) -> None:
        plan = study_helper.diagnostic_plan(self.catalog, 8)
        self.assertEqual(8, len(plan))
        self.assertEqual(8, len({candidate.item.domain for _, candidate in plan}))
        self.assertTrue(all(2 <= candidate.suggested_level <= 3 for _, candidate in plan))

    def test_学習日は午前五時に切り替わる(self) -> None:
        timezone = study_helper.STUDY_TIMEZONE
        self.assertEqual(
            date(2026, 8, 22),
            study_helper.current_study_date(datetime(2026, 8, 23, 4, 59, tzinfo=timezone)),
        )
        self.assertEqual(
            date(2026, 8, 23),
            study_helper.current_study_date(datetime(2026, 8, 23, 5, 0, tzinfo=timezone)),
        )

    def test_セッション要約の更新後も末尾改行を保持する(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            session_path = Path(temp_dir) / "session.md"
            session_path.write_text(
                "## Session 1\n\n- Status: graded\n\n"
                "## Session 1 Summary\n\n"
                "- Average: 80 / 100\n"
                "- Progress updated: terms.md / domains.md / history.md",
                encoding="utf-8",
            )
            summary = {
                "average": 80,
                "strong": [],
                "weak": [],
                "next_review": "2026-08-16",
                "next_review_interval_days": 1,
            }

            study_helper.finalize_session(session_path, 1, summary)
            self.assertIn(
                "- 次回復習: 次の学習時に優先（目安: 1日後）",
                session_path.read_text(encoding="utf-8"),
            )
            self.assertTrue(session_path.read_bytes().endswith(b"\n"))

            study_helper.finalize_session(session_path, 1, summary)
            self.assertTrue(session_path.read_bytes().endswith(b"\n"))

    def test_未解答一覧は空欄だけをモード別に表示する(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            standard_dir = root / "学習記録" / "理解・応用問題"
            recall_dir = root / "学習記録" / "暗記語句問題"
            standard_dir.mkdir(parents=True)
            recall_dir.mkdir(parents=True)
            (standard_dir / "2026-08-17.md").write_text(
                """## Session 1

- Status: awaiting_answers
- Mode: adaptive
- Question Count: 2

### Q1

- Primary Terms:
  - `SQLインジェクション`

### 回答

<!-- この行の下に回答を書いてください -->

### Q2

- Primary Terms:
  - `XSS`

### 回答

<!-- この行の下に回答を書いてください -->
""",
                encoding="utf-8",
            )
            (recall_dir / "2026-08-17.md").write_text(
                """## Session 2

- Status: awaiting_answers
- Mode: term-recall
- Question Count: 1

### Q1

- Primary Terms:
  - `CSRF`

### 回答

<!-- この行の下に回答を書いてください -->
""",
                encoding="utf-8",
            )

            path = study_helper.write_unanswered_index(root)
            index = path.read_text(encoding="utf-8")

            self.assertEqual(root / "学習記録" / "未解答一覧.md", path)
            self.assertNotIn("回答欄が空の問題だけを表示します。", index)
            self.assertTrue(index.startswith("# 未解答一覧\n\n## 理解・応用問題\n"))
            self.assertIn("## 理解・応用問題", index)
            self.assertIn(
                "[2026-08-17 / Session 1 / Q1~2](理解・応用問題/2026-08-17.md)",
                index,
            )
            self.assertIn("## 暗記語句問題", index)
            self.assertIn(
                "[2026-08-17 / Session 2 / Q1](暗記語句問題/2026-08-17.md)",
                index,
            )
            self.assertNotIn("SQLインジェクション", index)

            self.assertEqual(
                {"SQLインジェクション", "XSS", "CSRF"},
                study_helper.unanswered_primary_terms(root),
            )

    def test_行ったことは採点日ごとに追記し同じ日付だけを更新する(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            normal_dir = root / "学習記録" / "理解・応用問題"
            quick_dir = root / "学習記録" / "10分復習"
            normal_dir.mkdir(parents=True)
            quick_dir.mkdir(parents=True)
            (normal_dir / "2026-08-22.md").write_text(
                """## Session 2

- Status: graded
- Graded: 2026-08-23
- Mode: adaptive
- Question Count: 6
""",
                encoding="utf-8",
            )
            (quick_dir / "2026-08-23.md").write_text(
                """## Session 1

- Status: graded
- Graded: 2026-08-23
- Mode: quick-review
- Question Count: 8
""",
                encoding="utf-8",
            )
            (normal_dir / "2026-08-21.md").write_text(
                """## Session 1

- Status: graded
- Graded: 2026-08-22
- Mode: adaptive
- Question Count: 6
""",
                encoding="utf-8",
            )

            activity_path = root / "学習記録" / "行ったこと.md"
            activity_path.write_text(
                """# 行ったこと

## 2026-08-22

### 暗記語句問題

- [2026-08-20 / Session 1 / 10問](暗記語句問題/2026-08-20.md)
""",
                encoding="utf-8",
            )
            path = study_helper.write_activity_log(root, date(2026, 8, 23))
            activity = path.read_text(encoding="utf-8")

            self.assertEqual(root / "学習記録" / "行ったこと.md", path)
            self.assertIn("## 2026-08-22", activity)
            self.assertIn("## 2026-08-23", activity)
            self.assertLess(activity.index("## 2026-08-23"), activity.index("## 2026-08-22"))
            self.assertIn("### 理解・応用問題", activity)
            self.assertIn(
                "[2026-08-22 / Session 2 / 6問](理解・応用問題/2026-08-22.md)",
                activity,
            )
            self.assertIn("### 10分復習", activity)
            self.assertIn(
                "[2026-08-23 / Session 1 / 8問](10分復習/2026-08-23.md)", activity
            )
            self.assertNotIn("2026-08-21 / Session 1", activity)

    def test_未回答語句は明示指定なしで出題候補から除外する(self) -> None:
        item = next(item for item in self.catalog if item.term == "CSRF")
        candidates = study_helper.build_candidates(
            [item], {}, date(2026, 8, 12), {}, mode=study_helper.TERM_RECALL_MODE
        )

        self.assertEqual(
            [], study_helper.exclude_unanswered_candidates(candidates, {"CSRF"})
        )
        self.assertEqual(
            candidates,
            study_helper.exclude_unanswered_candidates(
                candidates, {"CSRF"}, include_unanswered=True
            ),
        )

    def test_未復習一覧は未チェック項目だけを点数順に表示する(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            review_dir = root / "復習用" / "明日復習するべきところ"
            review_dir.mkdir(parents=True)
            (review_dir / "2026-08-23.md").write_text(
                """# 2026-08-23に復習するべきところ

#### SAML — 15点

- [ ] 復習済み

#### DNSSEC — 0点

- [x] 復習済み
""",
                encoding="utf-8",
            )
            (review_dir / "2026-08-24.md").write_text(
                """# 2026-08-24に復習するべきところ

#### AEAD — 15点

- [ ] 復習済み

#### VPN（IPsec） — 35点

- [ ] 復習済み
""",
                encoding="utf-8",
            )

            path = study_helper.write_unreviewed_index(root)
            index = path.read_text(encoding="utf-8")

            self.assertEqual(root / "復習用" / "未復習一覧.md", path)
            self.assertEqual(
                ["SAML", "AEAD", "VPN（IPsec）"],
                [item.term for item in study_helper.unreviewed_items(root)],
            )
            self.assertIn(
                "[2026-08-23 / SAML — 15点](明日復習するべきところ/2026-08-23.md)",
                index,
            )
            self.assertIn(
                "[2026-08-24 / AEAD — 15点](明日復習するべきところ/2026-08-24.md)",
                index,
            )
            self.assertNotIn("DNSSEC", index)

    def test_初回の分野指定が診断構成を変える(self) -> None:
        plan = study_helper.diagnostic_plan(self.catalog, 8, "Webセキュリティ")
        web_count = sum(candidate.item.domain == "Webセキュリティ" for _, candidate in plan)
        self.assertGreaterEqual(web_count, 3)

    def test_暗記語句トリガーは既定十問で指定数を優先する(self) -> None:
        for request in ("暗記単語問題作って", "暗記語句問題作って"):
            with self.subTest(request=request):
                self.assertEqual(
                    (study_helper.TERM_RECALL_MODE, 10),
                    study_helper.infer_generation_request(request),
                )
        self.assertEqual(
            (study_helper.TERM_RECALL_MODE, 10),
            study_helper.infer_generation_request("単語問題10問"),
        )
        self.assertEqual(
            (study_helper.TERM_RECALL_MODE, 20),
            study_helper.infer_generation_request("暗記問題20問作って"),
        )
        self.assertEqual(
            ("standard", None),
            study_helper.infer_generation_request("復習問題作って"),
        )

        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = study_helper.main(
                [
                    "plan",
                    "--root",
                    str(self.root),
                    "--date",
                    "2026-08-12",
                    "--mode",
                    study_helper.TERM_RECALL_MODE,
                ]
            )
        self.assertEqual(0, exit_code)
        self.assertIn("- Questions: 10", output.getvalue())
        self.assertIn("- Track allocation: A 4 / B 6", output.getvalue())

    def test_今日の十分復習は既定八問の三択計画になる(self) -> None:
        self.assertEqual(
            (study_helper.QUICK_REVIEW_MODE, 8),
            study_helper.infer_generation_request("今日の10分復習"),
        )
        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = study_helper.main(
                [
                    "plan", "--root", str(self.root), "--date", "2026-08-22",
                    "--mode", study_helper.QUICK_REVIEW_MODE,
                ]
            )
        self.assertEqual(0, exit_code)
        self.assertIn("- Questions: 8", output.getvalue())
        self.assertIn("- Format: 3-choice", output.getvalue())

    def test_十分復習は期限超過と今日の復習と低得点を優先する(self) -> None:
        items = [
            study_helper.CatalogItem(f"語句{number}", f"分野{number}", "B", 5, 2, False, "", "")
            for number in range(1, 9)
        ]
        records = {
            item.term: study_helper.TermRecord(
                item.term, item.domain, 40 if index >= 6 else 80,
                date(2026, 8, 1), 1, 80, 2,
                date(2026, 8, 21) if index < 4 else date(2026, 8, 22) if index < 6 else date(2026, 8, 30), "", "",
            )
            for index, item in enumerate(items)
        }
        candidates = study_helper.build_candidates(items, records, date(2026, 8, 22), {})
        plan = study_helper.quick_review_plan(candidates, records, date(2026, 8, 22))
        labels = [label for label, _ in plan]
        self.assertEqual(4, labels.count("期限超過"))
        self.assertEqual(2, labels.count("今日の復習"))
        self.assertEqual(2, labels.count("低得点"))

    def test_十分復習の記録は理解度進捗を更新しない(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            review_dir = root / "学習記録" / "10分復習"
            progress_dir = root / "進捗"
            review_dir.mkdir(parents=True)
            progress_dir.mkdir()
            for name in ("語句別理解度.md", "分野別理解度.md", "学習履歴.md"):
                (progress_dir / name).write_text("変更しない\n", encoding="utf-8")
            (review_dir / "2026-08-22.md").write_text(
                """## Session 1

- Status: grading
- Mode: quick-review
- Question Count: 1

### Q1

- Domain: Webセキュリティ
- Primary Terms:
  - `CSRF`
- Related Terms:
  - `SameSite`
- Level: 2
- Track: B

### 採点

Score: 0 / 100
""",
                encoding="utf-8",
            )
            result = study_helper.record_progress(
                root, date(2026, 8, 22), 1, study_helper.QUICK_REVIEW_MODE
            )
            self.assertEqual(0, result["average"])
            for name in ("語句別理解度.md", "分野別理解度.md", "学習履歴.md"):
                self.assertEqual("変更しない\n", (progress_dir / name).read_text(encoding="utf-8"))
            session = (review_dir / "2026-08-22.md").read_text(encoding="utf-8")
            self.assertIn("- Status: graded", session)
            self.assertIn("Mastery updated: いいえ", session)

    def test_十分復習は選択肢のチェックボックスで回答済みを判定する(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            review_dir = root / "学習記録" / "10分復習"
            review_dir.mkdir(parents=True)
            (review_dir / "2026-08-22.md").write_text(
                """## Session 1

- Status: awaiting_answers
- Mode: quick-review

### Q1

- Primary Terms:
  - `CSRF`

### 問題

- [ ] A. CSRFトークンを検証する。
- [ ] B. Cookieを常に削除する。
- [ ] C. ログを削除する。

### Q2

- Primary Terms:
  - `XSS`

### 問題

- [ ] A. Cookieを常に削除する。
- [x] B. 出力エンコーディングを行う。
- [ ] C. ログを削除する。
""",
                encoding="utf-8",
            )
            unanswered = study_helper.unanswered_questions(root)
            self.assertEqual([1], [question.question_number for question in unanswered])
            self.assertEqual(("B",), study_helper.quick_review_checked_choices(
                (review_dir / "2026-08-22.md").read_text(encoding="utf-8")
            ))

    def test_十分復習の作成済み判定は取消済みを除外する(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            review_dir = root / "学習記録" / "10分復習"
            review_dir.mkdir(parents=True)
            path = review_dir / "2026-08-22.md"
            path.write_text(
                "## Session 1\n\n- Status: cancelled\n- Mode: quick-review\n",
                encoding="utf-8",
            )
            self.assertFalse(study_helper.quick_review_exists(root, date(2026, 8, 22)))
            path.write_text(
                "## Session 1\n\n- Status: awaiting_answers\n- Mode: quick-review\n",
                encoding="utf-8",
            )
            self.assertTrue(study_helper.quick_review_exists(root, date(2026, 8, 22)))

    def test_問題数は一問から三十問を受理し範囲外を拒否する(self) -> None:
        accepted = [
            ["--mode", "standard", "--count", "1"],
            ["--mode", study_helper.TERM_RECALL_MODE, "--count", "30"],
        ]
        for extra_args in accepted:
            with self.subTest(accepted=extra_args):
                with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                    exit_code = study_helper.main(
                        [
                            "plan",
                            "--root",
                            str(self.root),
                            "--date",
                            "2026-08-12",
                            *extra_args,
                        ]
                    )
                self.assertEqual(0, exit_code)

        rejected = [
            ["--mode", "standard", "--count", "0"],
            ["--mode", study_helper.TERM_RECALL_MODE, "--count", "31"],
        ]
        for extra_args in rejected:
            with self.subTest(rejected=extra_args):
                error = io.StringIO()
                with redirect_stdout(io.StringIO()), redirect_stderr(error):
                    exit_code = study_helper.main(
                        [
                            "plan",
                            "--root",
                            str(self.root),
                            "--date",
                            "2026-08-12",
                            *extra_args,
                        ]
                    )
                self.assertEqual(2, exit_code)
                self.assertIn("--count must be between 1 and 30", error.getvalue())

    def test_自然言語依頼はコマンドラインオプションとして公開しない(self) -> None:
        error = io.StringIO()
        with redirect_stderr(error), self.assertRaises(SystemExit) as raised:
            study_helper.parse_args(["plan", "--request", "暗記問題10問作って"])
        self.assertEqual(2, raised.exception.code)
        self.assertIn("unrecognized arguments: --request", error.getvalue())

    def test_暗記語句計画は指定どおりに科目区分を配分する(self) -> None:
        candidates = study_helper.build_candidates(
            self.catalog,
            {},
            date(2026, 8, 12),
            {},
            mode=study_helper.TERM_RECALL_MODE,
        )
        for count in (1, 5, 7, 10, 20, 30):
            with self.subTest(count=count):
                plan = study_helper.term_recall_plan(candidates, count)
                expected_a, expected_b = study_helper.term_recall_track_counts(count)
                tracks = [
                    study_helper.planned_track(candidate, study_helper.TERM_RECALL_MODE)
                    for _, candidate in plan
                ]
                self.assertEqual(count, len(plan))
                self.assertEqual(expected_a, tracks.count("A"))
                self.assertEqual(expected_b, tracks.count("B"))
                self.assertTrue(all(candidate.suggested_level == 1 for _, candidate in plan))

    def test_重要度の高い未学習語句を明確に優先する(self) -> None:
        high = study_helper.CatalogItem(
            "重要語句", "Webセキュリティ", "A/B", 5, 1, False, "", ""
        )
        normal = study_helper.CatalogItem(
            "通常語句", "Webセキュリティ", "A/B", 3, 1, False, "", ""
        )
        candidates = study_helper.build_candidates(
            [high, normal], {}, date(2026, 8, 15), {}, mode=study_helper.TERM_RECALL_MODE
        )
        priority = {candidate.item.term: candidate.priority for candidate in candidates}
        self.assertGreater(priority["重要語句"] - priority["通常語句"], 7)

    def test_暗記語句問題は短い定義説明形式になる(self) -> None:
        question = study_helper.term_recall_question("CSRF")
        self.assertEqual(
            "CSRFとは何ですか？",
            question,
        )
        self.assertNotIn("意味・目的", question)
        self.assertEqual(1, question.count("？"))
        self.assertNotIn("シナリオ", question)
        self.assertEqual("短いシナリオ", study_helper.suggested_form(4))

    def test_暗記語句セッションは難易度一以外を拒否する(self) -> None:
        text = """## Session 1

- Status: grading
- Mode: term-recall
- Question Count: 1

### Q1

- Domain: Webセキュリティ
- Primary Terms:
  - `CSRF`
- Related Terms:
  - `SameSite`
- Level: 5
- Track: B

### 採点

Score: 100 / 100
"""
        with self.assertRaisesRegex(ValueError, "must use Level 1"):
            study_helper.parse_graded_session(text, 1)

    def test_暗記語句セッションは科目区分の配分違反を拒否する(self) -> None:
        text = """## Session 1

- Status: grading
- Mode: term-recall
- Question Count: 2

### Q1

- Domain: 暗号
- Primary Terms:
  - `ハッシュ関数`
- Related Terms:
  - `改ざん検知`
- Level: 1
- Track: A

### 採点

Score: 80 / 100

### Q2

- Domain: Webセキュリティ
- Primary Terms:
  - `CSRF`
- Related Terms:
  - `SameSite`
- Level: 1
- Track: B

### 採点

Score: 80 / 100
"""
        with self.assertRaisesRegex(ValueError, "Track allocation must be A 0 / B 2"):
            study_helper.parse_graded_session(text, 1)

    def test_暗記語句セッションは曖昧な科目区分を拒否する(self) -> None:
        text = """## Session 1

- Status: grading
- Mode: term-recall
- Question Count: 1

### Q1

- Domain: 暗号
- Primary Terms:
  - `ハッシュ関数`
- Related Terms:
  - `改ざん検知`
- Level: 1
- Track: A/B

### 採点

Score: 80 / 100
"""
        with self.assertRaisesRegex(ValueError, "must use Track A or B"):
            study_helper.parse_graded_session(text, 1)

    def test_暗記語句セッションは各問の中心語句を一つに限る(self) -> None:
        text = """## Session 1

- Status: grading
- Mode: term-recall
- Question Count: 1

### Q1

- Domain: Webセキュリティ
- Primary Terms:
  - `CSRF`
  - `XSS`
- Related Terms:
  - `SameSite`
- Level: 1
- Track: B

### 採点

Score: 100 / 100
"""
        with self.assertRaisesRegex(ValueError, "exactly one Primary Term each"):
            study_helper.parse_graded_session(text, 1)

        normal_text = text.replace("- Mode: term-recall", "- Mode: adaptive")
        _, questions = study_helper.parse_graded_session(normal_text, 1)
        self.assertEqual(("CSRF", "XSS"), questions[0].primary_terms)

    def test_問題数メタデータは一つの整数で必須になる(self) -> None:
        invalid_cases = (
            ((), "exactly one Question Count"),
            (("1", "1"), "exactly one Question Count"),
            (("one",), "Question Count must be an integer"),
        )
        for count_values, message in invalid_cases:
            with self.subTest(count_values=count_values):
                text = 採点済みセッション(count_values, ("1",))
                with self.assertRaisesRegex(ValueError, message):
                    study_helper.parse_graded_session(text, 1)

    def test_セッション問題数は一問から三十問の範囲に限る(self) -> None:
        for count in ("0", "31"):
            with self.subTest(count=count):
                text = 採点済みセッション((count,), ("1",))
                with self.assertRaisesRegex(ValueError, "must be between 1 and 30"):
                    study_helper.parse_graded_session(text, 1)

    def test_問題数と実際の見出し数は一致する(self) -> None:
        text = 採点済みセッション(("2",), ("1",))
        with self.assertRaisesRegex(ValueError, "but found 1 question headings"):
            study_helper.parse_graded_session(text, 1)

    def test_問題番号は一から連番で重複しない(self) -> None:
        for question_numbers in (("1", "1"), ("1", "3")):
            with self.subTest(question_numbers=question_numbers):
                text = 採点済みセッション(
                    (str(len(question_numbers)),), question_numbers
                )
                with self.assertRaisesRegex(ValueError, "consecutive and unique from Q1"):
                    study_helper.parse_graded_session(text, 1)

    def test_数字以外と形式違いの問題見出しを拒否する(self) -> None:
        for question_numbers in (
            ("1", "X"),
            ("1", ""),
            ("1", " 2"),
            ("1", "01"),
        ):
            with self.subTest(question_numbers=question_numbers):
                text = 採点済みセッション(("1",), question_numbers)
                with self.assertRaisesRegex(ValueError, "invalid question headings"):
                    study_helper.parse_graded_session(text, 1)

    def test_不正なセッション構造では進捗ファイルを更新しない(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            session_dir = root / "sessions" / "理解・応用問題"
            progress_dir = root / "progress"
            session_dir.mkdir(parents=True)
            progress_dir.mkdir()
            session_path = session_dir / "2026-08-12.md"
            progress_paths = [
                progress_dir / "terms.md",
                progress_dir / "domains.md",
                progress_dir / "history.md",
            ]
            for path in progress_paths:
                path.write_text(f"{path.name} sentinel\n", encoding="utf-8")
            before = {path: path.read_bytes() for path in progress_paths}

            invalid_sessions = (
                (採点済みセッション((), ("1",)), "exactly one Question Count"),
                (
                    採点済みセッション(("1",), ("1", "X")),
                    "invalid question headings",
                ),
                (
                    採点済みセッション(("1",), ("1",)).replace(
                        "- Mode: adaptive\n", ""
                    ),
                    "exactly one Mode",
                ),
                (
                    採点済みセッション(("1",), ("1",)).replace(
                        "- Mode: adaptive\n",
                        "- Mode: adaptive\n- Mode: term-recall\n",
                    ),
                    "exactly one Mode",
                ),
                (
                    採点済みセッション(("1",), ("1",)).replace(
                        "- Mode: adaptive", "- Mode: term-recal"
                    ),
                    "unsupported Mode",
                ),
                (
                    採点済みセッション(("1",), ("1",)).replace(
                        "- Mode: adaptive", "- Mode: term-recall"
                    ),
                    "must use standard mode",
                ),
            )
            for session_text, message in invalid_sessions:
                with self.subTest(message=message):
                    session_path.write_text(session_text, encoding="utf-8")
                    with self.assertRaisesRegex(ValueError, message):
                        study_helper.record_progress(
                            root,
                            date(2026, 8, 12),
                            1,
                            study_helper.STANDARD_SESSION_MODE,
                        )

                    self.assertEqual(
                        before, {path: path.read_bytes() for path in progress_paths}
                    )

    def test_現行セッションはモードを一つの許可値に限る(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            current_dir = root / "sessions" / "理解・応用問題"
            current_dir.mkdir(parents=True)
            session_path = current_dir / "2026-08-12.md"

            invalid_mode_lines = (
                "",
                "- Mode: adaptive\n- Mode: term-recall\n",
                "- Mode: term-recal\n",
            )
            for mode_lines in invalid_mode_lines:
                with self.subTest(mode_lines=mode_lines):
                    session_path.write_text(
                        "## Session 1\n\n- Status: grading\n" + mode_lines,
                        encoding="utf-8",
                    )
                    with self.assertRaisesRegex(ValueError, "Mode"):
                        study_helper.resolve_session_path(
                            root,
                            date(2026, 8, 12),
                            1,
                            study_helper.STANDARD_SESSION_MODE,
                        )

            session_path.write_text(
                "## Session 1\n\n- Status: grading\n- Mode: adaptive\n",
                encoding="utf-8",
            )
            self.assertEqual(
                session_path,
                study_helper.resolve_session_path(
                    root,
                    date(2026, 8, 12),
                    1,
                    study_helper.STANDARD_SESSION_MODE,
                ),
            )

    def test_モードなしは旧セッションだけ通常問題として読む(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            legacy_dir = root / "sessions"
            legacy_dir.mkdir()
            legacy_path = legacy_dir / "2026-08-12.md"
            legacy_path.write_text(
                "## Session 1\n\n- Status: graded\n",
                encoding="utf-8",
            )
            self.assertEqual(
                legacy_path,
                study_helper.resolve_session_path(
                    root,
                    date(2026, 8, 12),
                    1,
                    study_helper.STANDARD_SESSION_MODE,
                ),
            )

    def test_現行保存先とモードの対応を必須にする(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            cases = (
                ("暗記語句問題", "adaptive", study_helper.STANDARD_SESSION_MODE),
                ("理解・応用問題", "term-recall", study_helper.TERM_RECALL_MODE),
            )
            for directory, metadata_mode, cli_mode in cases:
                with self.subTest(directory=directory, metadata_mode=metadata_mode):
                    path = root / "sessions" / directory / "2026-08-12.md"
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(
                        f"## Session 1\n\n- Status: grading\n- Mode: {metadata_mode}\n",
                        encoding="utf-8",
                    )
                    with self.assertRaisesRegex(ValueError, "must use"):
                        study_helper.resolve_session_path(
                            root,
                            date(2026, 8, 12),
                            1,
                            cli_mode,
                        )
                    path.unlink()

            legacy = root / "sessions" / "term-recall" / "2026-08-12.md"
            legacy.parent.mkdir(parents=True)
            legacy.write_text(
                "## Session 1\n\n- Status: graded\n- Mode: adaptive\n",
                encoding="utf-8",
            )
            self.assertEqual(
                legacy,
                study_helper.resolve_session_path(
                    root,
                    date(2026, 8, 12),
                    1,
                    study_helper.STANDARD_SESSION_MODE,
                ),
            )

    def test_低得点は優先度を上げ基礎難易度を維持する(self) -> None:
        item = next(item for item in self.catalog if item.term == "DNSキャッシュポイズニング")
        weak = study_helper.TermRecord(
            item.term, item.domain, 31, date(2026, 8, 8), 2, 35, 2, date(2026, 8, 9), item.related, ""
        )
        strong = study_helper.TermRecord(
            item.term, item.domain, 92, date(2026, 8, 8), 5, 91, 5, date(2026, 9, 7), item.related, ""
        )
        weak_candidate = study_helper.build_candidates([item], {item.term: weak}, date(2026, 8, 9), {})[0]
        strong_candidate = study_helper.build_candidates([item], {item.term: strong}, date(2026, 8, 9), {})[0]
        self.assertGreater(weak_candidate.priority, strong_candidate.priority)
        self.assertEqual(1, weak_candidate.suggested_level)
        self.assertEqual(5, strong_candidate.suggested_level)

    def test_復習期限超過は忘却優先度を上げる(self) -> None:
        item = next(item for item in self.catalog if item.term == "CRL / OCSP")
        record = study_helper.TermRecord(
            item.term, item.domain, 70, date(2026, 8, 1), 3, 73, 3, date(2026, 8, 6), item.related, ""
        )
        candidate = study_helper.build_candidates([item], {item.term: record}, date(2026, 8, 9), {})[0]
        self.assertTrue(candidate.due)
        self.assertGreaterEqual(candidate.forgetting, 35)

    def test_暗記語句でも忘却度と次回復習日を使う(self) -> None:
        item = next(item for item in self.catalog if item.term == "CRL / OCSP")
        record = study_helper.TermRecord(
            item.term,
            item.domain,
            70,
            date(2026, 8, 1),
            3,
            73,
            3,
            date(2026, 8, 6),
            item.related,
            "",
            recall_score=75,
            recall_attempts=1,
            explanation_score=68,
            explanation_attempts=2,
        )
        candidate = study_helper.build_candidates(
            [item],
            {item.term: record},
            date(2026, 8, 9),
            {},
            mode=study_helper.TERM_RECALL_MODE,
        )[0]
        self.assertTrue(candidate.due)
        self.assertGreaterEqual(candidate.forgetting, 35)

    def test_暗記理解度の低さは通常問題の優先度を上げる(self) -> None:
        item = next(item for item in self.catalog if item.term == "CSRF")
        common = dict(
            term=item.term,
            domain=item.domain,
            score=70,
            last_studied=date(2026, 8, 8),
            attempts=4,
            average=70,
            last_level=3,
            next_review=date(2026, 8, 13),
            related=item.related,
            notes="",
            explanation_score=70,
            explanation_attempts=3,
            recall_attempts=1,
        )
        weak_recall = study_helper.TermRecord(**common, recall_score=20)
        strong_recall = study_helper.TermRecord(**common, recall_score=90)
        weak_priority = study_helper.build_candidates(
            [item], {item.term: weak_recall}, date(2026, 8, 9), {}
        )[0].priority
        strong_priority = study_helper.build_candidates(
            [item], {item.term: strong_recall}, date(2026, 8, 9), {}
        )[0].priority
        self.assertGreater(weak_priority, strong_priority)

    def test_通常説明理解度の低さは暗記語句の優先度を上げる(self) -> None:
        item = next(item for item in self.catalog if item.term == "DNSキャッシュポイズニング")
        common = dict(
            term=item.term,
            domain=item.domain,
            score=70,
            last_studied=date(2026, 8, 8),
            attempts=4,
            average=70,
            last_level=3,
            next_review=date(2026, 8, 13),
            related=item.related,
            notes="",
            recall_score=70,
            recall_attempts=1,
            explanation_attempts=3,
        )
        weak_explanation = study_helper.TermRecord(**common, explanation_score=20)
        strong_explanation = study_helper.TermRecord(**common, explanation_score=90)
        weak_priority = study_helper.build_candidates(
            [item],
            {item.term: weak_explanation},
            date(2026, 8, 9),
            {},
            mode=study_helper.TERM_RECALL_MODE,
        )[0].priority
        strong_priority = study_helper.build_candidates(
            [item],
            {item.term: strong_explanation},
            date(2026, 8, 9),
            {},
            mode=study_helper.TERM_RECALL_MODE,
        )[0].priority
        self.assertGreater(weak_priority, strong_priority)

    def test_通常説明理解度が通常問題の弱点度と難易度を決める(self) -> None:
        item = next(item for item in self.catalog if item.term == "DNSキャッシュポイズニング")
        common = dict(
            term=item.term,
            domain=item.domain,
            score=70,
            last_studied=date(2026, 8, 8),
            attempts=4,
            average=70,
            last_level=3,
            next_review=date(2026, 8, 13),
            related=item.related,
            notes="",
            recall_score=90,
            recall_attempts=1,
            explanation_attempts=3,
        )
        weak = study_helper.build_candidates(
            [item],
            {item.term: study_helper.TermRecord(**common, explanation_score=20)},
            date(2026, 8, 9),
            {},
        )[0]
        strong = study_helper.build_candidates(
            [item],
            {item.term: study_helper.TermRecord(**common, explanation_score=90)},
            date(2026, 8, 9),
            {},
        )[0]
        self.assertGreater(weak.priority, strong.priority)
        self.assertGreater(weak.weakness, strong.weakness)
        self.assertEqual(1, weak.suggested_level)
        self.assertEqual(5, strong.suggested_level)
        self.assertFalse(weak.challenge)
        self.assertTrue(strong.challenge)

    def test_暗記のみ学習した語句は通常説明で未評価になる(self) -> None:
        item = next(item for item in self.catalog if item.term == "DNSキャッシュポイズニング")
        record = study_helper.TermRecord(
            term=item.term,
            domain=item.domain,
            score=70,
            last_studied=date(2026, 8, 8),
            attempts=1,
            average=100,
            last_level=1,
            next_review=date(2026, 8, 13),
            related=item.related,
            notes="",
            recall_score=100,
            recall_attempts=1,
        )
        candidate = study_helper.build_candidates(
            [item], {item.term: record}, date(2026, 8, 9), {}
        )[0]
        self.assertTrue(candidate.unseen)
        self.assertEqual(0, candidate.weakness)
        self.assertIn("通常説明では未評価", candidate.reason)

    def test_難易度上限は定義問題だけでの習熟を防ぐ(self) -> None:
        self.assertEqual(70, study_helper.updated_mastery(None, 0, 100, 1))
        self.assertEqual(100, study_helper.updated_mastery(None, 0, 100, 5))
        self.assertEqual(100, study_helper.updated_recall_mastery(None, 0, 100))

    def test_分野は上限適用点を使い履歴は生点を保つ(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "progress").mkdir()
            (root / "progress" / "history.md").write_text(
                study_helper.render_history([]), encoding="utf-8"
            )
            record = study_helper.TermRecord(
                term="CSRF",
                domain="Webセキュリティ",
                score=70,
                last_studied=date(2026, 8, 12),
                attempts=1,
                average=100,
                last_level=1,
                next_review=date(2026, 8, 17),
                related="CSRFトークン",
                notes="",
                recall_score=100,
                recall_attempts=1,
            )
            question = study_helper.GradedQuestion(
                number=1,
                domain="Webセキュリティ",
                track="B",
                level=1,
                primary_terms=("CSRF",),
                related_terms=("CSRFトークン",),
                score=100,
                good_point="定義を説明できた",
                review_focus="応用条件",
                question_mode=study_helper.TERM_RECALL_MODE,
            )
            domain_text = study_helper.render_domains(
                [{"Domain": "Webセキュリティ", "Notes": ""}],
                {record.term: record},
                [(date(2026, 8, 12), 1, question)],
                date(2026, 8, 12),
            )
            domain_path = root / "progress" / "domains.md"
            domain_path.write_text(domain_text, encoding="utf-8")
            domain_row = study_helper.read_table(domain_path, "Domain")[0]
            self.assertEqual("70", domain_row["Score"])

            summary = study_helper.update_history(
                root,
                date(2026, 8, 12),
                1,
                [question],
                {record.term: record},
                root / "sessions" / "暗記語句問題" / "2026-08-12.md",
            )
            history_row = study_helper.read_table(
                root / "progress" / "history.md", "Date"
            )[0]
            self.assertEqual(100, summary["average"])
            self.assertEqual("100", history_row["Average"])
            self.assertEqual(100, record.recall_score)

    def test_カバレッジは暗記と応用と高難度安定を区別する(self) -> None:
        recall = study_helper.GradedQuestion(
            1, "Webセキュリティ", "B", 1, ("CSRF",), (), 100, "", "",
            study_helper.TERM_RECALL_MODE,
        )
        application = study_helper.GradedQuestion(
            2, "Webセキュリティ", "B", 4, ("XSS",), (), 80, "", "",
        )
        high_one = study_helper.GradedQuestion(
            3, "Webセキュリティ", "B", 5, ("SQLインジェクション",), (), 90, "", "",
        )
        high_two = study_helper.GradedQuestion(
            4, "Webセキュリティ", "B", 5, ("SSRF",), (), 95, "", "",
        )

        self.assertEqual(("未評価", "—"), study_helper.domain_coverage([]))
        self.assertEqual("用語想起のみ", study_helper.domain_coverage([recall])[0])
        self.assertEqual("応用まで確認", study_helper.domain_coverage([recall, application, high_one])[0])
        coverage, evidence = study_helper.domain_coverage(
            [recall, application, high_one, high_two]
        )
        self.assertEqual("高難度で安定", coverage)
        self.assertEqual("暗記 1問 / 応用 3問 / 高難度成功 2問", evidence)

    def test_分野表示は未評価重要語数とカタログ分野を含む(self) -> None:
        catalog = [
            study_helper.CatalogItem("評価済み", "新規分野", "B", 5, 2, False, "", ""),
            study_helper.CatalogItem("未評価重要語", "新規分野", "B", 4, 2, False, "", ""),
            study_helper.CatalogItem("低重要語", "新規分野", "B", 3, 2, False, "", ""),
        ]
        record = study_helper.TermRecord(
            "評価済み", "新規分野", 80, date(2026, 8, 12), 1, 80, 3,
            date(2026, 8, 17), "", "", explanation_score=80, explanation_attempts=1,
        )
        question = study_helper.GradedQuestion(
            1, "新規分野", "B", 3, ("評価済み",), (), 80, "", "",
        )
        rendered = study_helper.render_domains(
            [], {record.term: record}, [(date(2026, 8, 12), 1, question)],
            date(2026, 8, 12), catalog,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "domains.md"
            path.write_text(rendered, encoding="utf-8")
            row = study_helper.read_table(path, "Domain")[0]
        self.assertEqual("応用まで確認", row["Coverage"])
        self.assertEqual("1", row["Unassessed Important Terms"])
        self.assertEqual("1", row["Questions"])

    def test_通常六問計画は新規を二問含む(self) -> None:
        today = date(2026, 8, 9)
        wanted = {
            "SQLインジェクション": (35, date(2026, 8, 7), date(2026, 8, 8)),
            "XSS": (72, date(2026, 8, 1), date(2026, 8, 6)),
            "DMARC": (93, date(2026, 8, 8), date(2026, 9, 7)),
            "TLSハンドシェイク": (82, date(2026, 8, 8), date(2026, 8, 20)),
        }
        records = {}
        for item in self.catalog:
            if item.term in wanted:
                score, studied, review = wanted[item.term]
                records[item.term] = study_helper.TermRecord(
                    item.term, item.domain, score, studied, 3, score, 4, review, item.related, ""
                )
        candidates = study_helper.build_candidates(self.catalog, records, today, {})
        plan = study_helper.adaptive_plan(candidates, 6)
        buckets = [bucket for bucket, _ in plan]
        self.assertEqual(6, len(plan))
        self.assertIn("弱点", buckets)
        self.assertIn("復習期", buckets)
        self.assertEqual(2, buckets.count("新規"))
        self.assertIn("発展", buckets)

    def test_通常問題の六問超過分は全て新規になる(self) -> None:
        candidates = study_helper.build_candidates(self.catalog, {}, date(2026, 8, 9), {})
        plan = study_helper.adaptive_plan(candidates, 9)
        buckets = [bucket for bucket, _ in plan]
        self.assertEqual(9, len(plan))
        self.assertEqual(5, buckets.count("新規"))

    def test_通常問題の既定数は六問である(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = study_helper.main(
                ["plan", "--root", str(self.root), "--date", "2026-08-13"]
            )
        self.assertEqual(0, exit_code)
        self.assertIn("- Questions: 6", output.getvalue())

    def test_直近高得点は復習期でなく将来の発展候補になる(self) -> None:
        item = next(item for item in self.catalog if item.term == "DMARC")
        record = study_helper.TermRecord(
            item.term, item.domain, 95, date(2026, 8, 9), 6, 94, 5, date(2026, 9, 8), item.related, ""
        )
        candidate = study_helper.build_candidates([item], {item.term: record}, date(2026, 8, 9), {})[0]
        self.assertFalse(candidate.due)
        self.assertTrue(candidate.challenge)
        self.assertEqual(6, candidate.suggested_level)

    def test_新規モードは未学習枠を増やす(self) -> None:
        item = next(item for item in self.catalog if item.term == "SQLインジェクション")
        record = study_helper.TermRecord(
            item.term, item.domain, 55, date(2026, 8, 8), 2, 55, 2, date(2026, 8, 10), item.related, ""
        )
        candidates = study_helper.build_candidates(
            self.catalog, {item.term: record}, date(2026, 8, 9), {}, mode="new"
        )
        plan = study_helper.adaptive_plan(candidates, 5, mode="new")
        self.assertGreaterEqual(sum(bucket == "新規" for bucket, _ in plan), 2)

    def test_五問計画は科目B比率を範囲内に保つ(self) -> None:
        candidates = study_helper.build_candidates(self.catalog, {}, date(2026, 8, 10), {})
        plan = study_helper.adaptive_plan(candidates, 5)
        self.assertEqual(4, sum(candidate.item.track == "B" for _, candidate in plan))

    def test_分類表にない進捗語句も候補に残る(self) -> None:
        record = study_helper.TermRecord(
            "プレースホルダ",
            "Webセキュリティ",
            35,
            date(2026, 8, 9),
            1,
            35,
            2,
            date(2026, 8, 10),
            "SQLインジェクション",
            "",
            track="A",
        )
        merged = study_helper.merge_uncatalogued_terms(self.catalog, {record.term: record})
        merged_by_term = {item.term: item for item in merged}
        self.assertEqual("A", merged_by_term["プレースホルダ"].track)

    def test_同日抑制は生涯平均でなく直近得点を使う(self) -> None:
        item = next(item for item in self.catalog if item.term == "SQLインジェクション")
        failed = study_helper.TermRecord(
            item.term,
            item.domain,
            57,
            date(2026, 8, 9),
            10,
            85,
            5,
            date(2026, 8, 10),
            item.related,
            "",
            track="B",
            last_score=20,
        )
        passed = study_helper.TermRecord(
            item.term,
            item.domain,
            57,
            date(2026, 8, 9),
            10,
            85,
            5,
            date(2026, 8, 10),
            item.related,
            "",
            track="B",
            last_score=80,
        )
        failed_priority = study_helper.build_candidates(
            [item], {item.term: failed}, date(2026, 8, 9), {}
        )[0].priority
        passed_priority = study_helper.build_candidates(
            [item], {item.term: passed}, date(2026, 8, 9), {}
        )[0].priority
        self.assertEqual(30, failed_priority - passed_priority)

    def test_直近出題語句は再出題優先度が下がる(self) -> None:
        item = next(item for item in self.catalog if item.term == "CSRF")
        without_repeat = study_helper.build_candidates(
            [item], {}, date(2026, 8, 12), {}, mode=study_helper.TERM_RECALL_MODE
        )[0]
        with_repeat = study_helper.build_candidates(
            [item],
            {},
            date(2026, 8, 12),
            {},
            mode=study_helper.TERM_RECALL_MODE,
            recent_terms={item.term: 4},
        )[0]
        self.assertEqual(16, without_repeat.priority - with_repeat.priority)

    def test_暗記と通常説明の復習期限を別々に判定する(self) -> None:
        item = next(item for item in self.catalog if item.term == "CSRF")
        record = study_helper.TermRecord(
            item.term,
            item.domain,
            70,
            date(2026, 8, 20),
            2,
            70,
            1,
            date(2026, 8, 19),
            item.related,
            "",
            recall_score=90,
            recall_attempts=1,
            explanation_score=50,
            explanation_attempts=1,
            recall_last_studied=date(2026, 8, 20),
            recall_next_review=date(2026, 9, 19),
            explanation_last_studied=date(2026, 8, 10),
            explanation_next_review=date(2026, 8, 15),
        )

        recall = study_helper.build_candidates(
            [item], {item.term: record}, date(2026, 8, 20), {}, mode=study_helper.TERM_RECALL_MODE
        )[0]
        explanation = study_helper.build_candidates(
            [item], {item.term: record}, date(2026, 8, 20), {}, mode="standard"
        )[0]

        self.assertFalse(recall.due)
        self.assertTrue(explanation.due)

    def test_旧語句欄も直近出題語句として集計する(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            sessions = root / "sessions"
            sessions.mkdir()
            (sessions / "2026-08-12.md").write_text(
                """## Session 1

### Q1

- Domain: Webセキュリティ
- Terms: `CSRF`
""",
                encoding="utf-8",
            )

            recent_terms = study_helper.recent_term_counts(root, date(2026, 8, 12))
            self.assertEqual(4, recent_terms["CSRF"])

            item = next(item for item in self.catalog if item.term == "CSRF")
            without_repeat = study_helper.build_candidates(
                [item], {}, date(2026, 8, 12), {}, mode=study_helper.TERM_RECALL_MODE
            )[0]
            with_repeat = study_helper.build_candidates(
                [item],
                {},
                date(2026, 8, 12),
                {},
                mode=study_helper.TERM_RECALL_MODE,
                recent_terms=recent_terms,
            )[0]
            self.assertEqual(16, without_repeat.priority - with_repeat.priority)

    def test_古いセッションは新しい語句証拠を上書きできない(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "progress").mkdir()
            existing = study_helper.TermRecord(
                "SQLインジェクション",
                "Webセキュリティ",
                70,
                date(2026, 8, 9),
                1,
                70,
                2,
                date(2026, 8, 14),
                "プレースホルダ",
                "",
                track="B",
                last_score=70,
                last_session="2026-08-09#2",
                applied_sessions=("2026-08-09#2",),
            )
            terms_path = root / "progress" / "terms.md"
            terms_path.write_text(
                study_helper.render_terms({existing.term: existing}),
                encoding="utf-8",
            )
            question = study_helper.GradedQuestion(
                number=1,
                domain="Webセキュリティ",
                track="B",
                level=2,
                primary_terms=("SQLインジェクション",),
                related_terms=("プレースホルダ",),
                score=80,
                good_point="",
                review_focus="",
            )
            with self.assertRaisesRegex(ValueError, "record sessions chronologically"):
                study_helper.update_term_records(root, date(2026, 8, 9), 1, [question], [])
            self.assertEqual(1, study_helper.load_terms(root)[existing.term].attempts)

    def test_高難易度の成功は復習間隔を延ばす(self) -> None:
        self.assertEqual(30, study_helper.next_interval(92, 80, 5))
        self.assertGreater(study_helper.next_interval(92, 95, 5, 2), 30)

    def test_高得点継続には直前難易度五以上が必要になる(self) -> None:
        for previous_level, expected_days in ((1, 38), (5, 45)):
            with self.subTest(previous_level=previous_level):
                with tempfile.TemporaryDirectory() as temp_dir:
                    root = Path(temp_dir)
                    (root / "progress").mkdir()
                    old = study_helper.TermRecord(
                        term="CSRF",
                        domain="Webセキュリティ",
                        score=90,
                        last_studied=date(2026, 8, 1),
                        attempts=1,
                        average=100,
                        last_level=previous_level,
                        next_review=date(2026, 8, 31),
                        related="CSRFトークン",
                        notes="",
                        track="B",
                        last_score=100,
                        last_session="2026-08-01#1",
                        applied_sessions=("2026-08-01#1",),
                        explanation_score=100,
                        explanation_attempts=1,
                    )
                    (root / "progress" / "terms.md").write_text(
                        study_helper.render_terms({old.term: old}), encoding="utf-8"
                    )
                    question = study_helper.GradedQuestion(
                        number=1,
                        domain="Webセキュリティ",
                        track="B",
                        level=5,
                        primary_terms=("CSRF",),
                        related_terms=("CSRFトークン",),
                        score=100,
                        good_point="応用できた",
                        review_focus="残存リスク",
                    )
                    records = study_helper.update_term_records(
                        root, date(2026, 8, 12), 1, [question], []
                    )
                    interval = records[old.term].next_review - date(2026, 8, 12)
                    self.assertEqual(timedelta(days=expected_days), interval)

    def test_マークダウン表だけを状態管理に使う(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "references").mkdir()
            (root / "progress").mkdir()
            (root / "sessions").mkdir()
            taxonomy = self.root / "参照資料" / "出題分類と概念カタログ.md"
            (root / "references" / "taxonomy.md").write_text(taxonomy.read_text(encoding="utf-8"), encoding="utf-8")
            (root / "progress" / "terms.md").write_text(
                "| Term | Domain | Score | Last Studied | Attempts | Average | Last Level | Next Review | Related | Notes |\n"
                "|---|---|---:|---|---:|---:|---:|---|---|---|\n",
                encoding="utf-8",
            )
            self.assertTrue(study_helper.load_catalog(root))
            self.assertEqual({}, study_helper.load_terms(root))

    def test_旧進捗と旧セッションは通常説明として扱う(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "progress").mkdir()
            (root / "progress" / "terms.md").write_text(
                "| Term | Domain | Score | Last Studied | Attempts | Average | Last Level | Next Review | Related | Notes |\n"
                "|---|---|---:|---|---:|---:|---:|---|---|---|\n"
                "| CSRF | Webセキュリティ | 55 | 2026-08-01 | 2 | 50 | 3 | 2026-08-03 | XSS | 要復習 |\n",
                encoding="utf-8",
            )
            record = study_helper.load_terms(root)["CSRF"]
            self.assertEqual(55, record.explanation_score)
            self.assertEqual(2, record.explanation_attempts)
            self.assertIsNone(record.recall_score)
            self.assertEqual(0, record.recall_attempts)

            _, questions = study_helper.parse_graded_session(
                """## Session 1

- Status: grading
- Question Count: 1

### Q1

- Domain: Webセキュリティ
- Primary Terms:
  - `CSRF`
- Related Terms:
  - `XSS`
- Level: 3
- Track: B

### 採点

Score: 55 / 100
""",
                1,
            )
            self.assertEqual(study_helper.EXPLANATION_MODE, questions[0].question_mode)

    def test_暗記語句の記録は冪等でモード別得点を保つ(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "references").mkdir()
            (root / "progress").mkdir()
            (root / "sessions" / "暗記語句問題").mkdir(parents=True)
            shutil.copy(self.root / "参照資料" / "出題分類と概念カタログ.md", root / "references" / "taxonomy.md")
            (root / "progress" / "terms.md").write_text(
                study_helper.render_terms({}), encoding="utf-8"
            )
            shutil.copy(self.root / "進捗" / "分野別理解度.md", root / "progress" / "domains.md")
            (root / "progress" / "history.md").write_text(
                study_helper.render_history([]), encoding="utf-8"
            )
            session_path = root / "sessions" / "暗記語句問題" / "2026-08-12.md"
            session_path.write_text(
                """# 2026-08-12 セキスペ学習

## Session 1

- Created: 2026-08-12
- Status: grading
- Mode: term-recall
- Question Count: 1
- Track A/B Target: 40% / 60%

### Q1

- Domain: Webセキュリティ
- Primary Terms:
  - `CSRF`
- Related Terms:
  - `CSRFトークン`
- Level: 1
- Track: B

### 問題

CSRFとは何ですか？

### 回答

ほとんど説明できなかった。

### 採点

Score: 20 / 100

#### 良かった点

- Cookieに関係する攻撃だと認識した

#### 次回確認する観点

- 被害者ブラウザによる意図しない認証付きリクエスト
""",
                encoding="utf-8",
            )

            first = study_helper.record_progress(
                root, date(2026, 8, 12), 1, study_helper.TERM_RECALL_MODE
            )
            second = study_helper.record_progress(
                root, date(2026, 8, 12), 1, study_helper.TERM_RECALL_MODE
            )
            record = study_helper.load_terms(root)["CSRF"]
            history = study_helper.read_table(root / "progress" / "history.md", "Date")
            self.assertEqual(first["average"], second["average"])
            self.assertEqual(1, record.attempts)
            self.assertEqual(1, record.recall_attempts)
            self.assertEqual(0, record.explanation_attempts)
            self.assertEqual(20, record.recall_score)
            self.assertIsNone(record.explanation_score)
            self.assertEqual(20, record.score)
            self.assertEqual(date(2026, 8, 13), record.next_review)
            self.assertEqual(1, len(history))
            self.assertIn(
                "../sessions/暗記語句問題/2026-08-12.md#session-1",
                history[0]["Session File"],
            )

    def test_セッション保存先をモード別に分け連番を共有する(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            standard = root / "sessions" / "理解・応用問題"
            recall = root / "sessions" / "暗記語句問題"
            standard.mkdir(parents=True)
            recall.mkdir(parents=True)
            standard_path = standard / "2026-08-12.md"
            recall_path = recall / "2026-08-12.md"
            standard_path.write_text(
                "## Session 1\n\n- Status: graded\n- Mode: adaptive\n",
                encoding="utf-8",
            )
            recall_path.write_text(
                "## Session 2\n\n- Status: awaiting_answers\n- Mode: term-recall\n",
                encoding="utf-8",
            )

            self.assertEqual(
                standard_path,
                study_helper.session_path_for_mode(root, date(2026, 8, 12), "standard"),
            )
            self.assertEqual(
                recall_path,
                study_helper.session_path_for_mode(
                    root, date(2026, 8, 12), study_helper.TERM_RECALL_MODE
                ),
            )
            self.assertEqual(3, study_helper.next_session_number(root, date(2026, 8, 12)))
            self.assertEqual(
                recall_path,
                study_helper.resolve_session_path(
                    root, date(2026, 8, 12), 2, study_helper.TERM_RECALL_MODE
                ),
            )
            standard_path.write_text(
                standard_path.read_text(encoding="utf-8")
                + "\n## Session 2\n\n- Status: graded\n- Mode: adaptive\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "exists in multiple files"):
                study_helper.resolve_session_path(
                    root, date(2026, 8, 12), 2, study_helper.TERM_RECALL_MODE
                )

    def test_旧直下セッションを読み取れる(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "sessions").mkdir()
            legacy = root / "sessions" / "2026-08-12.md"
            legacy.write_text(
                "## Session 1\n\n- Status: graded\n- Mode: adaptive\n",
                encoding="utf-8",
            )
            self.assertEqual(
                legacy,
                study_helper.resolve_session_path(root, date(2026, 8, 12), 1),
            )
            self.assertEqual(2, study_helper.next_session_number(root, date(2026, 8, 12)))

    def test_旧英語ディレクトリのセッションを読み取れる(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            standard_dir = root / "sessions" / "standard"
            recall_dir = root / "sessions" / "term-recall"
            standard_dir.mkdir(parents=True)
            recall_dir.mkdir(parents=True)
            standard = standard_dir / "2026-08-12.md"
            recall = recall_dir / "2026-08-12.md"
            standard.write_text(
                "## Session 1\n\n- Status: graded\n- Mode: adaptive\n",
                encoding="utf-8",
            )
            recall.write_text(
                "## Session 2\n\n- Status: graded\n- Mode: term-recall\n",
                encoding="utf-8",
            )

            self.assertEqual(
                standard,
                study_helper.resolve_session_path(root, date(2026, 8, 12), 1),
            )
            self.assertEqual(
                recall,
                study_helper.resolve_session_path(
                    root, date(2026, 8, 12), 2, study_helper.TERM_RECALL_MODE
                ),
            )
            self.assertEqual(3, study_helper.next_session_number(root, date(2026, 8, 12)))

    def test_記録処理は冪等で翌日の計画へ反映される(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "references").mkdir()
            (root / "progress").mkdir()
            (root / "sessions").mkdir()
            shutil.copy(self.root / "参照資料" / "出題分類と概念カタログ.md", root / "references" / "taxonomy.md")
            (root / "progress" / "terms.md").write_text(
                study_helper.render_terms({}), encoding="utf-8"
            )
            shutil.copy(self.root / "進捗" / "分野別理解度.md", root / "progress" / "domains.md")
            (root / "progress" / "history.md").write_text(
                study_helper.render_history([]), encoding="utf-8"
            )
            session_path = root / "sessions" / "2026-08-09.md"
            session_path.write_text(
                """# 2026-08-09 セキスペ学習

## Session 1

- Created: 2026-08-09
- Status: grading
- Mode: diagnosis
- Question Count: 3
- Subject B Target: 70–85%

### Q1

- Domain: PKI・証明書
- Primary Terms:
  - `CRL / OCSP`
- Related Terms:
  - `証明書失効`
- Level: 3
- Track: B

<!-- CRLとOCSPを比較してください。 -->

### 回答

回答済み。

### 採点

Score: 45 / 100

#### 良かった点

- 失効確認という目的は説明できた

#### 次回確認する観点

- pull型と問い合わせ方式の違い

### Q2

- Domain: リスク・ガバナンス
- Primary Terms:
  - `リスク対応`
- Related Terms:
  - `リスク受容`
- Level: 2
- Track: A/B

<!-- リスク対応を説明してください。 -->

### 回答

回答済み。

### 採点

Score: 100 / 100

#### 良かった点

- 四つの対応を区別できた

#### 次回確認する観点

- 残存リスクの承認

### Q3

- Domain: リスク・ガバナンス
- Primary Terms:
  - `独自A概念`
- Related Terms:
  - `リスク対応`
- Level: 2
- Track: A

<!-- 独自A概念を説明してください。 -->

### 回答

回答済み。

### 採点

Score: 70 / 100

#### 良かった点

- 基本を説明できた

#### 次回確認する観点

- 応用例
""",
                encoding="utf-8",
            )

            _, parsed_questions = study_helper.parse_graded_session(
                session_path.read_text(encoding="utf-8"), 1
            )
            partial_records = study_helper.update_term_records(
                root,
                date(2026, 8, 9),
                1,
                parsed_questions,
                study_helper.load_catalog(root),
            )
            self.assertEqual(1, partial_records["CRL / OCSP"].attempts)
            self.assertIn("- Status: grading", session_path.read_text(encoding="utf-8"))
            self.assertEqual([], study_helper.read_table(root / "progress" / "history.md", "Date"))

            first = study_helper.record_progress(root, date(2026, 8, 9), 1)
            records = study_helper.load_terms(root)
            self.assertEqual(3, first["questions"])
            self.assertIn("- Status: graded", session_path.read_text(encoding="utf-8"))
            self.assertEqual({"CRL / OCSP", "リスク対応", "独自A概念"}, set(records))
            self.assertEqual("A", records["独自A概念"].track)
            self.assertEqual(45, records["CRL / OCSP"].last_score)
            self.assertEqual("2026-08-09#1", records["CRL / OCSP"].last_session)
            self.assertEqual(("2026-08-09#1",), records["CRL / OCSP"].applied_sessions)
            self.assertEqual(1, records["CRL / OCSP"].attempts)

            second = study_helper.record_progress(root, date(2026, 8, 9), 1)
            records_after_retry = study_helper.load_terms(root)
            history = study_helper.read_table(root / "progress" / "history.md", "Date")
            self.assertEqual(first["average"], second["average"])
            self.assertEqual(1, records_after_retry["CRL / OCSP"].attempts)
            self.assertEqual(1, len(history))
            self.assertEqual(0o644, (root / "progress" / "terms.md").stat().st_mode & 0o777)

            catalog = study_helper.merge_uncatalogued_terms(
                study_helper.load_catalog(root), records_after_retry
            )
            candidates = study_helper.build_candidates(
                catalog,
                records_after_retry,
                date(2026, 8, 10),
                study_helper.recent_domain_counts(root),
            )
            plan = study_helper.adaptive_plan(candidates, 5)
            self.assertIn("CRL / OCSP", {candidate.item.term for _, candidate in plan})


if __name__ == "__main__":
    unittest.main()
