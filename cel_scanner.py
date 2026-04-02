#!/usr/bin/env python3
"""
Commodity-Equity Lag Scanner
==============================
Daily scanner. When USO drops 2%+ in a single session, related energy
equities (E&P, refiners) typically lag the move by 1-2 days.

Validated signal (backtest 2015-2026, 5-day hold):
  USO drops >=2% -> SHORT XOP, XLE, CVX, XOM, COP: -0.55% to -0.71% alpha, p<0.05
  BULL side (USO up 2%+): FLAT -- not deployed

Scanner runs nightly. Checks yesterday's USO close vs prior close.
Fires SHORT signals when USO dropped >=2%.

IB AutoTrader email subject: 'CEL BEAR: XOP, XLE, CVX, XOM, COP'

Usage:
  python3 cel_scanner.py              # Normal nightly run
  python3 cel_scanner.py --test-email # Send test email
  python3 cel_scanner.py --status     # Show DB stats
  python3 cel_scanner.py --dry-run    # Detect signals, skip email
"""

import os
import sys
import sqlite3
import smtplib
import argparse
from datetime import datetime, timedelta, date
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import config

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH    = os.path.join(SCRIPT_DIR, config.DB_NAME)

TRIGGER_TICKER  = 'USO'
TRIGGER_DROP    = config.TRIGGER_DROP_PCT   # -2.0%
HOLD_DAYS       = config.HOLD_DAYS          # 5 trading days
SHORT_TICKERS   = config.SHORT_TICKERS      # XOP, XLE, CVX, XOM, COP

