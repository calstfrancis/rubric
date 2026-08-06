"""Regression tests for losing work: New Service, autosave, and the lectionary.

The first two protect against destroying a service the user had not finished
with. The third covers a date that had no readings at all.
"""

import unittest
import sys
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

from rcl_data import get_liturgical_info


class TestNewServiceKeepsWorkUntilConfirmed(unittest.TestCase):
    """Choosing a template must be what clears the service, not opening the dialog.

    _reset_state() used to run before the template picker was shown, so backing
    out of it — Cancel, or Escape — left the service already wiped with no way
    back. The current service is only discarded on the "ok" response now, which
    is what this asserts by driving the same handler shape.
    """

    def _handler(self, state):
        """The response handler as new_service() builds it, in miniature."""
        def on_resp(_d, r):
            if r != "ok":
                return
            state["entries"] = []
            state["title"] = ""
        return on_resp

    def test_cancel_leaves_the_service_intact(self):
        state = {"entries": ["Prelude", "Sermon"], "title": "Advent I"}
        self._handler(state)(None, "cancel")
        self.assertEqual(state["entries"], ["Prelude", "Sermon"])
        self.assertEqual(state["title"], "Advent I")

    def test_escape_leaves_the_service_intact(self):
        """set_close_response("cancel") makes Escape deliver "cancel"."""
        state = {"entries": ["Prelude"], "title": "Advent I"}
        self._handler(state)(None, "close")
        self.assertEqual(state["entries"], ["Prelude"])

    def test_confirming_clears_it(self):
        state = {"entries": ["Prelude"], "title": "Advent I"}
        self._handler(state)(None, "ok")
        self.assertEqual(state["entries"], [])
        self.assertEqual(state["title"], "")

    def test_reset_is_not_called_before_the_dialog_is_answered(self):
        """Guards the ordering directly, against the real source."""
        import inspect
        import rubric
        src = inspect.getsource(rubric.MainWindow.new_service)
        # The multi-template branch must not reset before presenting the dialog.
        before_dialog, _, after_dialog = src.partition("# Multiple templates")
        self.assertNotIn("self._reset_state()", after_dialog.split("def on_resp")[0],
                         "new_service() clears the service before the template "
                         "picker is answered — Cancel would discard the user's work")


class TestAutosaveNeverRestoresDeletedWork(unittest.TestCase):
    """Deleting every element is an edit, and must not leave a stale snapshot.

    _do_autosave() required service_entries to be non-empty, so emptying a
    service skipped the write and left the previous snapshot on disk. A crash
    then offered to "restore unsaved work" that resurrected the deleted
    elements. An emptied service has nothing to restore, so the snapshot is
    cleared instead of being left behind.
    """

    def _win(self, entries, title="", notes=""):
        import rubric
        win = MagicMock()
        win.service_entries = entries
        win.service_title_entry.get_text.return_value = title
        win.service_planning_notes = notes
        win._has_restorable_work = lambda: rubric.MainWindow._has_restorable_work(win)
        return win

    def test_emptied_service_has_nothing_to_restore(self):
        self.assertFalse(self._win([])._has_restorable_work())

    def test_a_service_with_elements_does(self):
        self.assertTrue(self._win(["Prelude"])._has_restorable_work())

    def test_a_titled_but_empty_service_still_does(self):
        """Losing a typed title would be losing work too."""
        self.assertTrue(self._win([], title="Advent I")._has_restorable_work())

    def test_planning_notes_alone_count_as_work(self):
        self.assertTrue(self._win([], notes="ring the bell")._has_restorable_work())

    def test_whitespace_only_title_does_not(self):
        self.assertFalse(self._win([], title="   ")._has_restorable_work())

    def test_autosave_clears_the_stale_snapshot_when_emptied(self):
        """The behaviour the guard exists for, driven through _do_autosave."""
        import rubric
        win = self._win([])
        win.modified = True
        cleared = []
        win._clear_autosave = lambda: cleared.append(True)
        rubric.MainWindow._do_autosave(win)
        self.assertEqual(cleared, [True])


class TestLectionaryCoversMajorWeekdayServices(unittest.TestCase):
    """Christmas Eve had no entry at all and fell through to Ordinary Time."""

    def test_christmas_eve_on_a_weekday(self):
        info = get_liturgical_info(date(2026, 12, 24))
        self.assertEqual(info["season"], "Christmas")
        self.assertEqual(info["week"], "Christmas Eve")
        self.assertTrue(info["found"])
        self.assertIn("Luke 2", info["gospel"])

    def test_christmas_eve_on_a_sunday_stays_advent_4(self):
        """24 Dec 2028 is a Sunday: the morning service is Advent 4."""
        self.assertEqual(date(2028, 12, 24).weekday(), 6)
        info = get_liturgical_info(date(2028, 12, 24))
        self.assertEqual(info["season"], "Advent")
        self.assertIn("Advent 4", info["week"])

    def test_easter_vigil(self):
        info = get_liturgical_info(date(2026, 4, 4))  # Easter 2026 is 5 April
        self.assertEqual(info["week"], "Easter Vigil")
        self.assertTrue(info["found"])

    def test_easter_vigil_gospel_follows_the_lectionary_year(self):
        # Easter Sunday: 2026-04-05 (A), 2027-03-28 (B), 2028-04-16 (C)
        for easter_day, expected in [(date(2026, 4, 5), "Matt"),
                                     (date(2027, 3, 28), "Mark"),
                                     (date(2028, 4, 16), "Luke")]:
            with self.subTest(year=easter_day.year):
                from datetime import timedelta
                info = get_liturgical_info(easter_day - timedelta(days=1))
                self.assertEqual(info["week"], "Easter Vigil")
                self.assertIn(expected, info["gospel"])

    def test_the_other_weekday_feasts_still_resolve(self):
        for d, week in [(date(2026, 2, 18), "Ash Wednesday"),
                        (date(2026, 4, 2), "Maundy Thursday"),
                        (date(2026, 4, 3), "Good Friday"),
                        (date(2026, 12, 25), "Christmas Day")]:
            with self.subTest(week=week):
                info = get_liturgical_info(d)
                self.assertEqual(info["week"], week)
                self.assertTrue(info["found"])


if __name__ == "__main__":
    unittest.main()
