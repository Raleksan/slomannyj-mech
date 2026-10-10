"""Tests for the silver set: prompts, schemas and answers, with a stand-in model.

  .venv/bin/python -m unittest discover tests
"""

import asyncio
import unittest

from pydantic import ValidationError

from bookgraph import scores, silver

PLACE = {"event": "e1", "where_text": "Коридоры Бикона", "run": None, "gid": "place-0001",
         "card": "<div><b>Драка</b></div>", "context": '<div><p><b>ch001.p0001</b> Раз.</p>'
         '<p style="background:#fff3c4"><b>ch001.p0002</b> Два &amp; три.</p></div>',
         "options": [{"value": "p0001 Бикон"}, {"value": "none: no such place listed"}]}
COMPARE = {"a": "e1", "b": "e2", "a_html": "<div>первое</div>", "b_html": "<div>второе</div>",
           "gid": "compare-0001"}


class Fake:
    """Answers each schema with what the test hands it, in order."""

    def __init__(self, answers):
        self.answers = list(answers)
        self.prompts = []

    async def ask(self, model, system, user, *, kind, max_tokens):
        self.prompts.append((system, user, kind))
        return model.model_validate(self.answers.pop(0))


class Silver(unittest.TestCase):
    def test_plain_marks_the_highlight(self):
        self.assertEqual(silver.plain(PLACE["context"]), "ch001.p0001 Раз.\n► ch001.p0002 Два & три.")

    def test_guide_has_the_rules_and_rulings(self):
        text = silver.guide("alias")
        self.assertIn("## Aliases", text)
        self.assertIn("## Your rulings", text)
        self.assertIn("Эхо Горького Сна", text)
        self.assertNotIn("## Links", text)

    def test_place_answer_must_be_an_option(self):
        model = silver.schema("place", PLACE)
        ok = model.model_validate({"why": "x", "place": "p0001 Бикон", "relation": "inside"})
        self.assertEqual(ok.place, "p0001 Бикон")
        with self.assertRaises(ValidationError):
            model.model_validate({"why": "x", "place": "Бикон"})

    def test_answer_row_fields_match_the_hand_answers(self):
        fake = Fake([{"why": "в тексте", "place": "p0001 Бикон", "relation": "inside"}])
        got = asyncio.run(silver.answer(fake, "place", PLACE))
        self.assertEqual((got["place"], got["relation"]), ("p0001 Бикон", "inside"))
        self.assertEqual(fake.prompts[0][2], "judge")
        self.assertIn("## Event places", fake.prompts[0][0])

    def test_compare_both_orders(self):
        # A wins, then (swapped) B wins: the same event both times.
        fake = Fake([{"why": "1", "winner": "A"}, {"why": "2", "winner": "B"}])
        got = asyncio.run(silver.answer(fake, "compare", COMPARE))
        self.assertEqual((got["winner"], got["orders"]), ("A", ["A", "A"]))
        self.assertIn("первое", fake.prompts[1][1].split("=== B")[1])
        # A wins both times: the order decided it, not the events.
        fake = Fake([{"why": "1", "winner": "A"}, {"why": "2", "winner": "A"}])
        got = asyncio.run(silver.answer(fake, "compare", COMPARE))
        self.assertEqual((got["winner"], got["orders"]), ("uncertain", ["A", "B"]))

    def test_every_task_has_a_prompt_and_schema(self):
        self.assertEqual(set(silver.TASKS), set(scores.AGREE))
        self.assertEqual(set(silver.TASKS), set(silver.SECTIONS))


if __name__ == "__main__":
    unittest.main()
