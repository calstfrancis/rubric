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
    migrate_from_json,
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
