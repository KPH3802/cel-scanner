"""Run-level logging: one row per scanner run in the shared signal-intelligence DB.

Covers the helper contract directly (offline, temp DB) and the wiring guarantee
that run_scan logs a run row even when the USO source is unreachable — the
exact 'looks dead but actually ran' failure mode this row exists to close.
"""
import sqlite3

import cel_scanner as cel


def test_log_scan_run_writes_one_row(tmp_path):
    db = tmp_path / "intel.db"
    cel.log_scan_run("CEL", "OK", 5, n_fired=5, note="unit", db_path=str(db))
    rows = sqlite3.connect(str(db)).execute(
        "SELECT scanner, source_status, n_evaluated, n_fired, note FROM scan_runs"
    ).fetchall()
    assert rows == [("CEL", "OK", 5, 5, "unit")]


def test_log_scan_run_never_raises_on_bad_path():
    # A directory path is not a writable sqlite file; must swallow, not raise.
    cel.log_scan_run("CEL", "OK", 1, db_path="/does/not/exist/x.db")


def test_run_scan_logs_run_row_on_fetch_fail(tmp_path, monkeypatch):
    intel = tmp_path / "intel.db"
    monkeypatch.setattr(cel, "SIGNAL_INTEL_DB", str(intel))
    monkeypatch.setattr(cel, "DB_PATH", str(tmp_path / "cel.db"))
    # USO source unreachable -> uso_chg None -> FETCH_FAIL path, no per-signal logs.
    monkeypatch.setattr(cel, "get_uso_change", lambda: ("2026-07-21", None))

    cel.run_scan(dry_run=True)

    rows = sqlite3.connect(str(intel)).execute(
        "SELECT scanner, source_status, n_evaluated, n_fired FROM scan_runs"
    ).fetchall()
    assert rows == [("CEL", "FETCH_FAIL", 0, 0)]
