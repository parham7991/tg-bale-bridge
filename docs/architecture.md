# 🏗 Architecture

## Components

```mermaid
flowchart LR
    subgraph TG[Telegram]
        CH1[(Channel)]
    end
    subgraph BRIDGE[tg-bale-bridge]
        TL[Telethon\nuser session]
        Q[(job queues)]
        ENGINE[transfer engine]
        DB[(SQLite\npairs · msg_map · caches)]
        ADMIN[admin command parser]
        BA[Bale Bot API client]
    end
    subgraph BL[Bale · بله]
        CH2[(Channel)]
        BOT{{Bale bot}}
    end

    CH1 <-->|MTProto events\nnew · edit · delete| TL
    TL <--> Q <--> ENGINE
    ENGINE <--> DB
    ENGINE <--> BA
    BA <-->|HTTPS\ngetUpdates · send* · edit · delete| BOT
    BOT <-->|channel posts| CH2
    BOT <-->|private chat\ncommands| ADMIN
    ADMIN <--> ENGINE
```

| Component | File | Responsibility |
|---|---|---|
| Telethon session | `bridge/tg_user.py` | Receives `NewMessage` / `MessageEdited` / `MessageDeleted`; routes Saved-Messages to admin, everything else to the engine |
| Job queues | `bridge/transfer.py` | Two FIFO queues (TG→Bale, Bale→TG) keep ordering deterministic |
| Transfer engine | `bridge/transfer.py` | Media classification, download/re-upload, albums, replies, forwards, edits, deletes |
| Bale client | `bridge/bale_api.py` | Raw Bot-API calls, multipart uploads, file downloads, long-polling, `retry_after` handling |
| Formatter | `bridge/formatter.py` | Telegram entities ⇄ Bale Markdown, UTF-16 offset math, renderers for polls/dice/venues/services |
| Store | `bridge/db.py` | Channel pairs, message mapping (for replies/edits/deletes), loop-prevention ledger |
| Admin | `bridge/admin.py` | `/add`, `/list`, `/mode`, `/remove`, `/test`, `/id`, `/status` |

## Data model

```mermaid
erDiagram
    PAISONS {
        int id PK
        int tg_chat_id
        string tg_username
        string bale_chat_id
        string bale_username
        string mode "tg2bale | bale2tg | both"
    }
    MSG_MAP {
        int id PK
        int pair_id FK
        string src_platform
        string src_chat
        int src_msg
        string dst_platform
        string dst_chat
        int dst_msg
    }
    SENT {
        string platform
        string chat
        int msg
        float created_at
    }
    SENT_FP {
        string platform
        string chat
        string fp
        float created_at
    }
```

> `msg_map` is the heart of fidelity: it remembers which message on one platform
> corresponds to which message on the other — enabling **replies that stay replies**,
> **edits that edit the mirror**, and **deletes that delete the copy**.

## Message lifecycle (Telegram → Bale)

```mermaid
sequenceDiagram
    autonumber
    participant U as User / Channel
    participant T as Telethon session
    participant Q as TG queue
    participant E as Engine
    participant D as SQLite
    participant B as Bale bot API
    participant C as Bale channel

    U->>T: post (text / media / album)
    T->>D: was_sent? (loop guard)
    T->>Q: enqueue
    Q->>E: dequeue (ordered)
    E->>D: pairs_for_tg(chat)
    loop each pair
        E->>E: download media → convert entities
        E->>B: sendMessage / sendPhoto / sendMediaGroup / …
        B->>C: publish
        B-->>E: message_id(s)
        E->>D: msg_map(src↔dst) + mark_sent + fingerprint
    end
```

## Loop prevention (two layers)

1. **ID ledger** — every message the bridge *creates* is recorded (`platform, chat, msg_id`).
   When an event for that exact ID comes back, it is dropped (and the ledger entry consumed).
2. **Content fingerprint** — covers the race where a platform echoes our post *before* our
   HTTP call returns (Bale `getUpdates` vs `sendMessage`). A short-TTL hash of `kind|text`
   suppresses the duplicate.

## Fidelity strategy

| Situation | Strategy |
|---|---|
| Album (media group) | Buffered for `ALBUM_DELAY` seconds, sent via `sendMediaGroup`; falls back to sequential sends |
| Reply | Resolved through `msg_map` to the destination's counterpart message |
| Forward | Content re-uploaded with an attribution header (`🔁 باز‌ارسال از: …`) |
| Edit — text/caption | In-place `editMessageText` / `editMessageCaption` (or `Message.edit`) |
| Edit — media replaced | Delete + resend + `msg_map` row updated |
| Delete (Telegram side) | `deleteMessage` on Bale for every mapped copy |
| Unsupported (poll, dice…) | Human-readable text rendering |
| Oversized files | Upload cap respected (50 MB / 10 MB photos); notice message instead of silent loss |
