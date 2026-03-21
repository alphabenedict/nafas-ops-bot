import json
import os
import logging
from difflib import get_close_matches
from typing import Optional, List

logger = logging.getLogger(__name__)

MEMORY_FILE = "nafasmemory.json"


def _ensure_memory_file_exists():
    if not os.path.exists(MEMORY_FILE):
        initial = {"clients": {}}
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(initial, f, indent=2, ensure_ascii=False)


def load_memory() -> dict:
    _ensure_memory_file_exists()
    with open(MEMORY_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_memory(mem: dict):
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(mem, f, indent=2, ensure_ascii=False)


def get_client_memory(client_name: str) -> Optional[dict]:
    mem = load_memory()
    return mem.get("clients", {}).get(client_name)


def search_clients(query: str, limit: int = 5) -> List[str]:
    """Fuzzy-search client names. Returns up to `limit` close matches."""
    mem = load_memory()
    all_names = list(mem.get("clients", {}).keys())
    # Case-insensitive fuzzy match
    matches = get_close_matches(query, all_names, n=limit, cutoff=0.4)
    return matches


def update_client_memory(
    client_name: str,
    address: str = None,
    device: str = None,
    last_service: str = None,
    service_type: str = None,
    technician: str = None,
    issue: str = None,
    solution: str = None,
    client_type: str = None,
    notes: str = None,
):
    mem = load_memory()
    clients = mem.setdefault("clients", {})

    if client_name not in clients:
        clients[client_name] = {
            "address": address,
            "device": device,
            "last_service": last_service,
            "service_type": service_type,
            "technician": technician,
            "issue": issue,
            "solution": solution,
            "client_type": client_type,
            "notes": notes,
            "history": [],
        }
    else:
        existing = clients[client_name]
        # Use `is not None` so empty strings can intentionally clear fields
        if address is not None:
            existing["address"] = address
        if device is not None:
            existing["device"] = device
        if last_service is not None:
            existing["last_service"] = last_service
        if service_type is not None:
            existing["service_type"] = service_type
        if technician is not None:
            existing["technician"] = technician
        if issue is not None:
            existing["issue"] = issue
        if solution is not None:
            existing["solution"] = solution
        if client_type is not None:
            existing["client_type"] = client_type
        if notes is not None:
            existing["notes"] = notes

    # Build history entry and deduplicate before appending
    history_entry = {
        "date": last_service,
        "type": service_type,
        "tech": technician,
        "issue": issue,
        "solution": solution,
    }

    history = clients[client_name].setdefault("history", [])

    # Only append if this exact entry doesn't already exist
    if history_entry not in history:
        history.append(history_entry)

    save_memory(mem)
    return clients[client_name]
