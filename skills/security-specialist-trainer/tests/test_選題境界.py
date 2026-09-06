from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path
import random
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from trainer.common import Candidate, CatalogItem, TermRecord, base_interval
from trainer.planner import adaptive_plan, build_candidates, planned_track


class 選題境界テスト(unittest.TestCase):
    today = date(2026, 9, 6)

    def 候補(self, name, track, priority, kind):
        item = CatalogItem(name, name, track, 3, 2, False, "", "")
        return Candidate(item, priority, 20 if kind == "weak" else 0, 0,
                         kind == "new", kind == "due", kind == "challenge", 2, "")

    def 記録(self, mode, score):
        record = TermRecord("TLS", "暗号", 90, self.today - timedelta(days=1),
                            2, 90, 4, None, "", "")
        prefix = "recall" if mode == "term-recall" else "explanation"
        return replace(record, **{prefix + "_score": score,
                                  prefix + "_attempts": 1,
                                  prefix + "_last_studied": self.today - timedelta(days=1)})

    def test_零点も自己モードの復習間隔を使う(self):
        item = CatalogItem("TLS", "暗号", "B", 3, 2, False, "", "")
        for mode in ("standard", "term-recall"):
            with self.subTest(mode=mode):
                candidate = build_candidates([item], {"TLS": self.記録(mode, 0)}, self.today, {}, mode=mode)[0]
                self.assertEqual(35.0, candidate.forgetting)
                self.assertTrue(candidate.due)
                self.assertFalse(candidate.unseen)

    def test_全ての得点境界で自己モードの間隔を使う(self):
        item = CatalogItem("TLS", "暗号", "B", 3, 2, False, "", "")
        for mode in ("standard", "term-recall"):
            for score in (0, 1, 39, 40, 59, 60, 74, 75, 89, 90, 100):
                with self.subTest(mode=mode, score=score):
                    candidate = build_candidates([item], {"TLS": self.記録(mode, score)}, self.today, {}, mode=mode)[0]
                    self.assertAlmostEqual(35 / base_interval(score), candidate.forgetting)

    def test_未評価と零点を区別する(self):
        item = CatalogItem("TLS", "暗号", "B", 3, 2, False, "", "")
        for mode in ("standard", "term-recall"):
            with self.subTest(mode=mode):
                candidate = build_candidates([item], {"TLS": self.記録(mode, None)}, self.today, {}, mode=mode)[0]
                self.assertTrue(candidate.unseen)
                self.assertEqual(0, candidate.weakness)

    def 配分候補(self, excessive=False):
        return [self.候補("弱点一", "B", 100, "weak"),
                self.候補("弱点二", "B", 90, "weak"),
                self.候補("期限", "B", 80, "due"),
                self.候補("新規一", "B", 70, "new"),
                self.候補("新規二", "B" if excessive else "A", 60, "new"),
                self.候補("発展", "B" if excessive else "A", 0, "challenge"),
                self.候補("代替新規", "A" if excessive else "B", 1, "new")]

    def test_科目配分を増やす際も実際の新規数と挑戦数を保つ(self):
        plan = adaptive_plan(self.配分候補(), 6)
        self.assertEqual(5, sum(c.item.track == "B" for _, c in plan))
        self.assertEqual(2, sum(c.unseen for _, c in plan))
        self.assertEqual(1, sum(c.challenge for _, c in plan))

    def test_科目配分を減らす際も実際の新規数と挑戦数を保つ(self):
        plan = adaptive_plan(self.配分候補(True), 6)
        self.assertEqual(5, sum(c.item.track == "B" for _, c in plan))
        self.assertEqual(2, sum(c.unseen for _, c in plan))
        self.assertEqual(1, sum(c.challenge for _, c in plan))

    def test_両立できない配分を元の区分に偽装しない(self):
        candidates = self.配分候補()
        candidates[2] = replace(candidates[2], item=replace(candidates[2].item, track="A"))
        candidates[4] = replace(candidates[4], item=replace(candidates[4].item, track="B"))
        plan = adaptive_plan(candidates, 6)
        self.assertEqual(5, sum(c.item.track == "B" for _, c in plan))
        self.assertTrue(any(label == "配分補完" for label, _ in plan))
        self.assertTrue(all(c.challenge for label, c in plan if label == "発展"))

    def test_問題数と科目比率と重複排除が両立する(self):
        for seed in range(5):
            rng = random.Random(seed)
            candidates = [self.候補(f"候補{i}", "A" if i < 30 else "B",
                                    rng.random() * 100, ("weak", "due", "new", "challenge")[i % 4])
                          for i in range(60)]
            for count in range(1, 31):
                for mode in ("standard", "term-recall"):
                    with self.subTest(seed=seed, count=count, mode=mode):
                        plan = adaptive_plan(candidates, count, mode)
                        self.assertEqual(count, len(plan))
                        self.assertEqual(count, len({c.item.term for _, c in plan}))
                        b_count = sum(planned_track(c, mode) == "B" for _, c in plan)
                        if mode == "term-recall":
                            self.assertEqual(count - int(count * .4), b_count)
                        elif count >= 4:
                            self.assertGreaterEqual(b_count / count, .70)
                            self.assertLessEqual(b_count / count, .85)
                        matches = {"弱点": lambda c: not c.unseen and c.weakness >= 13.5,
                                   "復習期": lambda c: not c.unseen and c.due,
                                   "新規": lambda c: c.unseen,
                                   "発展": lambda c: c.challenge,
                                   "定着確認": lambda c: c.challenge}
                        self.assertTrue(all(matches[label](c) for label, c in plan if label in matches))

    def test_空候補と候補不足でも停止し重複しない(self):
        self.assertEqual([], adaptive_plan([], 6))
        candidate = self.候補("唯一", "A", 1, "new")
        for mode in ("standard", "term-recall"):
            plan = adaptive_plan([candidate], 30, mode)
            self.assertEqual(1, len(plan))

    def test_同じ入力から同じ選定結果を得る(self):
        candidates = self.配分候補()
        self.assertEqual(adaptive_plan(candidates, 6), adaptive_plan(candidates, 6))


if __name__ == "__main__":
    unittest.main()