# ============================================================
# DATABASE
# ============================================================

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS cel_signals (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            trigger_date    TEXT NOT NULL,
            uso_change_pct  REAL NOT NULL,
            detected_date   TEXT NOT NULL,
            emailed         INTEGER DEFAULT 0,
            UNIQUE(trigger_date)
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS scan_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            scan_date   TEXT,
            uso_change  REAL,
            signal_fired INTEGER DEFAULT 0,
            emailed     INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    return conn

# ============================================================
# PRICE FETCH
# ============================================================

def get_uso_change():
    """Get yesterday's USO price change %.
    Returns (date_str, change_pct) or (None, None) if unavailable.
    """
    try:
        import yfinance as yf
        uso = yf.Ticker('USO')
        hist = uso.history(period='5d')
        if len(hist) < 2:
            return None, None
        closes = hist['Close'].tolist()
        dates  = [str(d.date()) for d in hist.index.tolist()]
        # Yesterday = second-to-last row, today may not have traded yet
        prior = closes[-2]
        last  = closes[-1]
        chg   = (last - prior) / prior * 100.0
        return dates[-1], round(chg, 3)
    except Exception as e:
        print(f'  USO price fetch failed: {e}')
        return None, None

# ============================================================
# SIGNAL LOGIC
# ============================================================

def already_fired(conn, trigger_date):
    c = conn.cursor()
    c.execute('SELECT id FROM cel_signals WHERE trigger_date=?', (trigger_date,))
    return c.fetchone() is not None

def store_signal(conn, trigger_date, uso_chg):
    c = conn.cursor()
    try:
        c.execute('INSERT OR IGNORE INTO cel_signals (trigger_date, uso_change_pct, detected_date, emailed) VALUES (?,?,?,0)',
                  (trigger_date, uso_chg, datetime.utcnow().strftime('%Y-%m-%d')))
        conn.commit()
        return c.rowcount > 0
    except Exception as e:
        print(f'  store_signal error: {e}')
        return False

def mark_emailed(conn, trigger_date):
    c = conn.cursor()
    c.execute('UPDATE cel_signals SET emailed=1 WHERE trigger_date=?', (trigger_date,))
    conn.commit()

def log_scan(conn, uso_chg, signal_fired, emailed):
    c = conn.cursor()
    c.execute('INSERT INTO scan_log (scan_date, uso_change, signal_fired, emailed) VALUES (?,?,?,?)',
              (datetime.utcnow().strftime('%Y-%m-%d %H:%M'), uso_chg, 1 if signal_fired else 0, 1 if emailed else 0))
    conn.commit()

def get_recent_signals(conn, n=10):
    c = conn.cursor()
    c.execute('SELECT trigger_date, uso_change_pct, detected_date FROM cel_signals ORDER BY trigger_date DESC LIMIT ?', (n,))
    return c.fetchall()

# ============================================================
# EMAIL
# ============================================================

def build_email_subject():
    tickers = ', '.join(SHORT_TICKERS)
    return f'CEL BEAR: {tickers}'

def build_email_html(trigger_date, uso_chg, recent):
    today = datetime.utcnow().strftime('%Y-%m-%d')
    html = f"""<!DOCTYPE html>
<html><head><style>
body{{font-family:'Segoe UI',Arial,sans-serif;background:#1a1a2e;color:#e0e0e0;margin:0;padding:0}}
.wrap{{max-width:700px;margin:0 auto;padding:20px}}
h1{{color:#f44336;font-size:22px;border-bottom:2px solid #333;padding-bottom:10px;margin-top:0}}
.summary{{background:#16213e;border-radius:8px;padding:14px;margin:14px 0}}
.card{{background:#16213e;border-left:4px solid #f44336;border-radius:8px;padding:14px;margin:10px 0}}
.ticker{{font-size:20px;font-weight:bold;color:#fff}}
.badge{{display:inline-block;padding:3px 10px;border-radius:12px;font-size:12px;font-weight:bold;background:#f44336;color:#fff;margin-left:8px;vertical-align:middle}}
.backtest{{background:#0d2137;border:1px solid #1a5276;border-radius:8px;padding:12px;margin:20px 0;font-size:12px;color:#7fb3d8}}
table{{width:100%;border-collapse:collapse;margin-top:8px}}
th{{background:#0f3460;color:#e0e0e0;padding:7px;text-align:left;font-size:12px}}
td{{padding:7px;border-bottom:1px solid #333;font-size:12px}}
.footer{{color:#555;font-size:11px;margin-top:28px;border-top:1px solid #333;padding-top:10px}}
</style></head><body><div class='wrap'>
<h1>CEL BEAR SIGNAL &mdash; {today}</h1>
<div class='summary'>
  USO dropped <strong style='color:#f44336;'>{uso_chg:.2f}%</strong> on {trigger_date}
  &nbsp;|&nbsp; Trigger: &le;{TRIGGER_DROP}%
  &nbsp;|&nbsp; Hold: {HOLD_DAYS} trading days
</div>
"""
    for t in SHORT_TICKERS:
        html += f"""
<div class='card'>
  <span class='ticker'>{t}</span>
  <span class='badge'>SHORT</span>
  <div style='font-size:12px;color:#aaa;margin-top:6px;'>Energy equity lag play &bull; {HOLD_DAYS}-day hold</div>
</div>"""

    html += f"""
<div class='backtest'>
  <strong>Backtest Reference (2015-2026, 5-day hold):</strong><br>
  USO drops &ge;2% &rarr; SHORT XOP/XLE/CVX/XOM/COP: -0.55% to -0.71% alpha/trade, p&lt;0.05 across all 5<br>
  BULL side (USO up &ge;2%) is FLAT &mdash; not deployed
</div>"""

    if recent:
        html += """
<h2 style='color:#64b5f6;'>Recent Signal History</h2>
<table><tr><th>Trigger Date</th><th>USO Change</th><th>Detected</th></tr>"""
        for r in recent:
            html += f"<tr><td>{r[0]}</td><td style='color:#f44336;'>{r[1]:.2f}%</td><td>{r[2]}</td></tr>"
        html += '</table>'

    html += f"""
<div class='footer'>
  CEL Scanner v1.0 &nbsp;|&nbsp; USO &ge;2% daily drop trigger &nbsp;|&nbsp;
  IB AutoTrader subject: 'CEL BEAR: XOP, XLE, CVX, XOM, COP'<br>
  Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}
</div></div></body></html>"""
    return html

def send_email(subject, html_body):
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From']    = config.EMAIL_SENDER
    msg['To']      = config.EMAIL_RECIPIENT
    msg.attach(MIMEText(html_body, 'html'))
    try:
        with smtplib.SMTP(config.SMTP_SERVER, config.SMTP_PORT) as srv:
            srv.starttls()
            srv.login(config.EMAIL_SENDER, config.EMAIL_PASSWORD)
            srv.sendmail(config.EMAIL_SENDER, config.EMAIL_RECIPIENT, msg.as_string())
        print('  Email sent successfully')
        return True
    except Exception as e:
        print(f'  Email error: {e}')
        return False

# ============================================================
# MAIN
# ============================================================

def run_scan(dry_run=False):
    print(f'CEL SCANNER -- {datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")}')
    conn = init_db()

    trigger_date, uso_chg = get_uso_change()
    if uso_chg is None:
        print('  Could not fetch USO price.')
        log_scan(conn, 0, False, False)
        conn.close()
        return

    print(f'  USO latest: {trigger_date} {uso_chg:+.2f}%')

    if uso_chg > TRIGGER_DROP:
        print(f'  No signal (USO {uso_chg:+.2f}% > trigger {TRIGGER_DROP}%)')
        log_scan(conn, uso_chg, False, False)
        conn.close()
        return

    if already_fired(conn, trigger_date):
        print(f'  Signal for {trigger_date} already sent.')
        log_scan(conn, uso_chg, False, False)
        conn.close()
        return

    # Signal fires
    print(f'  SIGNAL: USO {uso_chg:+.2f}% on {trigger_date} -> SHORT {SHORT_TICKERS}')
    store_signal(conn, trigger_date, uso_chg)
    recent = get_recent_signals(conn)
    subject = build_email_subject()
    html    = build_email_html(trigger_date, uso_chg, recent)

    email_sent = False
    if dry_run:
        print(f'  DRY RUN: subject would be: {subject}')
    else:
        email_sent = send_email(subject, html)
        if email_sent:
            mark_emailed(conn, trigger_date)

    log_scan(conn, uso_chg, True, email_sent)
    print(f'  Done. Signals: {subject}')
    conn.close()

def show_status():
    conn = init_db()
    c = conn.cursor()
    c.execute('SELECT COUNT(*) FROM cel_signals')
    total = c.fetchone()[0]
    c.execute('SELECT * FROM scan_log ORDER BY id DESC LIMIT 5')
    scans = c.fetchall()
    recent = get_recent_signals(conn, 10)
    print(f'CEL SCANNER STATUS')
    print(f'Total signals: {total}')
    if scans:
        print('Last scans:')
        for s in scans:
            print(f'  {s[1]} | USO:{s[2]:+.2f}% | signal:{s[3]} | emailed:{s[4]}')
    if recent:
        print('Recent signals:')
        for r in recent:
            print(f'  {r[0]}  USO {r[1]:.2f}%  detected {r[2]}')
    conn.close()

def send_test_email():
    html = f"""<html><body style='font-family:Arial;background:#1a1a2e;color:#e0e0e0;padding:20px;'>
<h1 style='color:#f44336;'>CEL Scanner -- Test Email</h1>
<p>Trigger: USO drops &ge;{abs(TRIGGER_DROP)}% in one session</p>
<p>Short: {', '.join(SHORT_TICKERS)}</p>
<p>Hold: {HOLD_DAYS} trading days</p>
<p>Subject format: 'CEL BEAR: XOP, XLE, CVX, XOM, COP'</p>
<p style='color:#666;'>{datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}</p>
</body></html>"""
    send_email('CEL Scanner -- Test Email', html)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Commodity-Equity Lag Scanner')
    parser.add_argument('--test-email', action='store_true')
    parser.add_argument('--status',     action='store_true')
    parser.add_argument('--dry-run',    action='store_true')
    args = parser.parse_args()
    if args.test_email:
        send_test_email()
    elif args.status:
        show_status()
    else:
        run_scan(dry_run=args.dry_run)

