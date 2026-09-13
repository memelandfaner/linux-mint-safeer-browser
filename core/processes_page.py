"""safeer://procesi - the browser's own task manager page.

One row per tab from the monitor's last sample: CPU share, resident memory, threads, state
(active / playing sound / sleeping) and two actions that go back to the browser as links
on the same scheme (`?spi=<id>` puts a tab to sleep, `?zapri=<id>` closes it). The page
refreshes itself every three seconds. It is rendered from plain data, so it is testable
without GTK.
"""
import html
import urllib.parse

REFRESH_SECONDS = 3

_TEXT = {
    "sl": {
        "title": "Procesi",
        "intro": "Vsak zavihek teče v svojem procesu. Safeer meri vsaki dve sekundi; težek zavihek v ozadju brez zvoka po minuti zaspi.",
        "tab": "Zavihek", "cpu": "CPU", "memory": "Pomnilnik", "threads": "Niti", "state": "Stanje", "actions": "Dejanja",
        "active": "aktiven", "audio": "zvok", "sleeping": "spi", "hot": "nad proračunom", "hog": "dolgo nad proračunom",
        "sleep": "Uspavaj", "close": "Zapri", "total": "Skupaj", "no_process": "—",
        "limit": "Meja pomnilnika na zavihek: {limit} MB · proračun CPU: {cpu} % enega jedra",
    },
    "en": {
        "title": "Processes",
        "intro": "Every tab runs in its own process. Safeer samples every two seconds; a heavy background tab without sound is put to sleep after a minute.",
        "tab": "Tab", "cpu": "CPU", "memory": "Memory", "threads": "Threads", "state": "State", "actions": "Actions",
        "active": "active", "audio": "sound", "sleeping": "sleeping", "hot": "over budget", "hog": "over budget for long",
        "sleep": "Sleep", "close": "Close", "total": "Total", "no_process": "—",
        "limit": "Memory limit per tab: {limit} MB · CPU budget: {cpu} % of one core",
    },
}


def _fmt_mb(mb, lang):
    if mb >= 1024:
        text = f"{mb / 1024:.2f} GB"
        return text.replace(".", ",") if lang == "sl" else text
    return f"{mb} MB"


def render(rows, lang="sl", limit_mb=0, cpu_budget=0.0):
    """`rows`: list of dicts with id, title, cpu, rss_mb, threads, active, audio, sleeping, verdict."""
    tx = _TEXT.get(lang, _TEXT["en"])
    body = []
    total_cpu = 0.0
    total_mb = 0
    for row in sorted(rows, key=lambda r: (-(r.get("cpu") or 0.0), -(r.get("rss_mb") or 0))):
        tab_id = str(row.get("id", ""))
        cpu = float(row.get("cpu") or 0.0)
        mb = int(row.get("rss_mb") or 0)
        total_cpu += cpu
        total_mb += mb
        states = []
        if row.get("active"):
            states.append(tx["active"])
        if row.get("audio"):
            states.append(tx["audio"])
        if row.get("sleeping"):
            states.append(tx["sleeping"])
        verdict = row.get("verdict")
        if verdict in ("hot", "hog"):
            states.append(tx[verdict])
        klass = " class=\"hot\"" if verdict in ("hot", "hog") else ""
        sleeping = bool(row.get("sleeping"))
        cpu_text = tx["no_process"] if sleeping else f"{int(round(cpu * 100))} %"
        mem_text = tx["no_process"] if sleeping else _fmt_mb(mb, lang)
        threads = tx["no_process"] if sleeping else str(row.get("threads") or 0)
        actions = []
        if not sleeping and not row.get("active"):
            actions.append(f'<a href="safeer://procesi?spi={urllib.parse.quote(tab_id)}">{tx["sleep"]}</a>')
        actions.append(f'<a href="safeer://procesi?zapri={urllib.parse.quote(tab_id)}" class="close">{tx["close"]}</a>')
        body.append(
            f"<tr{klass}><td class=\"t\">{html.escape(str(row.get('title') or ''))}</td>"
            f"<td>{cpu_text}</td><td>{mem_text}</td><td>{threads}</td>"
            f"<td>{html.escape(', '.join(states))}</td><td>{' · '.join(actions)}</td></tr>"
        )
    body.append(
        f"<tr class=\"total\"><td class=\"t\">{tx['total']}</td><td>{int(round(total_cpu * 100))} %</td>"
        f"<td>{_fmt_mb(total_mb, lang)}</td><td></td><td></td><td></td></tr>"
    )
    limit_line = tx["limit"].format(limit=limit_mb, cpu=int(round(cpu_budget * 100))) if limit_mb else ""
    return f"""<!doctype html>
<html lang="{html.escape(lang)}"><head><meta charset="utf-8">
<meta http-equiv="refresh" content="{REFRESH_SECONDS}">
<title>Safeer · {tx['title']}</title>
<style>
  body {{ font-family: system-ui, sans-serif; background: #0f172a; color: #e2e8f0; margin: 0; padding: 32px; }}
  h1 {{ font-size: 22px; margin: 0 0 6px; }}
  p {{ color: #94a3b8; margin: 0 0 18px; max-width: 70ch; }}
  table {{ border-collapse: collapse; width: 100%; max-width: 980px; }}
  th, td {{ text-align: left; padding: 8px 10px; border-bottom: 1px solid #1e293b; white-space: nowrap; }}
  td.t {{ white-space: normal; max-width: 40ch; overflow: hidden; text-overflow: ellipsis; }}
  th {{ color: #94a3b8; font-weight: 600; font-size: 13px; }}
  tr.hot td {{ color: #fdba74; }}
  tr.total td {{ color: #94a3b8; font-weight: 600; border-top: 2px solid #334155; }}
  a {{ color: #38bdf8; text-decoration: none; }} a.close {{ color: #f87171; }} a:hover {{ text-decoration: underline; }}
  .limit {{ color: #64748b; font-size: 12px; margin-top: 14px; }}
</style></head><body>
<h1>🛡️ Safeer · {tx['title']}</h1>
<p>{tx['intro']}</p>
<table><thead><tr><th>{tx['tab']}</th><th>{tx['cpu']}</th><th>{tx['memory']}</th><th>{tx['threads']}</th><th>{tx['state']}</th><th>{tx['actions']}</th></tr></thead>
<tbody>{''.join(body)}</tbody></table>
<div class="limit">{html.escape(limit_line)}</div>
</body></html>"""


def parse_action(uri):
    """Return ('spi'|'zapri', tab_id) for an action link, else (None, None)."""
    try:
        parsed = urllib.parse.urlparse(uri)
    except ValueError:
        return None, None
    if parsed.scheme != "safeer" or parsed.netloc != "procesi":
        return None, None
    query = urllib.parse.parse_qs(parsed.query)
    for key in ("spi", "zapri"):
        values = query.get(key)
        if values and values[0]:
            return key, values[0][:64]
    return None, None
