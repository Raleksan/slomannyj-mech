"""Tests for the author's glossary: parsing its lines and looking names up.

  .venv/bin/python -m unittest discover tests
"""

import tempfile
import unittest
from pathlib import Path

from bookgraph import glossary, gold

FB2 = """<?xml version="1.0" encoding="utf-8"?>
<FictionBook xmlns="http://www.gribuser.ru/xml/fictionbook/2.0">
 <description><title-info><book-title>Справочник</book-title><lang>ru</lang></title-info></description>
 <body>
  <section><title><p>Глоссарий: Арки</p></title>
   <p>(Эмблема Арков)</p>
   <p>Жон Арк (62 год Э.В.) — Главный Герой.</p>
   <p>Майра и Николь Арк (67 год Э.В.) — близняшки.</p>
   <p>Прошлое поколение семьи Арк:</p>
   <p>Жон Арк (Пьяница) (616 год Э.К. – 655 год Э.К.) — старший сын Гарольда Арка.</p>
  </section>
  <section><title><p>Глоссарий: Другие Персонажи</p></title>
   <p>Ансель:</p>
   <p>Хейли Арк (Последний Дюрфор) — директор школы.</p>
   <p>Старейшина Аяме — мать Азэми.</p>
   <p>Бранан — лесоруб.</p>
   <p>Команда ASRB: Аш Сильвер, Гарнет Стронг.</p>
   <p>(Современный герб Вейла)</p>
   <p>Кроу Бранвен — охотник Вейла.</p>
  </section>
  <section><title><p>Глоссарий: Бикон</p></title>
   <p>Ученики:</p>
   <p>Команда JRNC (Jewel Renaissance — Драгоценное Возрождение):</p>
   <p>Жон Арк (лидер).</p>
   <p>Слабые Точки/Победа — видит уязвимости.</p>
   <p>Керри Мортис.</p>
   <p>Фантомная Нить</p>
   <p>— невидимые нити.</p>
   <p>Хозяин серого волка по имени Громобой.</p>
   <p>Первый Курс (на момент осени 80 г. Э.В.).</p>
   <p>Аква — лидер своей команды.</p>
  </section>
  <section><title><p>Глоссарий: Эхо Горького Сна</p></title>
   <p>Подавляющая часть персонажей является теми же персонажами, если вы хотите узнать, кто есть кто — идите в комментарии.</p>
   <p>Палач/Злобоглазый (ᚾᛖᚹᚢᚾ!) — основатель Легиона.</p>
   <p>[Фульмита — тайное подразделение Легиона]</p>
   <p>Железноногий — Верховный Фульмитарий.</p>
  </section>
  <section><title><p>Дополнительная Информация</p></title>
   <p>Хронология Произведения:</p>
   <p>1 Глава — 71 год Эпохи Витала.</p>
   <p>2-6 Главы — 74 год Эпохи Витала.</p>
  </section>
 </body>
</FictionBook>"""


