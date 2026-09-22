<div align="center">

<img src="docs/assets/banner.svg" alt="TG–Bale Bridge — Telegram ⇄ Bale two-way channel sync" width="100%"/>

<br/>

[![CI](https://github.com/parham7991/tg-bale-bridge/actions/workflows/ci.yml/badge.svg)](https://github.com/parham7991/tg-bale-bridge/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-66%20✅-success)](tests/)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

**پل دوطرفهٔ همگام‌سازی کانال‌های تلگرام و بله** — هرچه یک‌طرف بگذارید، بی‌کم‌وکاست در طرف دیگر می‌نشیند.<br/>
*Two-way Telegram ⇄ Bale (بله) channel sync bridge — mirror everything.*

</div>

---

## 📑 فهرست

- [✨ چرا این پروژه؟](#-چرا-این-پروژه)
- [🎬 نمای کلی قابلیت‌ها](#-نمای-کلی-قابلیت‌ها)
- [🏗 معماری](#-معماری)
- [🚀 راه‌اندازی سریع](#-راه‌اندازی-سریع)
- [🎛 پنل مدیریت داخل ربات](#-پنل-مدیریت-داخل-ربات)
- [⚙️ پیکربندی](#️-پیکربندی)
- [🧪 تست و توسعه](#-تست-و-توسعه)
- [⚠️ محدودیت‌های صادقانه](#️-محدودیت‌های-صادقانه)
- [🗺 نقشه راه](#-نقشه-راه)
- [🤝 مشارکت](#-مشارکت)
- [📄 مجوز](#-مجوز)

## ✨ چرا این پروژه؟

| ویژگی | توضیح |
|:---|:---|
| 🔁 **دوطرفه واقعی** | با یک پارامتر جهت را انتخاب کنید: `tg2bale` ، `bale2tg` یا `both` |
| 📦 **همه‌چیز** | متن، عکس، ویدیو، وویس، موزیک، گیف، فایل، استیکر، آلبوم چندتایی، فورواردی، ریپلای، لوکیشن، مخاطب |
| ✏️ **ویرایش = ویرایش** | پیام را در تلگرام ادیت کنید → همان پیام در بله ادیت می‌شود (و برعکس) |
| 🗑 **حذف = حذف** | حذف در تلگرام، کپی را در بله پاک می‌کند |
| 🎨 **قالب‌بندی حفظ می‌شود** | بولد/ایتالیک/لینک تلگرام ⇄ Markdown بله |
| 🧩 **بدون حلقه** | نگهبان دو‌لایه (ledger شناسه + اثرانگشت محتوا) مانع بازتاب بی‌نهایت می‌شود |
| 🎛 **تنظیمات داخل ربات** | بدون ویرایش فایل؛ با چند دستور ساده جفت کانال بسازید |
| 🧪 **۶۶ تست آفلاین** | pytest شامل تست‌های واحد و سرتاسری — CI روی پایتون ۳.۱۰ تا ۳.۱۲ |
| 🐳 **داکر و systemd** | آمادهٔ استقرار روی سرور |

## 🎬 نمای کلی قابلیت‌ها

| محتوا | تلگرام→بله | بله→تلگرام |
|---|:---:|:---:|
| متن + بولد/ایتالیک/لینک | ✅ | ✅ |
| عکس · ویدیو · وویس · موزیک · گیف · فایل | ✅ | ✅ |
| استیکر (به‌صورت تصویر/فایل) | ✅ | ✅ |
| آلبوم (رسانه گروهی) | ✅ | ✅ |
| فورواردی (با ذکر منبع) | ✅ | ✅ |
| جواب/ریپلای (به پیام معادل) | ✅ | ✅ |
| لوکیشن و مخاطب | ✅ | ✅ |
| ویدیوی دایره‌ای | ✅ (با فالبک) | ➖ *API بله ندارد* |
| نظرسنجی و تاس | ✅ (به‌صورت متن) | ➖ |
| **ویرایش پیام** | ✅ | ✅ |
| **حذف پیام** | ✅ | ⛔ *API بله روید حذف نمی‌دهد* |

## 🏗 معماری

```mermaid
flowchart LR
    subgraph TG[Telegram]
        CH1[(کانال)]
    end
    subgraph BRIDGE[tg-bale-bridge]
        TL[Telethon\nuser session]
        E[transfer engine]
        DB[(SQLite)]
        BA[Bale Bot API client]
    end
    subgraph BL[Bale · بله]
        CH2[(کانال)]
        BOT{{ربات بله}}
    end
    CH1 <-->|new · edit · delete| TL
    TL <--> E <--> DB
    E <--> BA
    BA <-->|getUpdates · send* · edit · delete| BOT
    BOT <--> CH2
```

مستندات کامل معماری (مودل داده، دیاگرام ترتیب پیام، استراتژی وفاداری):
[**docs/architecture.md**](docs/architecture.md)

## 🚀 راه‌اندازی سریع

```bash
git clone https://github.com/parham7991/tg-bale-bridge.git
cd tg-bale-bridge
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env        # ← مقادیر را کامل کنید
python login.py             # ← ورود به تلگرام (یک بار، کد تایید می‌خواهد)
python main.py              # ▶️
```

<details>
<summary>🐳 اجرا با Docker</summary>

```bash
cp .env.example .env        # ← مقادیر را کامل کنید
docker compose run --rm bridge python login.py   # ورود یک‌باره
docker compose up -d
docker compose logs -f
```
</details>

<details>
<summary>🐧 استقرار حرفه‌ای (systemd) و نکات سرور</summary>

به [**docs/DEPLOY.md**](docs/DEPLOY.md) مراجعه کنید.
</details>

**پیش از اجرا:**
1. از [my.telegram.org](https://my.telegram.org) → `api_id` و `api_hash` بگیرید
2. در بله به [`@botfather`](https://ble.ir/botfather) بروید و ربات بسازید → توکن
3. حساب تلگرام عضو کانال(های) مبدأ باشد؛ ربات بله **ادمین** کانال(های) مقصد با دسترسی ارسال/ویرایش/حذف

## 🎛 پنل مدیریت داخل ربات

به ربات بله پیام بدهید (یا در تلگرام در **پیام‌های ذخیره‌شده** خودتان بنویسید):

| دستور | کار |
|---|---|
| `/add <کانال_تلگرام> <کانال_بله> [حالت]` | اتصال دو کانال — نمونه: `/add @tg_ch @bale_ch both` |
| `/list` | فهرست جفت‌های متصل |
| `/mode <id> <حالت>` | تغییر جهت: `both` / `tg2bale` / `bale2tg` |
| `/remove <id>` | حذف یک جفت |
| `/test <id>` | پیام آزمایشی برای اطمینان از اتصال |
| `/id` *(یا فوروارد پیام از کانال)* | گرفتن شناسه عددی کانال‌ها |
| `/status` · `/help` | وضعیت و راهنما |

> 💡 برای اولین بار: `/start` را بزنید → ربات آیدی عددی‌تان را می‌گوید → در `.env` کلید `ADMIN_BALE_ID` بگذارید.

## ⚙️ پیکربندی

| کلید | الزامی | توضیح |
|---|:---:|---|
| `TG_API_ID` | ✅ | از my.telegram.org |
| `TG_API_HASH` | ✅ | از my.telegram.org |
| `TG_PHONE` | ✅ | شماره تلفن حساب تلگرام |
| `BALE_TOKEN` | ✅ | توکن ربات بله از @botfather |
| `ADMIN_BALE_ID` | ✅ | آیدی عددی شما در بله (برای دستورات) |
| `ALBUM_DELAY` | – | تاخیر جمع‌آوری آلبوم، پیش‌فرض `0.9` ثانیه |
| `BALE_POLL_TIMEOUT` | – | مدت long-polling بله، پیش‌فرض `30` ثانیه |
| `DATA_DIR` | – | مسیر دیتابیس و سشن، پیش‌فرض `./data` |

## 🧪 تست و توسعه

```bash
make dev      # نصب وابستگی‌های توسعه
make test     # اجرای ۶۶ تست آفلاین (بدون نیاز به اکانت واقعی)
make lint     # ruff
```

- CI روی هر push / PR: lint + pytest روی پایتون ۳.۱۰ / ۳.۱۱ / ۳.۱۲
- راهنمای مشارکت: [CONTRIBUTING.md](CONTRIBUTING.md)

## ⚠️ محدودیت‌های صادقانه

این‌ها سقف‌های **API خود پلتفرم‌ها** است و در [docs/architecture.md](docs/architecture.md) استراتژی جایگزین هرکدام شرح داده شده:

1. بله برای **حذف پیام** رویداد نمی‌فرستد ⇒ حذفِ بله→تلگرام ممکن نیست (بقیه جهت‌ها ✅)
2. دانلود فایل از بله: سقف `getFile` **۲۰MB** — فایل بزرگ‌تر با پیام اطلاع‌رسانی جایگزین می‌شود
3. آپلود به بله: **۵۰MB** (عکس **۱۰MB**؛ حجیم‌تر به‌صورت فایل می‌رود)
4. پک استیکر بین دو پیام‌رسان مشترک نیست ⇒ ارسال به‌صورت تصویر/فایل
5. بله متن را همیشه با Markdown خودش رندر می‌کند؛ فقط بولد/ایتالیک/لینک قابل ترجمه است
6. نظرات کانال (دیدگاه‌ها) فعلاً همگام نمی‌شوند

## 🗺 نقشه راه

- [ ] همگام‌سازی دیدگاه‌های (comments) کانال
- [ ] افزونه Bale Business API برای کانال‌های پرحجم
- [ ] تبدیل استیکر TGS به متحرک
- [ ] داشبورد وب برای مدیریت جفت‌ها
- [ ] پشتیبان‌گیری و بازیابی خودکار نگاشت پیام‌ها

## 🤝 مشارکت

ایده‌ها، گزارش باگ و PR خوش‌آمدند — [CONTRIBUTING.md](CONTRIBUTING.md) را ببینید.
اگر این پروژه برایتان مفید بود، ⭐ بزنید!

## 📄 مجوز

[MIT](LICENSE) © 2026 [Parham Khanmohammadi](https://github.com/parham7991)

<div align="center">
<sub>ساخته‌شده با Telethon و عشق — برای جامعهٔ فارسی‌زبان 🇮🇷</sub>
</div>
