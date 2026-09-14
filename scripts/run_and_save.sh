#!/usr/bin/env bash
# اجرای ربات در دوره‌های ۵۵ دقیقه‌ای و ذخیره‌ی دیتابیس بعد از هر دور.
# استفاده در GitHub Actions (jobs بدون نیاز به سرور شخصی).
set -u

ROUNDS="${ASTRA_ROUNDS:-6}"        # ۶ × ۵۵ دقیقه ≈ ۵.۵ ساعت
SECONDS_PER_ROUND="${ASTRA_ROUND_SECONDS:-3300}"

for round in $(seq 1 "$ROUNDS"); do
  echo "▶️ دور $round از $ROUNDS"
  timeout "$SECONDS_PER_ROUND" python -u main.py --platform telegram || true

  git add -f state/astra.db 2>/dev/null || true
  if ! git diff --quiet --cached; then
    git commit -q -m "🗄 دیتابیس ربات (دور $round) [skip ci]" || true
    git pull --rebase origin main || true
    git push origin main || echo "⚠️ ذخیره‌سازی ناموفق بود"
    echo "💾 دیتابیس ذخیره شد"
  else
    echo "💾 تغییری در دیتابیس نبود"
  fi
done

echo "🏁 پایان اجرا"
