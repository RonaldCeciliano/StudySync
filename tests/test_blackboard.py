import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

from icalendar import Calendar
from requests.exceptions import RequestException

import blackboard


NOW = datetime(2026, 9, 21, 12, tzinfo=timezone.utc)


class FixedDateTimeMeta(type):
    def __instancecheck__(cls, instance):
        return isinstance(instance, datetime)


class FixedDateTime(datetime, metaclass=FixedDateTimeMeta):
    @classmethod
    def now(cls, tz=None):
        return NOW.astimezone(tz) if tz else NOW.astimezone().replace(tzinfo=None)


def event(uid, dtstart=None):
    lines = ["BEGIN:VEVENT", f"UID:{uid}", f"SUMMARY:Project # {uid}"]
    if dtstart is not None:
        lines.append(dtstart)
    return "\r\n".join(lines + ["END:VEVENT"])


def calendar(*events):
    return Calendar.from_ical(
        "\r\n".join(["BEGIN:VCALENDAR", "VERSION:2.0", *events, "END:VCALENDAR", ""])
    )


class BlackboardDateTests(unittest.TestCase):
    def setUp(self):
        # Fail any accidental HTTP request; all feeds are in-memory fixtures.
        self.network = patch(
            "requests.sessions.Session.request",
            side_effect=AssertionError("Network access is forbidden in these tests"),
        )
        self.network.start()
        self.addCleanup(self.network.stop)
        clock = patch.object(blackboard, "datetime", FixedDateTime)
        clock.start()
        self.addCleanup(clock.stop)

    def assignments(self, *events):
        with patch.object(blackboard, "load_calendar", return_value=calendar(*events)):
            return blackboard.get_assignments()

    def test_future_utc_deadline_is_preserved(self):
        assignments = self.assignments(event("GradableItem-utc", "DTSTART:20260922T120000Z"))
        self.assertEqual(len(assignments), 1)
        self.assertEqual(assignments[0].due_date, NOW + timedelta(days=1))
        self.assertEqual(assignments[0].due_date.utcoffset(), timedelta(0))

    def test_timezone_aware_deadline_is_preserved(self):
        fixture = calendar(event(
            "GradableItem-local", "DTSTART;TZID=America/Chicago:20260922T120000"
        ))
        original = fixture.walk("VEVENT")[0]["DTSTART"].dt
        with patch.object(blackboard, "load_calendar", return_value=fixture):
            assignments = blackboard.get_assignments()
        self.assertEqual(len(assignments), 1)
        self.assertIs(assignments[0].due_date, original)
        self.assertEqual(original.utcoffset(), timedelta(hours=-5))

    def assert_skipped(self, dtstart, reason):
        with self.assertLogs("blackboard", level="WARNING") as logs:
            assignments = self.assignments(event("GradableItem-invalid", dtstart))
        self.assertEqual(assignments, [])
        self.assertEqual(len(logs.output), 1)
        self.assertIn("GradableItem-invalid", logs.output[0])
        self.assertIn("Project # GradableItem-invalid", logs.output[0])
        self.assertIn(reason, logs.output[0])

    def test_all_day_date_is_skipped_with_warning(self):
        self.assert_skipped("DTSTART;VALUE=DATE:20260922", "valid date and time")

    def test_naive_datetime_is_skipped_with_warning(self):
        self.assert_skipped("DTSTART:20260922T120000", "no timezone")

    def test_missing_dtstart_is_skipped_with_warning(self):
        self.assert_skipped(None, "missing DTSTART")

    def test_unusable_decoded_value_is_skipped_with_warning(self):
        component = {
            "uid": "GradableItem-invalid",
            "summary": "Invalid assignment",
            "dtstart": SimpleNamespace(dt="not a date"),
        }
        with self.assertLogs("blackboard", level="WARNING") as logs:
            self.assertIsNone(blackboard.parse_assignment_due_date(component))
        self.assertIn("GradableItem-invalid", logs.output[0])
        self.assertIn("Invalid assignment", logs.output[0])
        self.assertIn("valid date and time", logs.output[0])

    def test_mixed_assignments_keep_valid_items_sorted(self):
        with self.assertLogs("blackboard", level="WARNING") as logs:
            assignments = self.assignments(
                event("GradableItem-later", "DTSTART:20260924T120000Z"),
                event("GradableItem-all-day", "DTSTART;VALUE=DATE:20260922"),
                event("GradableItem-missing"),
                event("GradableItem-naive", "DTSTART:20260922T120000"),
                event("GradableItem-earlier", "DTSTART:20260922T120000Z"),
            )
        self.assertEqual([assignment.id for assignment in assignments], ["earlier", "later"])
        self.assertEqual(len(logs.output), 3)
        self.assertEqual(assignments[0].course_code, "CSCE_31903_001")

    def test_past_excluded_present_and_future_included(self):
        with self.assertNoLogs("blackboard", level="WARNING"):
            assignments = self.assignments(
                event("GradableItem-past", "DTSTART:20260921T115959Z"),
                event("GradableItem-present", "DTSTART:20260921T120000Z"),
                event("GradableItem-future", "DTSTART:20260921T120001Z"),
            )
        self.assertEqual([assignment.id for assignment in assignments], ["present", "future"])

    def test_non_gradable_event_is_ignored(self):
        with self.assertNoLogs("blackboard", level="WARNING"):
            self.assertEqual(self.assignments(event("OtherEvent-missing")), [])

    def test_download_failure_propagates(self):
        with patch.object(blackboard, "BLACKBOARD_ICS_URL", "https://example.invalid/feed.ics"):
            with patch.object(blackboard.requests, "get", side_effect=RequestException("offline")):
                with self.assertRaisesRegex(RequestException, "offline"):
                    blackboard.get_assignments()

    def test_feed_parse_failure_propagates(self):
        with patch.object(blackboard, "BLACKBOARD_ICS_URL", "https://example.invalid/feed.ics"):
            with patch.object(blackboard.requests, "get") as get:
                get.return_value.content = b"invalid feed"
                with patch.object(blackboard.Calendar, "from_ical", side_effect=ValueError("bad feed")):
                    with self.assertRaisesRegex(ValueError, "bad feed"):
                        blackboard.get_assignments()


if __name__ == "__main__":
    unittest.main()
