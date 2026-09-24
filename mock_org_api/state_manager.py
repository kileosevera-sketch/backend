"""
Persistent state manager for the mock organization API.
Stores all records in mock_state.json so restarts don't lose data.
"""

import json
import os
from datetime import datetime
from threading import Lock


STATE_FILE = os.path.join(os.path.dirname(__file__), "mock_state.json")
_lock = Lock()


def _empty_state():
    return {
        "complaints": [],
        "warranty_claims": [],
        "service_records": [],
        "product_returns": [],
        "failures": [],
        "next_ids": {
            "complaint": 20000,
            "warranty": 30000,
            "service": 40000,
            "return": 50000,
            "failure": 60000,
        },
        "last_updated": datetime.utcnow().isoformat(),
    }


def _save_unlocked(state: dict):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, default=str)


def load_state() -> dict:
    """Load state from disk. Creates empty state if file missing."""
    with _lock:
        if not os.path.exists(STATE_FILE):
            state = _empty_state()
            _save_unlocked(state)
            return state
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            state = _empty_state()
            _save_unlocked(state)
            return state


def save_state(state: dict):
    """Save state to disk."""
    with _lock:
        state["last_updated"] = datetime.utcnow().isoformat()
        _save_unlocked(state)


def append_records(store_name: str, records: list[dict]):
    """Append records to a store and persist."""
    state = load_state()
    state[store_name].extend(records)
    save_state(state)


def get_records(store_name: str) -> list[dict]:
    """Get all records from a store."""
    state = load_state()
    return state.get(store_name, [])


def next_id(counter_name: str) -> int:
    """Get and increment the next ID for a counter."""
    state = load_state()
    n = state["next_ids"].get(counter_name, 10000)
    state["next_ids"][counter_name] = n + 1
    save_state(state)
    return n


def reset_state():
    """Wipe everything. Use with care."""
    save_state(_empty_state())


def get_stats() -> dict:
    state = load_state()
    return {
        "counts": {k: len(v) for k, v in state.items() if isinstance(v, list)},
        "next_ids": state.get("next_ids", {}),
        "last_updated": state.get("last_updated"),
    }