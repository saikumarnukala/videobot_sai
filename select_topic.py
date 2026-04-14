"""
Selects a daily topic from topics.json based on the time slot.

Slot auto-detection (UTC):
  06:00 – 09:59  →  morning
  12:00 – 15:59  →  afternoon
  18:00 – 23:59  →  evening  (also the default)

Topic rotation: sequential round-robin based on days elapsed since a fixed
epoch. Every topic in a slot is used exactly once before any topic repeats.
With 10 topics per slot that means each topic reappears every 10 days.
"""
import json
import argparse
from datetime import date, datetime, timezone

# Fixed epoch — day 0 of the rotation
_EPOCH = date(2026, 1, 1)


def get_current_slot() -> str:
    hour = datetime.now(timezone.utc).hour
    if 6 <= hour < 10:
        return "morning"
    elif 12 <= hour < 16:
        return "afternoon"
    else:
        return "evening"


def select_topic(slot: str) -> str:
    with open("topics.json", "r", encoding="utf-8") as f:
        topics = json.load(f)

    topic_list = topics.get(slot, topics.get("morning", []))
    if not topic_list:
        raise ValueError(f"No topics found for slot: {slot}")

    # Sequential round-robin: each topic used once before any repeats
    days_elapsed = (date.today() - _EPOCH).days
    index = days_elapsed % len(topic_list)
    return topic_list[index]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Select a topic for the current time slot.")
    parser.add_argument(
        "--slot",
        choices=["morning", "afternoon", "evening", "news"],
        default=None,
        help="Force a specific slot. Auto-detects from UTC hour if omitted.",
    )
    args = parser.parse_args()

    slot = args.slot or get_current_slot()
    print(select_topic(slot))
