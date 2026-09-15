"""ساخت docs/data/brain.json از مغزِ پایتون (یک منبعِ حقیقت برای ربات و مینی‌اپ)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from astra.services import brain          # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "docs" / "data" / "brain.json"

INTENTS = [
    ("greet", list(brain.GREETINGS)),
    ("mood", list(brain.MOODS)),
    ("thanks", list(brain.THANKS)),
    ("bye", list(brain.BYES)),
    ("praise", list(brain.PRAISE)),
    ("complaint", list(brain.COMPLAINT)),
    ("who", list(brain.WHOS)),
    ("ability", list(brain.ABILITIES)),
    ("joke", list(brain.JOKE_WORDS)),
    ("poem", list(brain.POEM_WORDS)),
]

data = {
    "version": 2,
    "name": brain.BOT_NAME,
    "about": brain.ABOUT_TEXT,
    "ability": brain.ABILITY_TEXT,
    "fallback": list(brain.UNKNOWN_REPLIES),
    "intents": [{"kind": kind, "patterns": sorted(set(p.lower() for p in patterns),
                                                  key=len, reverse=True)}
                for kind, patterns in INTENTS],
    "advice": [{"keywords": [brain.normalize(k) for k in keywords], "text": text}
               for keywords, text in brain.ADVICE],
    "replies": {
        "greet": list(brain.GREET_REPLIES),
        "mood": list(brain.MOOD_REPLIES),
        "thanks": list(brain.THANKS_REPLIES),
        "bye": list(brain.BYE_REPLIES),
        "praise": list(brain.PRAISE_REPLIES),
        "complaint": list(brain.COMPLAINT_REPLIES),
    },
}

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"✅ {OUT.relative_to(OUT.parents[2])} · {len(data['intents'])} نیت · "
      f"{OUT.stat().st_size} بایت")
