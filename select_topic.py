"""
Selects a daily topic from topics.json based on the time slot.

Slot auto-detection (UTC):
  06:00 – 09:59  →  morning
  12:00 – 15:59  →  afternoon
  18:00 – 23:59  →  evening  (also the default)

Topic rotation: uses today's date + slot as a deterministic seed so the
same topic is never picked twice on the same day, and they cycle through
the full list over time.
"""
import json
import argparse
import hashlib
from datetime import date, datetime, timezone


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

    # Deterministic daily rotation: same slot always picks same topic per day
    seed_str = f"{date.today().isoformat()}_{slot}"
    seed = int(hashlib.md5(seed_str.encode()).hexdigest(), 16)
    index = seed % len(topic_list)
    return topic_list[index]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Select a topic for the current time slot.")
    parser.add_argument(
        "--slot",
        choices=["morning", "afternoon", "evening"],
        default=None,
        help="Force a specific slot. Auto-detects from UTC hour if omitted.",
    )
    args = parser.parse_args()

    slot = args.slot or get_current_slot()
    print(select_topic(slot))
