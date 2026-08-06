"""Regression tests for the hymn subsystem.

Covers the bundled title database, hymn rendering in the bulletin, search
ordering, download robustness, and the integrity of the curated suggestion data
— including that every curated week override can actually be reached by a real
lectionary week string, which two of them could not.
"""

import json
import re
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
import unittest.mock
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

from rcl_data import get_liturgical_info
from hymn_lookup import HYMNALS, _BOOK_MAX, parse_hymn_ref
from hymn_suggestions import _load, get_theme_names, get_theme_hymns

_TITLES_FILE = Path(__file__).parent.parent / "rubric_package" / "data" / "hymn_titles.json"


def _titles():
    return json.loads(_TITLES_FILE.read_text(encoding="utf-8"))


class TestBundledTitleDatabase(unittest.TestCase):
    """Hymnary now blocks automated requests, so the app ships titles instead."""

    def test_the_database_ships_with_the_package(self):
        self.assertTrue(_TITLES_FILE.is_file(),
                        "hymn_titles.json must ship — without it a fresh install "
                        "has no hymn titles at all, since Hymnary blocks fetching")

    def test_every_key_is_a_known_book_and_a_number_in_range(self):
        for key, title in _titles().items():
            with self.subTest(key=key):
                m = re.match(r'^(LUS|VU|MV)(\d+)$', key)
                self.assertIsNotNone(m, f"malformed key {key!r}")
                book, num = m.group(1), int(m.group(2))
                self.assertIn(book, HYMNALS)
                self.assertGreaterEqual(num, 1)
                self.assertLessEqual(num, _BOOK_MAX[book])
                self.assertTrue(title.strip())

    def test_known_hymn_numbers_are_right(self):
        """Spot-checks against Voices United. A wrong number here misdirects a
        whole congregation, so these are pinned explicitly."""
        t = _titles()
        for key, expected in [("VU1", "O come, O come, Emmanuel"),
                              ("VU44", "It came upon the midnight clear"),
                              ("VU59", "Joy to the world"),
                              ("VU266", "Amazing grace"),
                              ("VU288", "Great is thy faithfulness"),
                              ("VU509", "I, the Lord of sea and sky")]:
            with self.subTest(key=key):
                self.assertIn(expected.lower(), t.get(key, "").lower())


class TestSeedingIsNonDestructive(unittest.TestCase):
    """The bundle must never overwrite a title the user entered by hand."""

    def setUp(self):
        self._home = tempfile.mkdtemp()
        self._patch = unittest.mock.patch.dict(
            "os.environ", {"HOME": self._home}, clear=False)
        self._patch.start()
        self.addCleanup(self._patch.stop)
        # db module resolves its path at call time from Path.home()
        import importlib
        import rubric_package.db as db
        importlib.reload(db)
        self.db = db
        db.init_db()

    def test_seeding_populates_an_empty_cache(self):
        added = self.db.hymn_seed_bundled()
        self.assertGreater(added, 0)
        self.assertEqual(self.db.hymn_count(), added)

    def test_seeding_twice_adds_nothing_the_second_time(self):
        self.db.hymn_seed_bundled()
        self.assertEqual(self.db.hymn_seed_bundled(), 0)

    def test_a_hand_typed_title_survives_reseeding(self):
        self.db.hymn_seed_bundled()
        self.db.hymn_set("VU44", "My own corrected title")
        self.db.hymn_seed_bundled()
        self.assertEqual(self.db.hymn_get("VU44"), "My own corrected title")


class TestHymnSearchOrdering(unittest.TestCase):
    """Results ran VU 1, VU 10, VU 100, VU 11, VU 2 — text order, not hymnal order."""

    def setUp(self):
        self._home = tempfile.mkdtemp()
        self._patch = unittest.mock.patch.dict(
            "os.environ", {"HOME": self._home}, clear=False)
        self._patch.start()
        self.addCleanup(self._patch.stop)
        import importlib
        import rubric_package.db as db
        importlib.reload(db)
        self.db = db
        db.init_db()
        for n in [1, 2, 3, 9, 10, 11, 100, 101, 110, 200, 961]:
            db.hymn_set(f"VU{n}", f"Placeholder hymn {n}")
        db.hymn_set("VU500", "Amazing beginnings")
        db.hymn_set("VU501", "An amazing thing happened")

    def test_results_run_in_hymnal_order(self):
        rows = self.db.hymn_search("Placeholder")
        nums = [int(r["key"][2:]) for r in rows]
        self.assertEqual(nums, sorted(nums))

    def test_titles_starting_with_the_query_come_first(self):
        rows = self.db.hymn_search("Amazing")
        self.assertEqual(rows[0]["key"], "VU500")


