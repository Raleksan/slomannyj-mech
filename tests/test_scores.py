"""Tests for the gold measures on small cases worked out by hand.

  .venv/bin/python -m unittest discover tests
"""

import math
import unittest

from bookgraph import gold, scores

KEY = [{"a", "b", "c"}, {"d"}]
RESPONSE = [{"a", "b"}, {"c", "d"}]


class Coreference(unittest.TestCase):
    def check(self, got, want):
        for g, w in zip(got, want):
            self.assertAlmostEqual(g, w, places=4)

    def test_muc(self):
        self.check(scores.muc(KEY, RESPONSE), (0.5, 0.5, 0.5))

    def test_b_cubed(self):
        self.check(scores.b_cubed(KEY, RESPONSE), (0.75, 2 / 3, 2 * 0.75 * (2 / 3) / (0.75 + 2 / 3)))

    def test_ceaf_e(self):
        best = 0.8 + 2 / 3
        self.check(scores.ceaf_e(KEY, RESPONSE), (best / 2, best / 2, best / 2))

    def test_lea(self):
        # Recall: {a,b,c} resolves 1 of 3 links; {d} is not a response singleton.
        # Precision: {a,b} resolves its 1 link; {c,d} resolves none.
        self.check(scores.lea(KEY, RESPONSE), (0.5, 0.25, 1 / 3))

    def test_identical_clusterings_score_one(self):
        for fn in (scores.muc, scores.b_cubed, scores.ceaf_e, scores.lea):
            self.assertAlmostEqual(fn(KEY, KEY)[2], 1.0)

    def test_clusters_from_pairs(self):
        got = scores.clusters_of(["a", "b", "c", "d"], [("a", "b"), ("b", "c")])
        self.assertEqual(sorted(map(sorted, got)), [["a", "b", "c"], ["d"]])


class Assignment(unittest.TestCase):
    def test_square(self):
        self.assertAlmostEqual(scores.assignment([[0.2, 0.9], [0.8, 0.1]]), 1.7)

    def test_rectangular(self):
        self.assertAlmostEqual(scores.assignment([[1, 2, 3]]), 3)
        self.assertAlmostEqual(scores.assignment([[1], [5], [2]]), 5)


class Statistics(unittest.TestCase):
    def test_kappa(self):
        self.assertEqual(scores.kappa([("x", "x"), ("y", "y")]), 1.0)
        self.assertAlmostEqual(scores.kappa([("x", "x"), ("x", "y"), ("y", "x"), ("y", "y")]), 0.0)

    def test_ndcg(self):
        self.assertAlmostEqual(scores.ndcg(["a", "b", "c"], ["a", "b", "c"], 3), 1.0)
        self.assertLess(scores.ndcg(["a", "b", "c"], ["c", "b", "a"], 3), 1.0)

    def test_interval_brackets_the_value(self):
        items = [1] * 70 + [0] * 30
        r = scores.rate(items, scores.mean)
        self.assertEqual(r["value"], 0.7)
        self.assertLess(r["low"], 0.7)
        self.assertGreater(r["high"], 0.7)

    def test_empty_interval(self):
        self.assertTrue(math.isnan(scores.interval([], scores.mean)[0]))


class Import(unittest.TestCase):
    def test_answer_fields(self):
        result = [
            {"from_name": "verdict", "type": "choices", "value": {"choices": ["same"]}},
            {"from_name": "features", "type": "choices", "value": {"choices": ["decision"]}},
            {"from_name": "note", "type": "textarea", "value": {"text": ["Озпин — директор"]}},
            {"from_name": "rank", "type": "ranker", "value": {"ranker": {"top": ["e2", "e1"]}}},
        ]
        self.assertEqual(gold.answer(result), {"verdict": "same", "features": ["decision"],
                                               "note": "Озпин — директор",
                                               "rank": {"top": ["e2", "e1"]}})

    def test_task_of(self):
        self.assertEqual(gold.task_of("alias-0007"), "alias")


if __name__ == "__main__":
    unittest.main()
