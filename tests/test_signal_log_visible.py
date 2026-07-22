"""A signal-log write failure must be VISIBLE, not silently swallowed.

The per-signal ``log_signal_intelligence`` writer must not swallow a failed
write with a bare ``except: pass`` -- a silent failure is indistinguishable
from a scanner that logged nothing. On write failure it must print a
one-line ``[SIGNAL_LOG_FAIL]`` diagnostic and keep going (never re-raise).
"""
import cel_scanner as cel


def test_signal_log_failure_is_printed(capsys, monkeypatch):
    # Force the DB write to fail by pointing the hardcoded path at an unwritable dir.
    monkeypatch.setattr(cel.os.path, "expanduser",
                        lambda p: "/does/not/exist/nope/signal_intelligence.db")
    # Must not raise.
    cel.log_signal_intelligence("2026-07-22", "CEL", "XOP", "SHORT", 1)
    out = capsys.readouterr().out
    assert "[SIGNAL_LOG_FAIL]" in out
    assert "CEL" in out and "XOP" in out
