# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.8.0] - 2026-09-22

### Changed — ❤️ transfer engine: the heart of the bridge, modularized
- **All mirroring logic extracted into `bridge/transfer/`** (the 811-line
  `transfer.py` was the largest file left) — same per-section engines pattern:
  - `bridge/transfer/types_map.py` — pure mappings: TG message classification,
    Bale content extraction, UTF-16 entity building, content fingerprint
  - `bridge/transfer/loopguard.py` — **LoopGuard**: sent-ledger (was_sent/mark_sent),
    content fingerprints, delete-echo suppression sets (both layers of loop prevention)
  - `bridge/transfer/albums.py` — **AlbumCollector**: media-group collection with
    flush timers (Bale delay ×1.4), one instance per direction
  - `bridge/transfer/queueing.py` — **QueueEngine**: the two deterministic FIFOs,
    one worker per side, pause state, all event entry points
  - `bridge/transfer/mirror_t2b.py` — **T2BEngine**: Telegram→Bale (every media
    type, full fallback chain, albums with parallel download + group send)
  - `bridge/transfer/mirror_b2t.py` — **B2TEngine**: Bale→Telegram (entity offsets,
    caption_entities compat, 20 MB download cap, album fallback)
  - `bridge/transfer/sync_edit.py` — **EditSyncEngine**: two-way edits with
    delete+resend replacement on failure
  - `bridge/transfer/sync_delete.py` — **DeleteSyncEngine**: two-way deletes with
    echo suppression (selfbot-only on the Bale side)
  - `bridge/transfer/facade.py` — **Bridge**: compatibility façade with the exact
    legacy surface (`workers`, `on_*`, `queue_*`, `paused`, `bale_bot`, statics)
- `admin /test` now resolves the TG entity via `bridge.b2t.entity`
- `bridge/transfer.py` kept as a re-export shim (`_fp` import preserved)
- No behavior change; **229 tests green** (12 new engine tests), ruff clean

[2.8.0]: https://github.com/parham7991/tg-bale-bridge/compare/v2.7.0...v2.8.0

## [2.7.0] - 2026-09-22

### Changed — ✈️ Telegram selfbot (Telethon): modular engine package
- **All Telegram-selfbot logic extracted into `bridge/tguser/`** — including the
  TG login flow that previously lived inline inside the wizard:
  - `bridge/tguser/types_map.py` — pure mappings: Saved-Messages detection, text,
    forward
  - `bridge/tguser/session.py` — **TgSelfSession**: single source for building the
    Telethon client (main.py + login engine) + safe connect/authorize
  - `bridge/tguser/gateway.py` — **TgSelfGateway**: credential cascade
    (wizard input ← .env ← store), ready-client for resolve/probe, access probe
    (reads last message, both call signatures), `@user / t.me/user` normalization
  - `bridge/tguser/login.py` — **TgLoginEngine**: two-step login + 2FA password;
    the in-flight client and `phone_code_hash` now live inside the engine
  - `bridge/tguser/routing.py` — **TgEventRouter**: Saved-Messages = admin panel,
    everything else = bridge; edits/deletes in Saved-Messages ignored
  - `bridge/tguser/events.py` — **TgEventsEngine**: the only place touching the
    Telethon dispatcher; swallows+logs handler exceptions
  - `bridge/tguser/facade.py` — **TgSelfBot** + module-level `register()` with the
    exact legacy signature
- `main.py` builds its client via `TgSelfSession.build` and imports `register`
  from `bridge.tguser`; wizard `_tg_*` methods + `probe_tg_access` + `_tg_username`
  now delegate to the engines; `bridge/tg_user.py` kept as a re-export shim
- No behavior change; **217 tests green** (25 new offline engine tests), ruff clean

[2.7.0]: https://github.com/parham7991/tg-bale-bridge/compare/v2.6.0...v2.7.0

## [2.6.0] - 2026-09-22

### Changed — ✈️ Telegram control bot: modular engine package
- **All Telegram-bot logic extracted into `bridge/tgbot/`** — same per-section
  modules+engines pattern as `bridge/bale/` and `bridge/dashboard/`:
  - `bridge/tgbot/types_map.py` — pure mappings: START/SETUP texts, private-chat
    check, sender extraction, forward detection (all 3 Bot-API forward shapes)
  - `bridge/tgbot/session.py` — **TgBotSession**: bot identity (`get_me`), offset
    persistence (`tgbot_offset`), listen loop
  - `bridge/tgbot/claim.py` — **ClaimEngine**: automatic admin (first `/start`
    claims the bot) or the 🔒 owner-locked refusal
  - `bridge/tgbot/guards.py` — **GuardsEngine**: admin check + refusal message
  - `bridge/tgbot/routing.py` — **TgBotEventRouter**: full event dispatch
    (callback → wizard, no-admin → claim, setup → wizard, active wizard →
    handle_text, non-admin → 🔒, rest → admin panel)
  - `bridge/tgbot/facade.py` — **TgAdminBot**: compatibility façade composing
    all engines (unchanged public surface: `start()` / `on_update` / `_is_admin`)
