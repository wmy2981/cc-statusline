#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Claude Code status line - path | branch | repo | session | progress | model
from __future__ import annotations

import json, subprocess, sys, io, tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.request import Request, urlopen

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# ── ANSI helpers ──────────────────────────────────────────────────────────────
RST = '\033[0m'
BOLD = '\033[1m'

CYAN   = '\033[96m'        # path
BLUE   = '\033[94m'        # git branch
ORANGE = '\033[38;5;214m'  # remote repo
GRAY   = '\033[90m'        # session name, diff label, deepseek peak/offpeak
WHITE  = '\033[97m'        # deepseek balance (distinct from all other colours)
GREEN  = '\033[92m'        # low usage
YELLOW = '\033[93m'        # medium usage
RED    = '\033[91m'        # high usage
MAG    = '\033[95m'        # model
ADD    = '\033[38;5;76m'   # diff added (distinct from GREEN)
DEL    = '\033[38;5;160m'  # diff deleted (distinct from RED)

# ── helpers ───────────────────────────────────────────────────────────────────

def _git_branch() -> str:
    try:
        return subprocess.check_output(
            ['git', 'branch', '--show-current'],
            stderr=subprocess.DEVNULL, text=True, timeout=5,
        ).strip()
    except Exception:
        return ''

def _pct(val: object) -> float:
    if val is None:
        return 0.0
    try:
        return float(str(val).rstrip('%'))
    except (ValueError, TypeError):
        return 0.0

def _progress_bar(pct: float, width: int = 20) -> str:
    filled = round(pct / (100 / width))
    bar = '█' * filled + '░' * (width - filled)

    if pct < 50:
        colour = GREEN
    elif pct < 80:
        colour = YELLOW
    else:
        colour = RED

    return f'{colour}[{bar}]{RST}{colour} {pct:.0f}%{RST}'

def _short_host(host: str) -> str:
    """Abbreviate common git hosts."""
    h = host.lower().removesuffix('.com').removesuffix('.org')
    return {'github': 'gh', 'gitlab': 'gl', 'bitbucket': 'bb'}.get(h, h)

# ── deepseek extras (only for model names containing 'deepseek') ──────────────
# statusline runs on a 5s refreshInterval, so the balance call is cached in a
# temp file instead of hitting the API on every render.

DEEPSEEK_BALANCE_URL = 'https://api.deepseek.com/user/balance'
BALANCE_CACHE_TTL = 60  # seconds
BALANCE_CACHE_FILE = Path(tempfile.gettempdir()) / 'cc-statusline-deepseek-balance.json'

def _pricing_at(t: datetime) -> str:
    """peak/offpeak for a Beijing-local datetime: Mon-Fri 9:00-12:00, 14:00-18:00 = peak."""
    minutes = t.hour * 60 + t.minute
    peak = t.weekday() < 5 and ((9 * 60 <= minutes < 12 * 60) or (14 * 60 <= minutes < 18 * 60))
    return 'peak' if peak else 'offpeak'

def _deepseek_label() -> str:
    """Beijing time is UTC+8 with no DST, so a fixed offset from system UTC suffices."""
    return _pricing_at(datetime.now(timezone.utc) + timedelta(hours=8))

def _deepseek_key() -> str:
    """API key from ~/.claude/settings.json env: ANTHROPIC_AUTH_TOKEN, fallback ANTHROPIC_API_KEY."""
    env: dict = {}
    try:
        raw = Path.home().joinpath('.claude', 'settings.json').read_text(encoding='utf-8')
        env = json.loads(raw).get('env', {})
    except Exception:
        pass
    return env.get('ANTHROPIC_AUTH_TOKEN') or env.get('ANTHROPIC_API_KEY') or ''

def _read_balance_cache() -> str | None:
    try:
        ts, val = json.loads(BALANCE_CACHE_FILE.read_text(encoding='utf-8'))
        if datetime.now().timestamp() - ts < BALANCE_CACHE_TTL:
            return val
    except Exception:
        pass
    return None

