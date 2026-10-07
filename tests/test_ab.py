"""Tests for the model A/B comparison.

  .venv/bin/python -m unittest discover tests
"""

import unittest

from bookgraph import ab


def facts(*names, events=1):
    return {"summary": "", "characters": [{"name": n} for n in names],
            "events": [{"importance": 3}] * events}


class Measure(unittest.TestCase):
    def test_counts_refusals_failures_and_empty_answers(self):
        rows = [
            {"chunk": "c1", "facts": facts("Жон Арк"), "seconds": 10, "tokens": 100},
            {"chunk": "c2", "facts": facts("Жон Арк", events=0), "seconds": 10, "tokens": 50},
            {"chunk": "c3", "error": "no valid answer; last: 'Извините, я не могу помочь'", "seconds": 5},
            {"chunk": "c4", "error": "no valid answer; last: '{\"events\": [", "seconds": 5},
        ]
        m = ab.measure(rows, {"c1": facts("Жон Арк", "Руби")})
        self.assertEqual((m["chunks"], m["failed"], m["refused"], m["no events"]), (4, 2, 1, 1))
        self.assertEqual(m["same names as the run"], "50%")
        self.assertEqual(m["generated tokens"], 100)
        self.assertEqual(m["tokens / s"], 10.0)


if __name__ == "__main__":
    unittest.main()
