"""Make cel_scanner importable offline (stub the gitignored config module)."""
import os
import sys
import types

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

if "config" not in sys.modules:
    try:  # pragma: no cover
        import config  # noqa: F401
    except ImportError:
        _cfg = types.ModuleType("config")
        _cfg.DB_NAME = "cel_signals.db"
        _cfg.TRIGGER_DROP_PCT = -2.0
        _cfg.HOLD_DAYS = 5
        _cfg.SHORT_TICKERS = ["XOP", "XLE", "CVX", "XOM", "COP"]
        _cfg.EMAIL_SENDER = "placeholder@example.com"
        _cfg.EMAIL_RECIPIENT = "placeholder@example.com"
        _cfg.EMAIL_PASSWORD = ""
        _cfg.SMTP_SERVER = "smtp.gmail.com"
        _cfg.SMTP_PORT = 587
        sys.modules["config"] = _cfg
