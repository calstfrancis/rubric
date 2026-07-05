"""Tests for rubric_package.db — SQLite persistence layer."""

import sys
import unittest
import sqlite3
import tempfile
import json
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import rubric_package.db as db_module
from rubric_package.db import (
    init_db,
    hymn_get, hymn_set,
    snippets_load, snippets_save, snippets_has_data,
    service_index_update, service_index_get_mtime,
    service_index_all, service_index_prune,
    service_meta_update, service_meta_get, service_meta_all,
    service_meta_prune, service_meta_all_tags, service_meta_all_series,
    service_meta_paths_for_tag, service_meta_paths_for_series,
    migrate_from_json,
    element_index_service, element_instances,
    element_catalog_set_tags, element_catalog_set_favorite, element_catalog_set_notes,
    element_catalog_all_tags, element_catalog_keys_for_tag, element_library,
    element_catalog_find_duplicates, element_catalog_merge,
)


class _TempDB(unittest.TestCase):
    """Base class that redirects DB_PATH to a temp file for each test."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._db_path = Path(self._tmpdir.name) / "rubric.db"
        self._patcher = patch.object(db_module, "DB_PATH", self._db_path)
        self._patcher.start()
        init_db()

    def tearDown(self):
        self._patcher.stop()
        self._tmpdir.cleanup()


class TestHymnCache(_TempDB):

    def test_miss_returns_none(self):
        self.assertIsNone(hymn_get("VU999"))

    def test_set_then_get(self):
        hymn_set("VU16", "Joy to the World")
        self.assertEqual(hymn_get("VU16"), "Joy to the World")

    def test_overwrite(self):
        hymn_set("MV1", "First title")
        hymn_set("MV1", "Corrected title")
        self.assertEqual(hymn_get("MV1"), "Corrected title")

    def test_multiple_keys_independent(self):
        hymn_set("VU1", "Alpha")
        hymn_set("VU2", "Beta")
        self.assertEqual(hymn_get("VU1"), "Alpha")
        self.assertEqual(hymn_get("VU2"), "Beta")


class TestSnippets(_TempDB):

    def test_empty_database_has_no_data(self):
        self.assertFalse(snippets_has_data())

    def test_save_and_load(self):
        data = [{"name": "Test", "content": "Hello"}]
        snippets_save(data)
        self.assertTrue(snippets_has_data())
        result = snippets_load()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["name"], "Test")
        self.assertEqual(result[0]["content"], "Hello")

    def test_save_preserves_order(self):
        data = [
            {"name": "C", "content": "third"},
            {"name": "A", "content": "first"},
            {"name": "B", "content": "second"},
        ]
        snippets_save(data)
        result = snippets_load()
        self.assertEqual([r["name"] for r in result], ["C", "A", "B"])

    def test_save_replaces_existing(self):
        snippets_save([{"name": "Old", "content": "old"}])
        snippets_save([{"name": "New", "content": "new"}])
        result = snippets_load()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["name"], "New")


class TestServiceIndex(_TempDB):

    def test_unknown_path_returns_none(self):
        self.assertIsNone(service_index_get_mtime("/nonexistent.liturgy"))

    def test_update_and_retrieve_mtime(self):
        service_index_update("/a.liturgy", "Sunday", "2026-05-25", 10, 1234567.0)
        self.assertAlmostEqual(service_index_get_mtime("/a.liturgy"), 1234567.0)

    def test_all_returns_all_entries(self):
        service_index_update("/a.liturgy", "A", "2026-05-18", 5, 1.0)
        service_index_update("/b.liturgy", "B", "2026-05-25", 8, 2.0)
        rows = service_index_all()
        paths = {r["path"] for r in rows}
        self.assertIn("/a.liturgy", paths)
        self.assertIn("/b.liturgy", paths)

    def test_prune_removes_stale_entries(self):
        service_index_update("/keep.liturgy", "K", "2026-05-25", 5, 1.0)
        service_index_update("/gone.liturgy", "G", "2026-05-18", 3, 2.0)
        service_index_prune({"/keep.liturgy"})
        paths = {r["path"] for r in service_index_all()}
        self.assertIn("/keep.liturgy", paths)
        self.assertNotIn("/gone.liturgy", paths)

    def test_prune_empty_keep_set_removes_all(self):
        service_index_update("/a.liturgy", "A", "", 1, 1.0)
        service_index_prune(set())
        self.assertEqual(service_index_all(), [])


class TestServiceMeta(_TempDB):

    def test_unknown_path_returns_none(self):
        self.assertIsNone(service_meta_get("/nonexistent.liturgy"))

    def test_update_and_retrieve(self):
        service_meta_update("/a.liturgy", "Advent 1", "2026-11-29",
                             ["communion", "guest preacher"], "Advent 2026",
                             True, "A short preview of the notes.", 1234567.0)
        row = service_meta_get("/a.liturgy")
        self.assertEqual(row["title"], "Advent 1")
        self.assertEqual(row["tags"], ["communion", "guest preacher"])
        self.assertEqual(row["series"], "Advent 2026")
        self.assertTrue(row["pinned"])
        self.assertEqual(row["notes_preview"], "A short preview of the notes.")

    def test_update_overwrites_existing(self):
        service_meta_update("/a.liturgy", "A", "2026-05-18", [], "", False, "", 1.0)
        service_meta_update("/a.liturgy", "A2", "2026-05-25", ["baptism"], "Lent", True, "note", 2.0)
        row = service_meta_get("/a.liturgy")
        self.assertEqual(row["title"], "A2")
        self.assertEqual(row["tags"], ["baptism"])
        self.assertTrue(row["pinned"])

    def test_no_tags_or_series_round_trip_as_empty(self):
        service_meta_update("/a.liturgy", "A", "2026-05-18", [], "", False, "", 1.0)
        row = service_meta_get("/a.liturgy")
        self.assertEqual(row["tags"], [])
        self.assertEqual(row["series"], "")
        self.assertFalse(row["pinned"])

    def test_all_returns_all_entries_newest_first(self):
        service_meta_update("/old.liturgy", "Old", "2026-01-05", [], "", False, "", 1.0)
        service_meta_update("/new.liturgy", "New", "2026-05-25", [], "", False, "", 2.0)
        rows = service_meta_all()
        self.assertEqual(rows[0]["path"], "/new.liturgy")
        self.assertEqual(rows[1]["path"], "/old.liturgy")

    def test_prune_removes_stale_entries(self):
        service_meta_update("/keep.liturgy", "K", "2026-05-25", [], "", False, "", 1.0)
        service_meta_update("/gone.liturgy", "G", "2026-05-18", [], "", False, "", 2.0)
        service_meta_prune({"/keep.liturgy"})
        paths = {r["path"] for r in service_meta_all()}
        self.assertIn("/keep.liturgy", paths)
        self.assertNotIn("/gone.liturgy", paths)

    def test_all_tags_counts_and_orders_by_frequency(self):
        service_meta_update("/a.liturgy", "A", "2026-01-01", ["communion", "baptism"], "", False, "", 1.0)
        service_meta_update("/b.liturgy", "B", "2026-01-08", ["communion"], "", False, "", 2.0)
        tags = service_meta_all_tags()
        self.assertEqual(tags[0], ("communion", 2))
        self.assertIn(("baptism", 1), tags)

    def test_all_series_grouped_alphabetically(self):
        service_meta_update("/a.liturgy", "A", "2026-01-01", [], "Lent 2026", False, "", 1.0)
        service_meta_update("/b.liturgy", "B", "2026-01-08", [], "Advent 2026", False, "", 2.0)
        service_meta_update("/c.liturgy", "C", "2026-01-15", [], "Advent 2026", False, "", 3.0)
        series = service_meta_all_series()
        self.assertEqual(series, [("Advent 2026", 2), ("Lent 2026", 1)])

    def test_attendance_and_debrief_preview_round_trip(self):
        service_meta_update("/a.liturgy", "A", "2026-01-01", [], "", False, "", 1.0,
                             attendance=42, debrief_preview="Went well overall.")
        row = service_meta_get("/a.liturgy")
        self.assertEqual(row["attendance"], 42)
        self.assertEqual(row["debrief_preview"], "Went well overall.")

    def test_attendance_and_debrief_preview_default_to_empty(self):
        service_meta_update("/a.liturgy", "A", "2026-01-01", [], "", False, "", 1.0)
        row = service_meta_get("/a.liturgy")
        self.assertEqual(row["attendance"], 0)
        self.assertEqual(row["debrief_preview"], "")

    def test_paths_for_tag_exact_match_only(self):
        service_meta_update("/a.liturgy", "A", "2026-01-01", ["communion"], "", False, "", 1.0)
        service_meta_update("/b.liturgy", "B", "2026-01-08", ["communion", "baptism"], "", False, "", 2.0)
        service_meta_update("/c.liturgy", "C", "2026-01-15", ["baptism"], "", False, "", 3.0)
        paths = service_meta_paths_for_tag("communion")
        self.assertEqual(set(paths), {"/a.liturgy", "/b.liturgy"})

    def test_paths_for_series_exact_match_only(self):
        service_meta_update("/a.liturgy", "A", "2026-01-01", [], "Advent 2026", False, "", 1.0)
        service_meta_update("/b.liturgy", "B", "2026-01-08", [], "Advent 2027", False, "", 2.0)
        paths = service_meta_paths_for_series("Advent 2026")
        self.assertEqual(paths, ["/a.liturgy"])


class TestElementCatalog(_TempDB):

    def _items(self, *names):
        return [{"type": "item", "name": n, "note": f"{n} note", "leader": "", "bulletin_note": ""}
                for n in names]

    def test_indexing_creates_catalog_entries(self):
        element_index_service("/a.liturgy", "A", "2026-01-01", self._items("Welcome"))
        self.assertEqual(element_catalog_all_tags(), [])
        rows = element_library()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["name"], "Welcome")
        self.assertEqual(rows[0]["name_key"], "welcome")

    def test_name_key_normalizes_case_and_whitespace(self):
        element_index_service("/a.liturgy", "A", "2026-01-01", self._items("Welcome"))
        element_index_service("/b.liturgy", "B", "2026-01-08", self._items("  WELCOME  "))
        rows = element_library()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["use_count"], 2)

    def test_set_and_get_tags_round_trip(self):
        element_index_service("/a.liturgy", "A", "2026-01-01", self._items("Welcome"))
        element_catalog_set_tags("welcome", ["hospitality", "youth"])
        rows = element_library()
        self.assertEqual(rows[0]["tags"], ["hospitality", "youth"])

    def test_favorite_toggle(self):
        element_index_service("/a.liturgy", "A", "2026-01-01", self._items("Welcome"))
        element_catalog_set_favorite("welcome", True)
        self.assertTrue(element_library()[0]["favorite"])
        element_catalog_set_favorite("welcome", False)
        self.assertFalse(element_library()[0]["favorite"])

    def test_all_tags_counts_and_orders_by_frequency(self):
        element_index_service("/a.liturgy", "A", "2026-01-01", self._items("Welcome"))
        element_index_service("/b.liturgy", "B", "2026-01-08", self._items("Prayers of the People"))
        element_catalog_set_tags("welcome", ["hospitality"])
        element_catalog_set_tags("prayers of the people", ["hospitality", "prayer"])
        tags = element_catalog_all_tags()
        self.assertEqual(tags[0], ("hospitality", 2))
        self.assertIn(("prayer", 1), tags)

    def test_keys_for_tag_exact_match_only(self):
        element_index_service("/a.liturgy", "A", "2026-01-01", self._items("Welcome"))
        element_index_service("/b.liturgy", "B", "2026-01-08", self._items("Announcements"))
        element_catalog_set_tags("welcome", ["hospitality"])
        element_catalog_set_tags("announcements", ["hospitality", "logistics"])
        keys = element_catalog_keys_for_tag("hospitality")
        self.assertEqual(set(keys), {"welcome", "announcements"})
        self.assertEqual(element_catalog_keys_for_tag("logistics"), ["announcements"])

    def test_library_filters_by_query(self):
        element_index_service("/a.liturgy", "A", "2026-01-01", self._items("Welcome"))
        element_index_service("/b.liturgy", "B", "2026-01-08", self._items("Benediction"))
        rows = element_library(query="wel")
        self.assertEqual([r["name"] for r in rows], ["Welcome"])

    def test_library_filters_by_tag(self):
        element_index_service("/a.liturgy", "A", "2026-01-01", self._items("Welcome"))
        element_index_service("/b.liturgy", "B", "2026-01-08", self._items("Benediction"))
        element_catalog_set_tags("welcome", ["hospitality"])
        rows = element_library(tag="hospitality")
        self.assertEqual([r["name"] for r in rows], ["Welcome"])

    def test_library_filters_favorites_only(self):
        element_index_service("/a.liturgy", "A", "2026-01-01", self._items("Welcome"))
        element_index_service("/b.liturgy", "B", "2026-01-08", self._items("Benediction"))
        element_catalog_set_favorite("welcome", True)
        rows = element_library(favorites_only=True)
        self.assertEqual([r["name"] for r in rows], ["Welcome"])

    def test_library_sort_alpha(self):
        element_index_service("/a.liturgy", "A", "2026-01-01", self._items("Welcome"))
        element_index_service("/b.liturgy", "B", "2026-01-08", self._items("Benediction"))
        rows = element_library(sort="alpha")
        self.assertEqual([r["name"] for r in rows], ["Benediction", "Welcome"])

    def test_library_sort_recent(self):
        element_index_service("/a.liturgy", "A", "2026-01-01", self._items("Welcome"))
        element_index_service("/b.liturgy", "B", "2026-06-01", self._items("Benediction"))
        rows = element_library(sort="recent")
        self.assertEqual(rows[0]["name"], "Benediction")

    def test_favorites_sort_first_regardless_of_sort_mode(self):
        element_index_service("/a.liturgy", "A", "2026-01-01", self._items("Welcome"))
        element_index_service("/b.liturgy", "B", "2026-06-01", self._items("Benediction"))
        element_catalog_set_favorite("welcome", True)
        rows = element_library(sort="alpha")
        self.assertEqual(rows[0]["name"], "Welcome")

    def test_element_instances_newest_first(self):
        element_index_service("/old.liturgy", "Old", "2026-01-01", self._items("Welcome"))
        element_index_service("/new.liturgy", "New", "2026-06-01", self._items("Welcome"))
        rows = element_instances("welcome")
        self.assertEqual([r["service_path"] for r in rows], ["/new.liturgy", "/old.liturgy"])

    def test_notes_round_trip(self):
        element_index_service("/a.liturgy", "A", "2026-01-01", self._items("Welcome"))
        element_catalog_set_notes("welcome", "Always pair with the announcements slide.")
        self.assertEqual(element_library()[0]["notes"], "Always pair with the announcements slide.")

    def test_find_duplicates_flags_similar_names(self):
        element_index_service("/a.liturgy", "A", "2026-01-01", self._items("Offertory"))
        element_index_service("/b.liturgy", "B", "2026-01-08", self._items("Offeratory"))
        pairs = element_catalog_find_duplicates()
        keys = {pairs[0]["a"]["name_key"], pairs[0]["b"]["name_key"]}
        self.assertEqual(len(pairs), 1)
        self.assertEqual(keys, {"offertory", "offeratory"})
        self.assertGreaterEqual(pairs[0]["score"], 0.82)

    def test_find_duplicates_ignores_dissimilar_names(self):
        element_index_service("/a.liturgy", "A", "2026-01-01", self._items("Welcome"))
        element_index_service("/b.liturgy", "B", "2026-01-08", self._items("Benediction"))
        self.assertEqual(element_catalog_find_duplicates(), [])

    def test_find_duplicates_respects_threshold(self):
        element_index_service("/a.liturgy", "A", "2026-01-01", self._items("Offertory"))
        element_index_service("/b.liturgy", "B", "2026-01-08", self._items("Offeratory"))
        self.assertEqual(element_catalog_find_duplicates(threshold=0.99), [])

    def test_merge_reassigns_instances_to_keep_key(self):
        element_index_service("/a.liturgy", "A", "2026-01-01", self._items("Offertory"))
        element_index_service("/b.liturgy", "B", "2026-01-08", self._items("Offeratory"))
        element_catalog_merge("offertory", "offeratory")
        rows = element_instances("offertory")
        self.assertEqual({r["service_path"] for r in rows}, {"/a.liturgy", "/b.liturgy"})
        self.assertEqual(element_instances("offeratory"), [])

    def test_merge_removes_dropped_catalog_entry(self):
        element_index_service("/a.liturgy", "A", "2026-01-01", self._items("Offertory"))
        element_index_service("/b.liturgy", "B", "2026-01-08", self._items("Offeratory"))
        element_catalog_merge("offertory", "offeratory")
        keys = {r["name_key"] for r in element_library()}
        self.assertEqual(keys, {"offertory"})

    def test_merge_unions_tags_and_favorite(self):
        element_index_service("/a.liturgy", "A", "2026-01-01", self._items("Offertory"))
        element_index_service("/b.liturgy", "B", "2026-01-08", self._items("Offeratory"))
        element_catalog_set_tags("offertory", ["giving"])
        element_catalog_set_tags("offeratory", ["giving", "music"])
        element_catalog_set_favorite("offeratory", True)
        element_catalog_merge("offertory", "offeratory")
        merged = element_library()[0]
        self.assertEqual(merged["name_key"], "offertory")
        self.assertEqual(set(merged["tags"]), {"giving", "music"})
        self.assertTrue(merged["favorite"])

    def test_merge_keeps_existing_notes_over_dropped_notes(self):
        element_index_service("/a.liturgy", "A", "2026-01-01", self._items("Offertory"))
        element_index_service("/b.liturgy", "B", "2026-01-08", self._items("Offeratory"))
        element_catalog_set_notes("offertory", "Keep this one.")
        element_catalog_set_notes("offeratory", "Dropped note.")
        element_catalog_merge("offertory", "offeratory")
        self.assertEqual(element_library()[0]["notes"], "Keep this one.")

    def test_merge_uses_dropped_notes_if_keep_has_none(self):
        element_index_service("/a.liturgy", "A", "2026-01-01", self._items("Offertory"))
        element_index_service("/b.liturgy", "B", "2026-01-08", self._items("Offeratory"))
        element_catalog_set_notes("offeratory", "Only note available.")
        element_catalog_merge("offertory", "offeratory")
        self.assertEqual(element_library()[0]["notes"], "Only note available.")

    def test_merge_same_key_is_a_noop(self):
        element_index_service("/a.liturgy", "A", "2026-01-01", self._items("Welcome"))
        element_catalog_merge("welcome", "welcome")
        self.assertEqual(len(element_library()), 1)


class TestMigrateFromJson(_TempDB):

    def test_migrates_hymn_cache(self):
        with tempfile.TemporaryDirectory() as td:
            cache_file = Path(td) / "hymn_cache.json"
            cache_file.write_text(json.dumps({"VU42": "For the Beauty"}), encoding="utf-8")
            with patch("rubric_package.db.DB_PATH", self._db_path), \
                 patch("rubric_package.db.Path") as mock_path_cls:
                # Re-use our temp db; only redirect the cache JSON path
                pass

        # Simpler: write the migration file to the real home-relative path,
        # then patch it at the module level.
        cache_src = {"MV5": "Deep in Our Hearts"}
        snip_src = [{"name": "S", "content": "C"}]

        with tempfile.TemporaryDirectory() as td:
            cache_file = Path(td) / "hymn_cache.json"
            snip_file  = Path(td) / "snippets.json"
            cache_file.write_text(json.dumps(cache_src), encoding="utf-8")
            snip_file.write_text(json.dumps(snip_src), encoding="utf-8")

            home_share = Path(td)
            home_config = Path(td)

            with patch("rubric_package.db.DB_PATH", self._db_path):
                with patch("rubric_package.db._migrate_hymn_cache") as mhc, \
                     patch("rubric_package.db._migrate_snippets") as ms:
                    migrate_from_json()
                    mhc.assert_called_once()
                    ms.assert_called_once()

    def test_migration_skips_when_data_exists(self):
        """If the table already has rows, migration does not overwrite them."""
        hymn_set("VU1", "Existing")

        # Build a fake home directory with a hymn_cache.json that would override VU1
        fake_home = Path(self._tmpdir.name) / "fakehome"
        cache_dir = fake_home / ".local" / "share" / "rubric"
        cache_dir.mkdir(parents=True)
        (cache_dir / "hymn_cache.json").write_text(
            json.dumps({"VU1": "Override Attempt"}), encoding="utf-8"
        )

        from rubric_package.db import _migrate_hymn_cache
        with patch.object(Path, "home", return_value=fake_home):
            _migrate_hymn_cache()

        # DB row must be unchanged — guard fired before reading the JSON
        self.assertEqual(hymn_get("VU1"), "Existing")


if __name__ == "__main__":
    unittest.main()
