# functions/webshop/cartkvstorage/cartkvstorage.py

async def cartkvstorage(event, call_function):
    """
    Simuliert eine einfache cartkvstorage-Funktion.
    Erwartet ein Event-Dictionary mit einem 'operation'-Feld und ggf. weiteren Parametern.
    """

    print("[cartkvstorage] Event empfangen:", event)

    operation = event.get("operation", "unknown")
    user_id = event.get("userId", "unknown")
    item = event.get("item", {})

    if operation == "add":
        print(f"[cartkvstorage] Füge Artikel für User {user_id} hinzu:", item)
        return {
            "status": "added",
            "userId": user_id,
            "item": item
        }

    elif operation == "get":
        print(f"[cartkvstorage] Gebe Cart für User {user_id} zurück")
        return {
            "userId": user_id,
            "items": [
                {"productId": "QWERTY", "quantity": 2}
            ]
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