class TestSuggestionDataIntegrity(unittest.TestCase):
    """The curated suggestions once carried wrong hymn numbers."""

    def test_every_entry_is_a_valid_book_and_number(self):
        for group_name, group in _load().items():
            for key, hymns in group.items():
                for h in hymns:
                    with self.subTest(where=f"{group_name}/{key}", hymn=h):
                        prefix, number, title = h
                        self.assertIn(prefix, HYMNALS)
                        self.assertIsInstance(number, int)
                        self.assertGreaterEqual(number, 1)
                        self.assertLessEqual(number, _BOOK_MAX[prefix])
                        self.assertTrue(title.strip())

    def test_no_duplicate_numbers_within_a_group(self):
        for group_name, group in _load().items():
            for key, hymns in group.items():
                with self.subTest(where=f"{group_name}/{key}"):
                    refs = [(h[0], h[1]) for h in hymns]
                    self.assertEqual(len(refs), len(set(refs)))

    def test_curated_numbers_agree_with_the_verified_titles(self):
        """Where a suggestion's title is one we have verified, its number must
        be the verified number. 94 entries disagreed."""
        titles = _titles()
        def norm(t):
            t = t.split(" (")[0].lower().replace("’", "'")
            return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9' ]+", " ", t)).strip()
        by_title = {}
        for k, v in titles.items():
            m = re.match(r'^(LUS|VU|MV)(\d+)$', k)
            by_title.setdefault((m.group(1), norm(v)), set()).add(int(m.group(2)))
        for group_name, group in _load().items():
            for key, hymns in group.items():
                for prefix, number, title in hymns:
                    cands = by_title.get((prefix, norm(title)))
                    if not cands or len(cands) > 1:
                        continue  # unverifiable, or a title printed at two numbers
                    with self.subTest(where=f"{group_name}/{key}", title=title):
                        self.assertEqual(number, next(iter(cands)))


class TestEveryWeekOverrideIsReachable(unittest.TestCase):
    """A curated override keyed on a string no week ever produces is dead code.

    "Palm Sunday" and "Reign of Christ Sunday" were both unreachable: the real
    week strings are "Palm / Passion Sunday, Year A" and "Reign of Christ /
    Christ the King, Year A".
    """

    def _weeks_over(self, start_year, years=3):
        seen = set()
        d = date(start_year, 1, 1)
        end = date(start_year + years, 1, 1)
        while d < end:
            seen.add(get_liturgical_info(d)["week"])
            d += timedelta(days=1)
        return seen

    def test_each_override_matches_some_real_week(self):
        weeks = self._weeks_over(2025, years=4)
        for key in _load()["week_overrides"]:
            with self.subTest(override=key):
                self.assertTrue(
                    any(key.lower() in w.lower() for w in weeks),
                    f"week override {key!r} can never fire — no lectionary week "
                    f"string contains it")


class TestBaptismOfTheLord(unittest.TestCase):
    """It is the first Sunday AFTER 6 January, not the nearest Sunday to it."""

    def test_it_exists_every_year(self):
        for y in range(2024, 2036):
            with self.subTest(year=y):
                found = None
                d = date(y, 1, 1)
                while d < date(y, 2, 15):
                    if "Baptism of the Lord" in get_liturgical_info(d)["week"]:
                        found = d
                        break
                    d += timedelta(days=1)
                self.assertIsNotNone(found, f"Baptism of the Lord missing in {y}")
                self.assertEqual(found.weekday(), 6, "must fall on a Sunday")
                self.assertGreater(found, date(y, 1, 6), "must follow the Epiphany")

    def test_known_dates(self):
        for y, expected in [(2025, date(2025, 1, 12)), (2026, date(2026, 1, 11)),
                            (2027, date(2027, 1, 10)), (2030, date(2030, 1, 13))]:
            with self.subTest(year=y):
                self.assertIn("Baptism of the Lord",
                              get_liturgical_info(expected)["week"])

    def test_epiphany_sundays_are_numbered_from_it(self):
        """Epiphany 1 is Baptism of the Lord, so the next Sunday is Epiphany 2."""
        self.assertIn("Baptism of the Lord", get_liturgical_info(date(2026, 1, 11))["week"])
        self.assertIn("Epiphany 2", get_liturgical_info(date(2026, 1, 18))["week"])
        self.assertIn("Epiphany 3", get_liturgical_info(date(2026, 1, 25))["week"])


