"""رادیوهای آنلاینِ آماده‌ی پخش."""
from __future__ import annotations

# نام، نشانی Stream، توضیح کوتاه
STATIONS = [
    ("📻 رادیو جوان", "https://stream.radiojavan.com/", "موزیک پاپ و هیپ‌هاپ"),
    ("🎶 رادیو فردا", "https://stream.radiofarda.com/", "خبر و موسیقی"),
    ("🎙 رادیو ایران", "https://ice1.radio.ir/ir/128", "شبکه سراسری"),
    ("🎧 رادیو پیام", "https://stream.peyamradio.com:8000/;", "گفتگو و موسیقی"),
    ("🌙 رادیو آرام", "https://stream.radiojavan.com/m/", "موزیک آرام"),
]


def list_stations() -> str:
    lines = ["📻 رادیو آنلاین", "───────────────",
             "یکی از ایستگاه‌ها رو انتخاب کن:"]
    lines += [f"{index}. {name} — {desc}" for index, (name, _, desc) in enumerate(STATIONS, 1)]
    return "\n".join(lines)


def station(index: int) -> tuple[str, str] | None:
    try:
        name, url, _ = STATIONS[index - 1]
        return name, url
    except IndexError:
        return None
