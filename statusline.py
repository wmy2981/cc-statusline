#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Claude Code status line - path | branch | repo | session | progress | model
from __future__ import annotations

import json, subprocess, sys, io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# ── ANSI helpers ──────────────────────────────────────────────────────────────
RST = '\033[0m'
BOLD = '\033[1m'

CYAN   = '\033[96m'        # path
BLUE   = '\033[94m'        # git branch
ORANGE = '\033[38;5;214m'  # remote repo
GRAY   = '\033[90m'        # session name, diff label
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
    lines[2].append(f'{MAG}{model_name}{RST}')

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
