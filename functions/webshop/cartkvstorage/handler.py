# functions/webshop/cartkvstorage/handler.py

import time

async def handler(event, context=None, call_function=None):
    """
    Simuliert eine einfache cartkvstorage-Funktion.
    Erwartet ein Event mit einem 'operation'-Feld.
    """

    print("[cartkvstorage] Event empfangen:", event)

    operation = event.get("operation", "").lower()
    user_id = event.get("userId", "unknown")
    item = event.get("item", {})

    if operation == "add":
        print(f"[cartkvstorage] Füge Artikel für User {user_id} hinzu:", item)
        _simulate_workload()  # Rechenlast wie eratosthenes()
        return {
            "status": "added",
            "userId": user_id,
            "item": item
        }

    elif operation == "get":
        print(f"[cartkvstorage] Gebe Cart für User {user_id} zurück")
        return {
            "userId": user_id,
            "items": [{"productId": "QWERTY", "quantity": 2}]
        }

    elif operation == "empty":
        print(f"[cartkvstorage] Leere Cart für User {user_id}")
        return {
            "status": "emptied",
            "userId": user_id
        }

    else:
        print(f"[cartkvstorage] ❗ Unbekannte Operation: {operation}")
        return {
            "error": "Unbekannte Operation",
            "received_operation": operation
        }


def _simulate_workload(limit: int = 500_000):
    """Rechenintensive Aufgabe (Primzahlen finden) – simuliert Latenz."""
    primes = []
    nums = list(range(2, limit))
    for i in nums:
        if all(i % p != 0 for p in primes):
            primes.append(i)

