"""نقطه شروع پل همگام‌سازی تلگرام ⇄ بله — لانچر نازک.

دو حالت بوت:
• حالت نصاب — فقط TG_BOT_TOKEN لازم است؛ بات تلگرام ویزارد نصب را می‌چرخاند
  (سلف تلگرام، سلف بله، ربات بله، جفت کانال‌ها، تست دسترسی) و در پایان خودش ری‌استارت می‌شود.
• حالت کامل — همه حساب‌ها از store/.env آماده‌اند؛ پل کامل بالا می‌آید.

همهٔ منطق در ``bridge.runtime`` (بستهٔ Runtime) است؛ این فایل فقط اجرا می‌کند.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from bridge.runtime import Runtime  # noqa: E402

if __name__ == "__main__":
    Runtime.cli()
