# Contributing

Contributions are welcome! 🎉

## Development setup

```bash
git clone https://github.com/parham7991/tg-bale-bridge.git
cd tg-bale-bridge
python -m venv .venv && source .venv/bin/activate
make dev          # installs runtime + dev dependencies
make test         # runs the pytest suite
make lint         # ruff lint
```

## Guidelines

- **Tests first** — any bug fix or feature should come with tests (`tests/`).
  The suite runs fully offline with fakes; no real Telegram/Bale accounts needed.
- **Style** — `ruff check .` must pass. Keep functions small and documented
  (docstrings in Persian or English are both fine).
- **Commits** — [Conventional Commits](https://www.conventionalcommits.org/):
  `feat:`, `fix:`, `docs:`, `test:`, `ci:`, `refactor:`, `chore:`.
- **PRs** — one feature per PR; describe *what* and *why*; link related issues.
- **Secrets** — never commit `.env`, `data/`, session files or tokens.

## Good first ideas

- Comment (دیدگاه) syncing for linked discussion groups
- Bale Business API adapter for high-volume channels
- Web dashboard for pair management
- Sticker conversion (TGS → animated) instead of file fallback
