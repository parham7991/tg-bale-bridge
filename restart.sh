#!/bin/bash
# ری‌استارت امن پل — الگوی bracket مانع کشته‌شدن خود اسکریپت/سشن SSH می‌شود
# (pgrep -f با الگوی literal، هم سشن را مچ می‌کند هم اگر پروسه با مسیر مطلق
#  اجرا شده باشد — مثل nohup ... /root/tg-bale-bridge/main.py — آن را نمی‌بیند).
cd /root/tg-bale-bridge || exit 1

OLD=$(ps ax | grep "[m]ain\.py" | awk '{print $1}')
[ -n "$OLD" ] && kill $OLD 2>/dev/null

# حداکثر ۱۰ ثانیه منتظر مرگ کامل و آزادشدن پورت ۸۰۸۰ می‌مانیم
for i in $(seq 1 10); do
  ps ax | grep -q "[m]ain\.py" || break
  sleep 1
done
STILL=$(ps ax | grep "[m]ain\.py" | awk '{print $1}')
[ -n "$STILL" ] && kill -9 $STILL 2>/dev/null && sleep 1

nohup .venv/bin/python main.py >> bridge.log 2>&1 &
echo "STARTED $!"
