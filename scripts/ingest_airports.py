"""Retired: the World Explorer no longer serves the OurAirports reference.

The airport route (`/world/airports`), its layer, its capture and `aplomb.world.airports` were
removed because they do not serve the persona decisions (backend/aplomb/world/SPEC.md §8.2).
This stub only keeps the root README link valid until that row is rewritten; delete it then.
"""
import sys


def main(argv: list[str] | None = None) -> int:
    print("ingest_airports.py is retired: the airport reference is no longer part of the World Explorer.",
          file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
