"""جستجو و دانلود موسیقی/ویدیو با yt-dlp.

اگر yt-dlp روی سرور نصب نباشد، ربات به‌جای خطای زشت،
لینک جستجو و راهنمای نصب را نشان می‌دهد (تجربه‌ی کاربر حفظ می‌شود).
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from .. import config
from ..core.utils import format_duration

YTDLP = config.YTDLP_PATH
TIMEOUT = 240  # ثانیه


class MediaError(Exception):
    """خطای دانلود یا جستجو."""


def available() -> bool:
    return shutil.which(YTDLP) is not None


def _run(args: list[str]) -> str:
    try:
        result = subprocess.run(
            args, capture_output=True, text=True, timeout=TIMEOUT, check=False,
        )
    except FileNotFoundError as exc:
        raise MediaError("yt-dlp نصب نیست") from exc
    except subprocess.TimeoutExpired as exc:
        raise MediaError("زمان دانلود به پایان رسید؛ فایل احتمالاً خیلی بزرگ است") from exc
    if result.returncode != 0:
        stderr = (result.stderr or "").strip().splitlines()
        raise MediaError(stderr[-1][:160] if stderr else "دانلود ناموفق بود")
    return result.stdout or ""


def search(query: str, limit: int = 5) -> list[dict]:
    """جستجو در یوتیوب و برگرداندن فهرست نتایج."""
    if not available():
        raise MediaError("yt-dlp نصب نیست")
    raw = _run([YTDLP, "--flat-playlist", "--no-warnings", "--dump-json",
                f"ytsearch{limit}:{query}"])
    items: list[dict] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        items.append({
            "id": data.get("id", ""),
            "title": data.get("title", "بدون عنوان")[:80],
            "uploader": data.get("uploader") or data.get("channel") or "نامشخص",
            "duration": data.get("duration") or 0,
            "url": data.get("url") or f"https://www.youtube.com/watch?v={data.get('id', '')}",
        })
    return items


def _out_dir() -> Path:
    path = Path(config.TEMP_DIR) / "media"
    path.mkdir(parents=True, exist_ok=True)
    return path


def download_audio(url: str, bitrate: str = "192") -> Path:
    """دانلود صدا با کیفیت مشخص (128 / 192 / 320)."""
    if not available():
        raise MediaError("yt-dlp نصب نیست")
    template = str(_out_dir() / "%(title).60s.%(ext)s")
    _run([
        YTDLP, "-f", "bestaudio/best", "--extract-audio", "--audio-format", "mp3",
        "--audio-quality", bitrate, "--no-playlist", "--no-warnings",
        "-o", template, url, "--print", "after_move:filepath",
    ])
    return _newest_file()


def download_video(url: str, max_height: int = 720) -> Path:
    """دانلود ویدیو با محدودیت ارتفاع (360 / 480 / 720 / 1080)."""
    if not available():
        raise MediaError("yt-dlp نصب نیست")
    template = str(_out_dir() / "%(title).60s.%(ext)s")
    _run([
        YTDLP, "-f", f"best[height<={max_height}]/best", "--no-playlist",
        "--no-warnings", "-o", template, url, "--print", "after_move:filepath",
    ])
    return _newest_file()


def download_generic(url: str) -> Path:
    """دانلود از اینستاگرام، تیک‌تاک، پینترست و سایر سایت‌های پشتیبانی‌شده."""
    if not available():
        raise MediaError("yt-dlp نصب نیست")
    template = str(_out_dir() / "%(title).60s.%(ext)s")
    _run([YTDLP, "--no-warnings", "--no-playlist", "-o", template, url,
          "--print", "after_move:filepath"])
    return _newest_file()


def _newest_file() -> Path:
    files = [p for p in _out_dir().iterdir() if p.is_file()]
    if not files:
        raise MediaError("فایلی ساخته نشد")
    return max(files, key=lambda p: p.stat().st_mtime)


def cleanup(path: Path) -> None:
    try:
        Path(path).unlink(missing_ok=True)
    except OSError:
        pass


def youtube_search_link(query: str) -> str:
    from urllib.parse import quote
    return "https://www.youtube.com/results?search_query=" + quote(query)


def pretty_duration(seconds: int) -> str:
    return format_duration(seconds)
