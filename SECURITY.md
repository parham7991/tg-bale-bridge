# Security Policy

## Supported Versions

| Version | Supported |
| ------- | --------- |
| 1.0.x   | ✅        |

## Reporting a Vulnerability

Please open a **private security advisory** on GitHub (Security → Advisories → Report a vulnerability),
or contact the maintainer. Please do not open public issues for vulnerabilities.

## Operational Security (important!)

This tool holds **high-privilege credentials**. Please:

- 🔐 Treat `data/tg.session` **like a password** — it *is* your Telegram account.
  Never commit it, never share it, restrict file permissions (`chmod 600`).
- 🔐 Keep `.env` out of version control (already in `.gitignore`) — it holds your
  Telegram API hash and Bale bot token.
- 🚫 **Never paste tokens/keys into issues, chats or commits.** If a token ever leaks
  (e.g. it was pasted somewhere), **revoke it immediately**:
  - Telegram `api_hash`: revoke via <https://my.telegram.org>
  - Bale bot token: regenerate via `@botfather` in Bale
  - GitHub PAT: <https://github.com/settings/tokens>
- 🖥️ Run the bridge on a trusted machine/VPS only; anyone with shell access to it
  controls your Telegram account and Bale bot.
- 🧹 Rotate credentials periodically.
