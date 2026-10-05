"""Tests for the stages that need no model: parse, chunk, name keys and sets.

  .venv/bin/python -m unittest discover tests
"""

import tempfile
import unittest
from pathlib import Path

from bookgraph import chunk, parse, resolve

FB2 = """<?xml version="1.0" encoding="utf-8"?>
<FictionBook xmlns="http://www.gribuser.ru/xml/fictionbook/2.0">
 <description><title-info>
  <author><first-name>Ann</first-name><home-page>https://x</home-page><id>7</id></author>
  <book-title>Книга</book-title>
  <annotation><p><strong>Предупреждение.</strong></p><p>***</p><p>Про героя.</p></annotation>
  <lang>ru</lang>
 </title-info></description>
 <body>
  <section><title><p>Часть 1</p></title>
   <p>Вступление.</p>
   <section><title><p>Глава 1</p></title>
    <p>Раз <emphasis>два</emphasis>.</p><p>* * *</p><p>Три.</p>
   </section>
   <section><title><p>Глава 2</p></title>
    <poem><stanza><v>Строка</v></stanza></poem><empty-line/><p></p><p>Конец.</p>
   </section>
  </section>
 </body>
 <body name="notes"><section><p>Сноска</p></section></body>
</FictionBook>"""


class Parse(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        path = Path(self.dir.name) / "kniga-b123.fb2"
        path.write_text(FB2, encoding="utf-8")
        self.book = parse.parse(path)

    def tearDown(self):
        self.dir.cleanup()

    def test_metadata(self):
        self.assertEqual(self.book["book"], "kniga")
        self.assertEqual(self.book["author"], "Ann")
        # The all-bold notice and the asterisks are dropped.
        self.assertEqual(self.book["annotation"], "Про героя.")

    def test_chapters_and_scenes(self):
        titles = [c["title"] for c in self.book["chapters"]]
        self.assertEqual(titles, ["Часть 1", "Часть 1 / Глава 1", "Часть 1 / Глава 2"])
        ch1 = self.book["chapters"][1]
        self.assertEqual(ch1["scenes"], [["Раз два."], ["Три."]])
        self.assertEqual(self.book["chapters"][2]["scenes"], [["Строка", "Конец."]])

    def test_notes_body_ignored(self):
        text = str(self.book["chapters"])
        self.assertNotIn("Сноска", text)


class Chunk(unittest.TestCase):
    def test_one_chunk_when_small(self):
        self.assertEqual(chunk.chunk_chapter([["a" * 10], ["b" * 10]], 1000),
                         ["a" * 10 + "\n\n***\n\n" + "b" * 10])

    def test_cuts_land_on_scene_breaks(self):
        # Two scenes of 600 chars in 10 paragraphs each, limit 700: two
        # chunks, and the cut is the scene break, not a paragraph near it.
        scenes = [["x" * 58] * 10, ["y" * 58] * 10]
        out = chunk.chunk_chapter(scenes, 700)
        self.assertEqual(len(out), 2)
        self.assertNotIn("y", out[0])
        self.assertNotIn("x", out[1])

    def test_long_scene_is_cut_between_paragraphs(self):
        out = chunk.chunk_chapter([["p" * 100] * 30], 1000)
        self.assertEqual(len(out), 4)
        self.assertTrue(all(len(c) <= 1300 for c in out))
        self.assertEqual(sum(c.count("p") for c in out), 3000)


class Names(unittest.TestCase):
    def test_case_forms_share_a_key(self):
        self.assertEqual(resolve.key("Жона Арка"), resolve.key("Жон Арк"))
        self.assertEqual(resolve.key("Белого Клыка"), "белый клык")

    def test_invented_names_share_a_stem(self):
        for a, b in (("Ансель", "Ансел"), ("Озпина", "Озпин"), ("Бикона", "Бикон")):
            self.assertEqual(resolve.stem(resolve.key(a)), resolve.stem(resolve.key(b)), (a, b))

    def test_aliases(self):
        self.assertTrue(resolve.is_alias("Жон-Жон", "Жон Арк"))
        self.assertFalse(resolve.is_alias("братец", "Жон Арк"))
        self.assertFalse(resolve.is_alias("Капитан", "Жон Арк"))
        self.assertFalse(resolve.is_alias("Жон Арк", "Жон Арк"))

    def test_candidate_sets_are_capped(self):
        # Fifty relatives share the surname; each has a first-name variant.
        groups = {}
        for i in range(50):
            first = f"Имяокс{chr(0x430 + i % 32)}{chr(0x430 + i // 32)}"
            for name in (f"{first} Арк", first):
                groups[resolve.key(name)] = {"forms": {name}, "names": {}, "about": [], "chunks": []}
        sets = resolve.candidate_sets(groups)
        self.assertTrue(all(len(s) <= resolve.MAX_SET for s in sets))
        # Each person's two forms stay together after the surname stops linking.
        together = {frozenset(s) for s in sets}
        self.assertIn(frozenset({resolve.key("Имяоксаа Арк"), resolve.key("Имяоксаа")}), together)


if __name__ == "__main__":
    unittest.main()


class SiteMarkdown(unittest.TestCase):
    def setUp(self):
        from bookgraph.site import Site

        self.site = Site.__new__(Site)
        self.site.by_name = {"Жон Арк": "Персонажи/Жон Арк", "Глава 1": "Главы/Глава 1"}

    def test_wikilinks_and_emphasis(self):
        out = self.site.inline("**[[Жон Арк]]** и [[Глава 1#^ch001-01-e02|обед]] с [[Никто]] <b>", 1)
        self.assertEqual(out, '<strong><a href="../%D0%9F%D0%B5%D1%80%D1%81%D0%BE%D0%BD%D0%B0%D0%B6%D0%B8/'
                              '%D0%96%D0%BE%D0%BD%20%D0%90%D1%80%D0%BA.html">Жон Арк</a></strong> и '
                              '<a href="../%D0%93%D0%BB%D0%B0%D0%B2%D1%8B/%D0%93%D0%BB%D0%B0%D0%B2%D0%B0%201.html'
                              '#ch001-01-e02">обед</a> с Никто &lt;b&gt;')

    def test_nested_list_with_block_id(self):
        md = "---\ntype: x\n---\n# T\n\n- Обед — ссора ^ch001-01-e02\n\t- [[Жон Арк]]\n- Второе\n\nТекст"
        out = self.site.body(md, 0).replace("\n", "")
        self.assertIn('<li id="ch001-01-e02">Обед — ссора<ul><li>', out)
        self.assertIn("</li></ul></li><li>Второе</li></ul><p>Текст</p>", out)
        self.assertNotIn("type: x", out)


class Fix(unittest.TestCase):
    def test_respell_keeps_endings_and_merges(self):
        from bookgraph import fix

        pats = fix.patterns([("Джон", "Жон")])
        n = [0]
        data = {"aliases": ["Жоном", "Джоном", "Аджонов"], "what": "Джону Арку и Джонс, не Джонатан Ли",
                "index": {"characters:джон арк": "c1", "characters:жон арк": "c1"},
                "scenes": [["* * *", "* * *"]]}
        out = fix.respell(data, pats, n)
        self.assertEqual(out["aliases"], ["Жоном", "Аджонов"])
        self.assertEqual(out["what"], "Жону Арку и Жонс, не Жонатан Ли")
        self.assertEqual(out["index"], {"characters:жон арк": "c1"})
        self.assertEqual(out["scenes"], [["* * *", "* * *"]])
        self.assertEqual(n[0], 5)
