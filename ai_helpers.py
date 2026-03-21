
import json
import os

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

from typing import Optional

def get_client_memory(client_name: str) -> Optional[dict]:
    mem = load_memory()
    return mem.get("clients", {}).get(client_name)

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
    notes: str = None
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
            "history": []
        }
    else:
        existing = clients[client_name]
        existing["address"] = address or existing.get("address")
        existing["device"] = device or existing.get("device")
        existing["last_service"] = last_service or existing.get("last_service")
        existing["service_type"] = service_type or existing.get("service_type")
        existing["technician"] = technician or existing.get("technician")
        existing["issue"] = issue or existing.get("issue")
        existing["solution"] = solution or existing.get("solution")
        existing["client_type"] = client_type or existing.get("client_type")
        existing["notes"] = notes or existing.get("notes")

    # Tambah ke riwayat
    clients[client_name].setdefault("history", [])
    clients[client_name]["history"].append({
        "date": last_service,
        "type": service_type,
        "tech": technician,
        "issue": issue,
        "solution": solution
    })

    save_memory(mem)
    return clients[client_name]
