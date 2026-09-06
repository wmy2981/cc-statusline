# cc-statusline

Custom multi-line statusline for Claude Code, following the official [statusline docs](https://code.claude.com/docs/en/statusline).

Requires Python 3.9+ (standard library only, no third-party dependencies).

## How to Use

Edit `~/.claude/settings.json`:

```json
"statusLine": {
    "type": "command",
    "command": "python /path/to/statusline.py",
    "refreshInterval": 5
}
```

`refreshInterval` is the seconds between statusline refreshes; 5 is a good default.

The script reads the statusline JSON from stdin and prints up to four lines.

## What It Shows

| Line | Content |
| --- | --- |
| 1 | session name (gray bold); falls back to the first 8 chars of the session id |
| 2 | current path (cyan) · git branch (blue) · remote repo as `short:owner/name` (orange, e.g. `gh:wmy2981/cc-statusline`) |
| 3 | context window progress bar (green/yellow/red by usage) · model name (magenta) · **DeepSeek extras** (see below) |
| 4 | code changes: `diff:` + `+added` / `-removed` line counts |

Lines with no data are skipped, so the output adapts to the context.

## DeepSeek Extras

When the active model's display name contains `deepseek`, line 3 becomes:

```
modelname (peak|offpeak) ¥21.66
```