- `main.py` imports from `bridge.tgbot`; `bridge/tg_bot.py` kept as a one-line
  re-export shim — no breaking imports
- No behavior change; **192 tests green** (19 new offline engine tests), ruff clean

[2.6.0]: https://github.com/parham7991/tg-bale-bridge/compare/v2.5.0...v2.6.0

## [2.5.0] - 2026-09-22

### Changed — 🔐 Bale selfbot login: dedicated engine
- **All remaining Bale-selfbot auth logic extracted into `bridge/bale/login.py`**
  (**BaleLoginEngine**) — the last selfbot logic that lived outside the package:
  - `request_code()` / `validate_code()` — two-step phone auth with the login
    transaction kept inside the engine (was duplicated inline in the wizard)
  - `build_client()` / `session_path()` — single source for session-file
    normalization (`.bale` suffix + mkdir; was duplicated in 3 places)
  - `run_interactive()` — the console flow of `login_bale.py`
- `login_bale.py` is now a thin wrapper over the engine
- `wizard._bale_request_code` / `wizard._bale_validate` delegate to the engine —
  also fixes a latent crash (the wizard's `_txns` dict was never initialized)
- 12 new offline tests (session path, both auth steps, auth/network errors,
  pending-txn state, wizard + script delegation) — **173 total**, ruff clean

[2.5.0]: https://github.com/parham7991/tg-bale-bridge/compare/v2.4.0...v2.5.0

## [2.4.0] - 2026-09-22

### Changed — 🟡 Bale logic: from one 741-line file to a modular engine package
- **All Bale-side logic extracted into `bridge/bale/`** — every section its own module
  with one focused engine (same pattern as the v2.3.0 dashboard refactor):
  - `bridge/bale/types_map.py` — pure mappings: chat types, media classification, wrapper unwrapping
  - `bridge/bale/session.py` — **BaleSession**: shared state (aiobale client, id/file/date caches, lifecycle)
  - `bridge/bale/resolver.py` — **ResolverEngine**: chat ids, usernames, chat types, reply refs
  - `bridge/bale/normalize.py` — **NormalizeEngine**: internal Bale message ⇄ Bot-API dict
  - `bridge/bale/events.py` — **EventsEngine**: dispatcher wiring, `deleted_messages` surfacing, listen loop
  - `bridge/bale/sender.py` — **SenderEngine**: every `send_*` with full fallback chain (gif/sticker/video_note/…)
  - `bridge/bale/editor.py` — **EditorEngine**: edit text/caption + delete with cached dates
  - `bridge/bale/files.py` — **FilesEngine**: download + access-hash cache
  - `bridge/bale/admin_ops.py` — **AdminOpsEngine**: invite + make-user-admin (selfbot promotes the bot)
  - `bridge/bale/profile.py` — **ProfileEngine**: `get_me` / `get_chat`
  - `bridge/bale/gateway.py` — **BaleBotGateway**: resolve + access probe (single source for admin/wizard/dashboard)
  - `bridge/bale/routing.py` — **BaleEventRouter**: all Bale event routing (selfbot stream + hybrid bot panel)
  - `bridge/bale/facade.py` — **BaleUserAPI**: compatibility façade composing all engines
- `main.py` now delegates Bale event routing to `BaleEventRouter`; `admin._resolve_bale`
  and `wizard.probe_bale_access` (also used by the dashboard) now delegate to `BaleBotGateway`
- `bridge/bale_user.py` kept as a one-line re-export shim — no breaking imports
- No behavior change; **161 tests green**, ruff clean

[2.4.0]: https://github.com/parham7991/tg-bale-bridge/compare/v2.3.0...v2.4.0

## [2.3.0] - 2026-09-22

### Changed — 🧱 per-section modules & engines (backend architecture)
- **Dashboard backend split from one flat file into a package** — every section is its
  own module with one focused engine:
  - `bridge/dashboard/app.py` — Dashboard facade + aiohttp assembly
  - `bridge/dashboard/api.py` — thin HTTP layer (error/CSRF/session middlewares, handlers)
  - `bridge/dashboard/auth.py` — **AuthEngine**: PBKDF2, sessions, lockout (no HTTP knowledge)
  - `bridge/dashboard/context.py` — **RuntimeCtx**: typed live-state access for all engines
  - `bridge/dashboard/engines/{status,pairs,control,logs,ops}.py` — domain engines that
    raise `DashboardError(msg, status)`; zero HTTP concerns
- Fixed: control-bot identity now reported correctly in `/api/status` (was always empty —
  it read a key nobody populated; now sourced from the admin panel's live info), and
  tokens/phones are stripped from every account snapshot
- Frontend untouched (`dash.html` moved into the package) — same API contract
- 20 new engine-level tests (auth flows, lockout, session lifecycle, salted hashes,
  pairs CRUD, control pause/resume, status snapshot + no-token-leak, logs, ops guards) —
  **161 total**, ruff clean

[2.3.0]: https://github.com/parham7991/tg-bale-bridge/compare/v2.2.0...v2.3.0

## [2.2.0] - 2026-09-22

### Added — 🌐 the web dashboard
- **Full web dashboard** (`bridge/dashboard.py` + `bridge/dash.html`) served by aiohttp
  on the same event loop — zero new dependencies
  - live status cards (pairs, mapped messages, Bale mode, uptime, pause state)
  - pairs table: switch direction inline, delete, add via modal (real resolution of
    @usernames/ids through the admin resolvers)
  - global pause/resume toggle (persisted), **live color-coded log terminal**
  - 🔓 real access probes and 🛡 bot promotion — same engines as the bot commands
  - dashboard-credentials management (change password from the browser)
- **Auth**: PBKDF2-HMAC-SHA256 (100k iters) · HttpOnly SameSite=Strict session cookie ·
  CSRF header guard · 60s lockout after 5 failed logins
- **Bot integration**: `/dashboard` (creates + shows one-time initial password),
  `/passwd <new>`, `/dashuser <name>`, wizard button 🌐 داشبورد
- Config: `DASH_ENABLED` / `DASH_HOST` / `DASH_PORT` (default 0.0.0.0:8080);
  docker-compose exposes the port
- Runs in **both** boot modes (installer + full bridge)
- 15 new tests (auth, CSRF, rate-limit, pairs CRUD, control, logs, password rotation,
  access/promote guards) — **141 total**, ruff clean

[2.2.0]: https://github.com/parham7991/tg-bale-bridge/compare/v2.1.0...v2.2.0

## [2.1.0] - 2026-09-22

### Added — 🛡 the selfbot can now promote the Bale bot itself
- **`BaleUserAPI.add_admin(chat, user)`** — when the Bale selfbot is a channel admin,
  it can add the Bale bot to the channel and grant admin: `search_username` (resolve
  the bot with its access_hash) → `invite_user` → `make_user_admin` (aiobale internal
  API); "already member" is tolerated, denials surface as clear errors
- Wizard button **🛡 ادمین‌کردن ربات** — runs the flow for every paired channel and
  finishes with a **real send-test through the bot itself** (✔/✘ per channel)
- New admin command **`/promote [@bot]`** (works from every panel surface; in bot
  mode returns a friendly hint)
- 10 new tests (FSM, invite/promote ordering, already-member tolerance, denial
  errors, private-chat guard) — **126 total**, ruff clean

[2.1.0]: https://github.com/parham7991/tg-bale-bridge/compare/v2.0.0...v2.1.0

## [2.0.0] - 2026-09-22

### Added — 🧙‍♂️ the one-token installer
- **`.env` now needs only `TG_BOT_TOKEN`** — everything else is configured from inside
  the Telegram control bot, with an inline-button wizard (`/setup`)
- **First `/start` claims admin** — no numeric IDs in config, ever
- **Wizard flows** (all conversational, inside the bot chat):
  - 📱 **Telegram selfbot**: api_id → api_hash → phone → code → optional 2FA password
    (real Telethon `send_code_request`/`sign_in`, session persisted)
  - 🟡 **Bale selfbot**: phone → SMS code (aiobale `start_phone_auth`/`validate_code`,
    session file written automatically)
  - 🤖 **Bale bot**: paste token → validated via `getMe`
  - 🔗 **Channel pairing**: forward a Telegram-channel message *or* send @username →
    send the Bale channel @username → pick direction with inline buttons
    (`both` / `tg2bale` / `bale2tg`) → saved instantly
- **Live access verification** — after pairing (and on demand via the new `/access`
  command) every configured account is probed *for real*: Telegram self reads the
  channel, Bale self/bot send+delete a probe message — report shows ✔/✘ per account
- **Auto-restart** — finishing the wizard re-execs `main.py` and the full bridge boots
- `bridge/store.py` — DB-backed runtime settings (accounts, admin, tokens) so restarts
  need no .env beyond the bot token; `.env.example` rewritten (minimal-first)
- 19 new tests (FSM transitions, admin claim, callback routing, probes, /access) —
  **116 total**, ruff clean

[2.0.0]: https://github.com/parham7991/tg-bale-bridge/compare/v1.3.0...v2.0.0

## [1.3.0] - 2026-09-22

### Added
- 🎛 **Quad-surface admin panel** — the identical command panel now answers from FOUR
  surfaces: Bale bot chat · **Bale self-chat** (message yourself in Bale — the selfbot
  replies!) · Telegram control bot · Telegram Saved Messages
- **Hybrid Bale mode** — with `BALE_MODE=user` *and* `BALE_TOKEN` together, the Bale bot
  runs alongside the selfbot as an extra admin surface (channel mirroring stays on the
  user session only — no duplicates, separate `bale_bot_offset`)
- **Zero-config Bale admin** — in user mode `ADMIN_BALE_ID` defaults to your own account
  id, so messaging yourself `/help` in Bale just works
- `/status` and `/whoami` are now mode-aware: selfbot vs bot, active admin surfaces,
  two-way delete coverage in user mode
- 4 new surface tests (97 total)

[1.3.0]: https://github.com/parham7991/tg-bale-bridge/compare/v1.2.1...v1.3.0

## [1.2.1] - 2026-09-22

### Fixed
- **`bale_user`: dispatcher registration** — aiobale's `Router.register` is a
  decorator-factory: `dp.message(handler)` silently registered the handler as a
  *filter*, so zero handlers ever fired. Correct form: `dp.message()(handler)`.
  Found by frame-level live debugging on a real account.
- **`get_me` / `get_chat`** — read name/username from `client.me.user` (UserAuth),
  unwrap aiobale value-wrappers (e.g. `StringValue`), and pass the required
  `chat_type` to `load_user`.
- `live_test/local_kit.py` battery is now **event-driven** (edit/delete verified via
  real echo events) — aiobale's `load_history` fails to parse messages sent through
  the API (library-side `MessageData` model bug), so history is never used.

### Verified live (real account, real server)
- WebSocket connect · get_me · send text & photo · edit · delete
- Live events: `message`, `edited_message`, **`message_deleted`** — including
  third-party deletions inside groups, the feed that powers Bale→Telegram
  delete sync.

[1.2.1]: https://github.com/parham7991/tg-bale-bridge/compare/v1.2.0...v1.2.1

## [1.2.0] - 2026-09-22

### Added
- 🕵️ **Bale selfbot mode (`BALE_MODE=user`)** — post to Bale channels with your own user
  account via [`aiobale`](https://github.com/aminmadaniofficial/aiobale); no need to add
  any bot as channel admin (which new Bale versions refuse anyway)
- `bridge/bale_user.py` — `BaleUserAPI`, a drop-in `BotAPI`-compatible adapter over
  aiobale: normalizes internal messages to Bot-API shape (media classified by mime),
  caches dates/access-hashes (persistent in `meta`) for delete & download, resolves
  `@usernames`, degrades sticker/video-note/location/contact/poll gracefully
- `login_bale.py` — one-time interactive phone + SMS login; session saved to
  `data/session.bale`, no password stored
- **Bale→Telegram delete sync** in user mode — aiobale delivers `message_deleted`
  events (impossible with the Bot API); routed as a `deleted_messages` pseudo-update
  to the new `Bridge.on_bale_delete` worker job, with two-way echo guards
- Config: `BALE_MODE` (bot/user), `BALE_SESSION`, `BALE_PHONE`; `BALE_TOKEN` is now
  optional in user mode
- README troubleshooting: "the Bale bot can't be added to a channel" — mobile/web
  workarounds plus the definitive selfbot fix
- Tests: 13 new offline tests (`tests/test_bale_user.py`) — normalization, delete
  events, send fallbacks, delete-sync (93 total)

### Changed
- `main.py` wires either the Bale bot or the selfbot; in user mode private chats are
  answered **only** to `ADMIN_BALE_ID` (a human account must never auto-reply to
  strangers)
- Honest-limitations section rewritten per mode (20 MB getFile cap and 50/10 MB
  upload caps apply to bot mode only)

[1.2.0]: https://github.com/parham7991/tg-bale-bridge/compare/v1.1.0...v1.2.0

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