class Parse(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "spravochnik.fb2"
            path.write_text(FB2, encoding="utf-8")
            cls.data = glossary.parse_lines(glossary.read_sections(path))
        cls.by = {}
        for e in cls.data["entries"]:
            cls.by.setdefault(e["name"], []).append(e)

    def test_names_years_and_eras(self):
        jon, drunk = self.by["Жон Арк"]
        self.assertEqual((jon["era"], drunk["era"]), ("ЭВ", "ЭК"))
        self.assertEqual(drunk["epithets"], ["Пьяница"])
        self.assertIn("Жон Пьяница", drunk["forms"])
        self.assertEqual(drunk["group"], "Прошлое поколение семьи Арк")
        self.assertIsNone(jon["group"])

    def test_two_people_on_one_line(self):
        self.assertIn("Майра Арк", self.by)
        self.assertEqual(self.by["Николь Арк"][0]["text"], "близняшки.")

    def test_titles_and_groups(self):
        self.assertIn("Аяме", self.by["Старейшина Аяме"][0]["forms"])
        self.assertEqual(self.by["Хейли Арк"][0]["group"], "Ансель")
        # A coat of arms starts another kingdom: Кроу is not from Ансель.
        self.assertIsNone(self.by["Кроу Бранвен"][0]["group"])

    def test_teams(self):
        asrb = self.by["Команда ASRB"][0]
        self.assertEqual(asrb["members"], ["Аш Сильвер", "Гарнет Стронг"])
        self.assertEqual(self.by["Аш Сильвер"][0]["team"], "Команда ASRB")
        jrnc = self.by["Команда JRNC"][0]
        self.assertEqual(jrnc["members"], ["Жон Арк", "Керри Мортис"])
        # The student is the Arcs' Жон, not a third «Жон Арк».
        self.assertEqual(len(self.by["Жон Арк"]), 2)
        self.assertEqual(self.by["Жон Арк"][0]["team"], "Команда JRNC")
        self.assertTrue(self.by["Жон Арк"][0]["semblance"].startswith("Слабые Точки/Победа"))
        kerry = self.by["Керри Мортис"][0]
        self.assertEqual(kerry["semblance"], "Фантомная Нить — невидимые нити.")
        self.assertIn("Громобой", kerry["text"])
        self.assertEqual(self.by["Аква"][0]["group"], "Первый Курс (на момент осени 80 г. Э.В.)")

    def test_echo(self):
        self.assertNotIn("Подавляющая часть персонажей является теми же персонажами, если вы хотите "
                         "узнать, кто есть кто", self.by)
        palach = self.by["Палач"][0]
        self.assertEqual(palach["world"], "echo")
        self.assertEqual(palach["forms"], ["Палач", "Злобоглазый"])
        self.assertEqual(self.by["Фульмита"][0]["kind"], "unit")
        self.assertEqual(self.by["Железноногий"][0]["group"], "Фульмита")
        self.assertEqual(self.by["Жон Арк"][0]["world"], "main")

    def test_chronology(self):
        self.assertEqual(self.data["chronology"],
                         [{"from": 1, "to": 1, "when": "71 год Эпохи Витала."},
                          {"from": 2, "to": 6, "when": "74 год Эпохи Витала."}])

    def test_lookup(self):
        def names(q, least=2):
            return [e["name"] for _, e in glossary.lookup(self.data, q, least)]

        self.assertEqual(names("Хейль"), ["Хейли Арк"])  # the run's respelling
        self.assertEqual(names("Аяме Ноэда"), ["Старейшина Аяме"])
        self.assertEqual(names("Бранвен"), ["Кроу Бранвен"])  # not «Бранан»
        self.assertEqual(names("Жон Пьяница"), ["Жон Арк"])
        self.assertEqual(glossary.lookup(self.data, "Жон Пьяница")[0][1]["era"], "ЭК")
        self.assertTrue(glossary.same_word("арком", "арк"))
        self.assertFalse(glossary.same_word("бранвен", "бранан"))

    def test_alias_task_panel(self):
        task = {"kind": "characters", "a": "Хейль", "b": "Никто Никтович", "stratum": "merged",
                "a_html": "<h3>Хейль</h3><p>x</p>", "b_html": "<h3>Никто Никтович</h3>", "gid": "alias-0001"}
        once = gold.with_glossary(dict(task), self.data)
        twice = gold.with_glossary(dict(once), self.data)
        self.assertEqual(once, twice)
        self.assertEqual({k: v for k, v in once.items() if not k.endswith("_html")},
                         {k: v for k, v in task.items() if not k.endswith("_html")})
        self.assertIn("Хейли Арк", once["a_html"])
        self.assertTrue(once["a_html"].startswith('<h3>Хейль</h3><div class="glossary"'))
        self.assertIn("в справочнике нет", once["b_html"])


if __name__ == "__main__":
    unittest.main()
