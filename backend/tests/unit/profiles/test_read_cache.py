"""Per-process cache of the deterministic profile reads (overview, performance)."""

from __future__ import annotations

import unittest

from aplomb.api.errors import ServiceError
from aplomb.profiles import service as service_module

from tests.unit.profiles.test_profiles import A, B, service


class Counting:
    """Wraps the uncached computation of a service to count real computations."""

    def __init__(self, svc, name: str) -> None:
        self.calls = 0
        original = getattr(svc, name)

        def counted(*args, **kwargs):
            self.calls += 1
            return original(*args, **kwargs)

        setattr(svc, name, counted)


class ReadCache(unittest.TestCase):

    def test_repeated_reads_compute_once_and_match(self):
        svc = service()
        overview, performance = Counting(svc, "_overview"), Counting(svc, "_performance")
        first = svc.overview(A, "robert", {}).to_wire()
        again = svc.overview(A, "robert", {}).to_wire()
        self.assertEqual(first, again)
        self.assertEqual(overview.calls, 1)
        svc.performance(A, "robert", {"window": "3y"})
        svc.performance(A, "robert", {"window": "3y"})
        self.assertEqual(performance.calls, 1)

    def test_sessions_share_an_unedited_default_profile(self):
        svc = service()
        overview = Counting(svc, "_overview")
        self.assertEqual(svc.overview(A, "robert", {}).to_wire(), svc.overview(B, "robert", {}).to_wire())
        self.assertEqual(overview.calls, 1)

    def test_window_benchmark_and_profile_are_part_of_the_key(self):
        svc = service()
        overview, performance = Counting(svc, "_overview"), Counting(svc, "_performance")
        svc.overview(A, "robert", {})
        svc.overview(A, "robert", {"window": "1y"})
        svc.overview(A, "mateo", {})
        self.assertEqual(overview.calls, 3)
        svc.performance(A, "robert", {})
        svc.performance(A, "robert", {"benchmark": "SPY"})
        self.assertEqual(performance.calls, 2)
        # The language is not an input of either read.
        svc.overview(A, "robert", {"lang": "fr"})
        self.assertEqual(overview.calls, 3)

    def test_an_edited_rule_recomputes_for_that_session_only(self):
        svc = service()
        overview = Counting(svc, "_overview")
        before = svc.overview(A, "robert", {}).to_wire()
        svc.patch_rule(A, "robert", "cap.position", 12, None)
        edited = svc.overview(A, "robert", {}).to_wire()
        self.assertEqual(overview.calls, 2)
        self.assertNotEqual(before["ruleChecks"], edited["ruleChecks"])
        # Session B still reads the unedited default, from the cache.
        self.assertEqual(svc.overview(B, "robert", {}).to_wire(), before)
        self.assertEqual(overview.calls, 2)

    def test_callers_get_a_copy(self):
        svc = service()
        first = svc.overview(A, "robert", {})
        first.counts.conflict = 99
        self.assertNotEqual(svc.overview(A, "robert", {}).counts.conflict, 99)

    def test_errors_are_not_cached(self):
        svc = service()
        overview = Counting(svc, "_overview")
        bad = {"window": "custom", "start": "1990-01-01", "end": "1990-06-01"}
        for _ in range(2):
            with self.assertRaises(ServiceError):
                svc.overview(A, "robert", bad)
        self.assertEqual(overview.calls, 2)

    def test_least_recently_used_entries_leave_first(self):
        svc = service()
        overview = Counting(svc, "_overview")
        size = service_module.READ_CACHE_SIZE
        try:
            service_module.READ_CACHE_SIZE = 2
            svc.overview(A, "robert", {"window": "1y"})
            svc.overview(A, "robert", {"window": "3y"})
            svc.overview(A, "robert", {"window": "1y"})   # refresh 1y
            svc.overview(A, "robert", {"window": "5y"})   # evicts 3y
            svc.overview(A, "robert", {"window": "1y"})   # still cached
            self.assertEqual(overview.calls, 3)
            svc.overview(A, "robert", {"window": "3y"})   # recomputed
            self.assertEqual(overview.calls, 4)
        finally:
            service_module.READ_CACHE_SIZE = size


if __name__ == "__main__":
    unittest.main()