def _write_balance_cache(val: str) -> None:
    try:
        BALANCE_CACHE_FILE.write_text(json.dumps([datetime.now().timestamp(), val]),
                                      encoding='utf-8')
    except Exception:
        pass

def _deepseek_balance(key: str) -> str:
    """Formatted balance like '¥110.00'/'$12.34', or '' on any failure (not cached)."""
    cached = _read_balance_cache()
    if cached is not None:
        return cached
    try:
        req = Request(DEEPSEEK_BALANCE_URL,
                      headers={'Authorization': f'Bearer {key}', 'Accept': 'application/json'})
        with urlopen(req, timeout=3) as resp:
            data = json.load(resp)
        infos = data.get('balance_infos') or []
        if not infos:
            return ''
        currency = str(infos[0].get('currency', ''))
        amount = str(infos[0].get('total_balance', '')).strip()
        if not amount:
            return ''
        symbol = {'CNY': '¥', 'USD': '$'}.get(currency, f'{currency} ')
        result = f'{symbol}{amount}'
    except Exception:
        return ''
    _write_balance_cache(result)
    return result

# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    data = json.loads(sys.stdin.buffer.read())

    ws    = data.get('workspace', {})
    ctx   = data.get('context_window', {})
    model = data.get('model', {})

    lines: list[list[str]] = [[], [], [], []]  # 4 lines

    # ── Line 1: session name ──────────────────────────────────────────────────
    session_label = data.get('session_name', '') or data.get('session_id', '')[:8]
    if session_label:
        lines[0].append(f'{GRAY}{BOLD}{session_label}{RST}')

    # ── Line 2: path  branch  repo ────────────────────────────────────────────
    raw_path = ws.get('current_dir', '').replace('\\', '/')
    display_path = raw_path if raw_path else '?'
    lines[1].append(f'{CYAN}\'{display_path}\'{RST}')

    branch = _git_branch()
    if branch:
        lines[1].append(f'{BLUE}[{branch}]{RST}')

    repo = ws.get('repo', {})
    host  = repo.get('host', '')
    owner = repo.get('owner', '')
    name  = repo.get('name', '')
    if host and owner and name:
        short = _short_host(host)
        lines[1].append(f'{ORANGE}{short}:{owner}/{name}{RST}')
    elif owner and name:
        lines[1].append(f'{ORANGE}{owner}/{name}{RST}')

    # ── Line 3: progress bar  model ───────────────────────────────────────────
    pct = _pct(ctx.get('used_percentage', 0))
    lines[2].append(_progress_bar(pct))

    model_name = model.get('display_name', '') or '—'
    model_seg = f'{MAG}{model_name}{RST}'

    # deepseek extras: (peak|offpeak) + balance, only for deepseek models
    if 'deepseek' in model_name.lower():
        label = _deepseek_label()
        label_colour = RED if label == 'peak' else GRAY
        parts = [model_seg, f'{label_colour}({label}){RST}']
        amount = _deepseek_balance(_deepseek_key())
        if amount:
            parts.append(f'{WHITE}{amount}{RST}')
        lines[2].append(' '.join(parts))
    else:
        lines[2].append(model_seg)

    # ── Line 4: code changes ──────────────────────────────────────────────────
    cost = data.get('cost', {})
    added   = cost.get('total_lines_added', 0)
    removed = cost.get('total_lines_removed', 0)
    if added or removed:
        diff_parts = [f'{GRAY}diff:{RST}']
        if added:
            diff_parts.append(f'{ADD}+{added}{RST}')
        if removed:
            diff_parts.append(f'{DEL}-{removed}{RST}')
        lines[3].append('  '.join(diff_parts))

    # ── output ────────────────────────────────────────────────────────────────
    out = '\n'.join('  '.join(ln) for ln in lines if ln)
    if out:
        print(out)

if __name__ == '__main__':
    main()
