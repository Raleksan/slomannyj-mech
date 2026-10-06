"""Tests for the request body each kind of model call sends.

  .venv/bin/python -m unittest discover tests
"""

import unittest

from pydantic import BaseModel

from bookgraph import llm


class Answer(BaseModel):
    ok: bool


class Request(unittest.TestCase):
    def test_every_kind_sets_its_own_sampling(self):
        for kind, opts in llm.SETTINGS.items():
            body = llm.request(Answer, "sys", "user", kind=kind, max_tokens=100)
            self.assertEqual(body["temperature"], opts["temperature"])
            self.assertEqual(body["top_p"], opts["top_p"])
            self.assertEqual(body["top_k"], 20)
            self.assertEqual(body["seed"], llm.SEED)
            self.assertEqual(body["chat_template_kwargs"]["enable_thinking"], opts["think"])

    def test_thinking_is_never_greedy(self):
        for opts in llm.SETTINGS.values():
            if opts["think"]:
                self.assertGreaterEqual(opts["temperature"], 0.6)

    def test_unknown_kind_fails(self):
        with self.assertRaises(KeyError):
            llm.request(Answer, "sys", "user", kind="guess", max_tokens=100)


if __name__ == "__main__":
    unittest.main()
