# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2026-09-22

### Added
- 🤖 **Telegram control bot** — manage the self-bot remotely via a Telegram bot
  (`TG_BOT_TOKEN` + `ADMIN_TG_ID`), powered by the same command panel
- `/whoami` — identity of all three accounts (self, Bale bot, control bot)
- `/pause` / `/resume` — temporary global pause of mirroring (persisted across restarts)
- `/logs [n]` — live log tail from the running instance (ring buffer)
- `/status` upgraded: pause state, mapped-message counter, uptime
- Chat-ID discovery now understands modern Bot API `forward_origin` payloads
- Generic `BotAPI` client (renamed from `BaleAPI`) — one client for Bale *and* Telegram Bot API

### Changed
- `bridge/bale_api.py` → `bridge/bot_api.py` (`BotAPI`, `BotAPIError`)

[1.1.0]: https://github.com/parham7991/tg-bale-bridge/compare/v1.0.0...v1.1.0

## [1.0.0] - 2026-09-22

### Added
- 🌉 Core bridge engine: Telegram ⇄ Bale two-way channel mirroring
- Full content coverage: text, photo, video, voice, audio, animation, document,
  sticker, video-note, location, contact, albums (media groups), forwards, replies
- Bidirectional edit sync; delete sync for Telegram → Bale
- Admin panel **inside the Bale bot** (`/add`, `/list`, `/mode`, `/remove`, `/test`, `/id`, `/status`)
  — mirrored in Telegram Saved Messages
- Telegram → Bale Markdown conversion (bold / italic / text-links) and reverse parsing
- Faithful fallbacks for cross-platform oddities (sticker→file, video-note→video,
  poll→text, oversized files→notice)
- Loop-prevention via sent-ID ledger + content fingerprints
- SQLite persistence for channel pairs, message mapping and caches
- Long-polling Bale client with multipart uploads, rate-limit (retry_after) handling
- Docker + docker-compose packaging
- Pytest suite: unit + end-to-end flows with fakes
- GitHub Actions CI (ruff lint + pytest on Python 3.10–3.12)

[1.0.0]: https://github.com/parham7991/tg-bale-bridge/releases/tag/v1.0.0
