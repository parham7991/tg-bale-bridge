# 🚢 Deployment Guide

## 1 · Virtualenv (any Linux VPS)

```bash
sudo apt update && sudo apt install -y python3-venv git
git clone https://github.com/parham7991/tg-bale-bridge.git
cd tg-bale-bridge
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # then edit values
python login.py           # one-time Telegram login (stores data/tg.session)
python main.py
```

## 2 · Docker Compose

```bash
cp .env.example .env      # edit values
docker compose run --rm bridge python login.py   # one-time login
docker compose up -d
docker compose logs -f
```

Data (SQLite DB + Telegram session) persists in `./data/`.

## 3 · systemd service

`/etc/systemd/system/tg-bale-bridge.service`:

```ini
[Unit]
Description=TG-Bale Bridge
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=bridge
WorkingDirectory=/opt/tg-bale-bridge
EnvironmentFile=/opt/tg-bale-bridge/.env
ExecStart=/opt/tg-bale-bridge/.venv/bin/python main.py
Restart=always
RestartSec=5

# hardening
NoNewPrivileges=true
PrivateTmp=false
ProtectSystem=full

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now tg-bale-bridge
journalctl -u tg-bale-bridge -f
```

## 4 · First-run checklist

- [ ] `TG_API_ID`, `TG_API_HASH`, `TG_PHONE` set (from <https://my.telegram.org>)
- [ ] `BALE_TOKEN` set (from `@botfather` in Bale)
- [ ] `python login.py` completed once — `data/tg.session` exists
- [ ] Telegram account is a member (ideally admin) of every source channel
- [ ] Bale bot is **admin** of every Bale channel with post/edit/delete rights
- [ ] Sent `/start` to the Bale bot, put your id into `ADMIN_BALE_ID`, restarted
- [ ] Created pairs with `/add …` and verified with `/test <id>`

## 5 · Operations

| Task | Command |
|---|---|
| Logs (docker) | `docker compose logs -f` |
| Logs (systemd) | `journalctl -u tg-bale-bridge -f` |
| Update | `git pull && pip install -r requirements.txt && sudo systemctl restart tg-bale-bridge` |
| Backup | copy `data/` (contains session + mapping DB) to a safe place — **encrypt it** |
| Start clean | stop service, delete `data/bridge.db`, start (pairs must be re-added) |

## 6 · Production tips

- Run **one instance per Telegram account** — two instances sharing one session will fight.
- If you mirror high-volume channels, consider a paid **Bale Business API** base URL
  (`https://tapi.bale.ai/business/bot<TOKEN>/<METHOD>`) and set `BALE_API_BASE`.
- Restrict permissions: `chmod 600 .env data/tg.session`.
- The bridge auto-handles rate limits (`retry_after`), but avoid pairing hundreds of
  channels on a single bot.
