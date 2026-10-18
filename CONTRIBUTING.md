# Contributing to JobHunting Agent

Thanks for helping! 💙

## Ground rules

1. **Public APIs / scraped public pages only.** No LinkedIn, Indeed or other
   sources whose ToS prohibit automated access — PRs adding them will be closed.
2. Respect rate limits: one request per run per endpoint when possible,
   custom User-Agent, sensible timeouts.
3. Keep the agent local-first: no telemetry, no third-party analytics.

## Ways to help

- **New job sources** — public APIs (Greenhouse/Lever boards, Hacker News
  "Who is hiring", RemoteOK-style aggregators)
- **Notification channels** — Slack, Discord, email (SMTP)
- **Scoring improvements** — with unit tests in `tests/test_filter.py`
- **Docs & i18n** — the README is bilingual (EN/中文); more languages welcome

## Dev workflow

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python tests/test_filter.py     # run tests before submitting
.venv/bin/python main.py run              # smoke test
```

- Code style: standard Python, type hints appreciated, Chinese comments OK
- Small, focused PRs with a clear problem statement
- New scoring behavior must come with tests