class TestHymnRenderingInTheBulletin(unittest.TestCase):

    def _bulletin(self, item):
        from rubric_package.exporters.bulletin_exporter import BulletinExporter
        main = MagicMock()
        main.service_entries = [item]
        main.service_title_entry.get_text.return_value = "Test"
        main.selected_date = None
        main.service_bulletin_text = ""
        main._load_typst_preamble.return_value = ""
        main._preamble._preamble_heading_typst.return_value = ""
        return BulletinExporter(main)._build_bulletin_typst(digital=False)

    def _hymn_item(self, text):
        from rubric_package.models.service import ServiceItem
        si = ServiceItem("Opening Hymn", "Gathering")
        si.set_plain_text(text)
        return si

    def test_reference_becomes_a_hymnref(self):
        out = self._bulletin(self._hymn_item("VU 1 — O come, O come, Emmanuel"))
        self.assertIn('#hymnref("VU 1", [_O come, O come, Emmanuel_])', out)

    def test_a_bare_reference_is_bolded(self):
        self.assertIn("*VU 1*", self._bulletin(self._hymn_item("VU 1")))

    def test_lines_below_the_reference_are_kept(self):
        """They were dropped from the printed bulletin while the preview and the
        manuscript still showed them."""
        out = self._bulletin(self._hymn_item(
            "VU 1 — O come, O come, Emmanuel\nVerses 1, 3 and 5 only\nPlease stand"))
        self.assertIn("#hymnref(", out)
        self.assertIn("Verses 1, 3 and 5 only", out)
        self.assertIn("Please stand", out)

    def test_a_leader_note_under_a_hymn_never_reaches_the_bulletin(self):
        from rubric_package.models.service import ServiceItem
        from rubric_package.models.content import make_block, make_run
        si = ServiceItem("Opening Hymn", "Gathering")
        si.content = [
            make_block("p", [make_run("VU 1 — O come, O come, Emmanuel")]),
            make_block("leader", [make_run("PRIVATE cue the organist")]),
            make_block("p", [make_run("Verses 1 and 3")]),
        ]
        out = self._bulletin(si)
        self.assertNotIn("PRIVATE", out)
        self.assertIn("Verses 1 and 3", out)


class TestLookupIsLocalOnly(unittest.TestCase):
    """Hymn titles come from Rubric's database and nowhere else.

    The Hymnary.org client is gone: it could not get past that site's
    bot-protection challenge, so lookup always failed and the bulk download
    worked through a whole hymnal to add nothing.
    """

    def test_lookup_takes_no_callback(self):
        """It is a synchronous read, so callers get the title back directly."""
        import inspect
        import hymn_lookup
        params = list(inspect.signature(hymn_lookup.lookup_hymn).parameters)
        self.assertEqual(params, ["prefix", "number"])

    def test_no_network_client_remains(self):
        import hymn_lookup
        for name in ("_curl_get", "_fetch_url", "_wayback_url",
                     "_extract_hymn_title", "prefetch_hymnal", "PrefetchHandle",
                     "subprocess", "threading"):
            with self.subTest(name=name):
                self.assertFalse(hasattr(hymn_lookup, name))

    def test_hymn_source_files_do_not_mention_a_url(self):
        """A stray hymnary.org URL would be a request waiting to be made."""
        for rel in ("hymn_lookup.py",
                    "rubric_package/panels/hymn_lookup_panel.py"):
            path = Path(__file__).parent.parent / rel
            body = path.read_text(encoding="utf-8")
            with self.subTest(file=rel):
                self.assertNotIn("http://", body)
                self.assertNotIn("https://", body)


class TestHymnReferenceParsing(unittest.TestCase):

    def test_valid_forms(self):
        self.assertEqual(parse_hymn_ref("VU 16"), ("VU", 16))
        self.assertEqual(parse_hymn_ref("vu16"), ("VU", 16))
        self.assertEqual(parse_hymn_ref("  LUS 5 "), ("LUS", 5))

    def test_unknown_book_is_rejected(self):
        self.assertIsNone(parse_hymn_ref("XYZ 1"))


class TestThemes(unittest.TestCase):

    def test_every_theme_has_usable_content(self):
        for t in get_theme_names():
            with self.subTest(theme=t):
                self.assertGreaterEqual(len(get_theme_hymns(t)), 3)


if __name__ == "__main__":
    unittest.main()
