"""
Selects a daily topic from topics.json based on the time slot.

Slot auto-detection (UTC):
  06:00 – 09:59  →  morning
  12:00 – 15:59  →  afternoon
  18:00 – 23:59  →  evening  (also the default)

Topic rotation: never-repeat system. Used topics are tracked in
used_topics.json so no topic is ever repeated in the channel's lifetime.
When all topics in a slot are exhausted, the script raises an error — add
more topics to topics.json.
"""
import json
import os
import sys
import argparse
from datetime import date, datetime, timezone

# Fixed epoch — day 0 of the rotation
_EPOCH = date(2026, 1, 1)
USED_TOPICS_FILE = "used_topics.json"


def _load_used_topics() -> dict:
    if os.path.exists(USED_TOPICS_FILE):
        with open(USED_TOPICS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"used": []}


def _save_used_topics(data: dict):
    with open(USED_TOPICS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def get_current_slot() -> str:
    hour = datetime.now(timezone.utc).hour
    if 6 <= hour < 10:
        return "morning"
    elif 12 <= hour < 16:
        return "afternoon"
    else:
        return "evening"


def select_topic(slot: str, run_number: int = 0, mark_used: bool = False) -> str:
    with open("topics.json", "r", encoding="utf-8") as f:
        topics = json.load(f)

    topic_list = topics.get(slot, topics.get("morning", []))
    if not topic_list:
        raise ValueError(f"No topics found for slot: {slot}")

    # Load the used-topics ledger
    used_data = _load_used_topics()
    used_set = set(used_data.get("used", []))

    # Filter out already-used topics
    available = [t for t in topic_list if t not in used_set]
    if not available:
        raise RuntimeError(
            f"ALL {len(topic_list)} topics in slot '{slot}' have been used! "
            "Add more topics to topics.json to continue."
        )

    # Pick using run_number as offset into the available pool
    if run_number > 0:
        index = run_number % len(available)
    else:
        days_elapsed = (date.today() - _EPOCH).days
        index = days_elapsed % len(available)

    chosen = available[index]

    # Optionally persist the choice so it's never picked again
    if mark_used:
        used_data.setdefault("used", []).append(chosen)
        _save_used_topics(used_data)
        print(f"[TopicSelect] Marked as used ({len(used_data['used'])} total used, "
              f"{len(available)-1} remaining in '{slot}')", file=sys.stderr)

    return chosen


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Select a topic for the current time slot.")
    parser.add_argument(
        "--slot",
        choices=["morning", "afternoon", "evening", "news"],
        default=None,
        help="Force a specific slot. Auto-detects from UTC hour if omitted.",
    )
    parser.add_argument(
        "--run-number",
        type=int,
        default=0,
        help="GitHub Actions run_number (passed from workflow to ensure unique topic per run).",
    )
    parser.add_argument(
        "--mark-used",
        action="store_true",
        help="Record the chosen topic in used_topics.json so it is never repeated.",
    )
    args = parser.parse_args()

    slot = args.slot or get_current_slot()
    print(select_topic(slot, run_number=args.run_number, mark_used=args.mark_used))
