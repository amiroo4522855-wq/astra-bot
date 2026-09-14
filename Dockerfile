# ============================================================
#  ایمیج داکر برای ربات آسترا
# ============================================================
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# ffmpeg برای yt-dlp (استخراج صدا و ترکیب ویدیو)
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install -r requirements.txt \
    && pip install --no-cache-dir yt-dlp gTTS "qrcode[pil]"

COPY . .

# داده‌ها (دیتابیس و کش) در ولوم نگه داشته می‌شوند
VOLUME ["/app/data"]

# حالت پیش‌فرض: وب‌هوک (با متغیر محیطی RUN_MODE=polling به حالت polling برو)
ENV RUN_MODE=webhook
EXPOSE 8443

CMD ["sh", "-c", "if [ \"$RUN_MODE\" = \"polling\" ]; then python main.py; \
     else python webhook_server.py --host 0.0.0.0 --port 8443 --path ${WEBHOOK_PATH:-/webhook}; fi"]
