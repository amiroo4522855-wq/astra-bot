#!/usr/bin/env bash
# انتشارِ امن روی گیت‌هاب — توکن هرگز در مخزن ذخیره نمی‌شود
# استفاده:  GITHUB_TOKEN=ghp_xxx bash scripts/deploy.sh
set -euo pipefail
cd "$(dirname "$0")/.."
REPO="amiroo4522855-wq/astra-bot"
TOKEN_FILE="/tmp/gh_token"
WORKFLOW="astra-24x7.yml"

# ۱) دریافتِ امنِ توکن
if [[ -n "${GITHUB_TOKEN:-}" ]]; then
  printf '%s' "$GITHUB_TOKEN" > "$TOKEN_FILE"
fi
if [[ ! -s "$TOKEN_FILE" ]]; then
  read -rsp "توکنِ گیت‌هاب: " TK; echo
  printf '%s' "$TK" > "$TOKEN_FILE"; unset TK
fi
chmod 600 "$TOKEN_FILE"
trap 'git remote set-url origin "https://github.com/'"$REPO"'.git" 2>/dev/null || true; rm -f '"$TOKEN_FILE" EXIT

# ۲) بررسی‌های پیش از انتشار
echo "▫️ بررسی کد…"
python3 -m compileall -q astra
python3 -m unittest discover -s tests 2>&1 | tail -2
python3 simulate.py 2>&1 | grep -E "بن‌بست|خطاها" || true

# ۳) کامیت در صورت وجود تغییر
if [[ -n "$(git status --porcelain)" ]]; then
  git add -A
  git -c user.name="Astra Bot" -c user.email="astra@bot.local" \
      commit -q -m "🚀 انتشار از اسکریپت $(date '+%Y-%m-%d %H:%M')"
fi

# ۴) پوش
git remote remove origin 2>/dev/null || true
git remote add origin "https://$(cat "$TOKEN_FILE")@github.com/$REPO.git"
git fetch -q origin main || true
git -c user.name="Astra Bot" -c user.email="astra@bot.local" rebase origin/main || {
  echo "❌ تداخل در rebase — رفع کن و دوباره اجرا کن"; git rebase --abort 2>/dev/null || true; exit 1; }
git push -u origin main
echo "✅ پوش انجام شد: $(git log --oneline -1)"

# ۵) لغوِ اجراهای قدیمی و راه‌اندازیِ ربات ۲۴ساعته
API="https://api.github.com/repos/$REPO"
AUTH=(-H "Authorization: Bearer $(cat "$TOKEN_FILE")" -H "Accept: application/vnd.github+json")
# فقط اجرای قبلیِ رباتِ ۲۴ساعته لغو می‌شود (اجرای CI/Testها دست‌نخورده می‌ماند)
for RUN in $(curl -s "${AUTH[@]}" "$API/actions/runs?status=in_progress&per_page=20" \
             | python3 -c "import sys,json;print(' '.join(str(r['id']) for r in json.load(sys.stdin).get('workflow_runs',[]) if r['name']=='Astra Bot 24x7'))"); do
  curl -s -X POST "${AUTH[@]}" "$API/actions/runs/$RUN/cancel" >/dev/null && echo "▫️ اجرای قبلیِ ربات ($RUN) لغو شد"
done
curl -s -X POST "${AUTH[@]}" "$API/actions/workflows/$WORKFLOW/dispatches" \
     -d '{"ref":"main"}' >/dev/null && echo "✅ ربات ۲۴ساعته راه‌اندازی شد"

# ۶) تأیید نهایی
sleep 6
echo "▫️ وضعیتِ صفحات:"
curl -s -o /dev/null -w "   index.html → %{http_code}\n" \
     "https://amiroo4522855-wq.github.io/astra-bot/"
echo "▫️ ربات:"
curl -s "https://api.telegram.org/bot$(grep TELEGRAM_BOT_TOKEN .env | cut -d= -f2-)/getMe" \
     | python3 -c "import sys,json;r=json.load(sys.stdin)['result'];print('   @'+r['username'],'·',r['first_name'])"
