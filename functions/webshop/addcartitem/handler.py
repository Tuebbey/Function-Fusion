async def handler(event, context=None, call_function=None):
    print("[add_cart_item] Eingabe:", event)

    if event.get("operation") == "test":
        print("[add_cart_item] Test-Operation erkannt – simuliere Workload")
        # → Option 1: einfache Antwort
        return {
            "statusCode": 200,
            "body": True
        }

    response = await call_function(
        "cartkvstorage",
        {
            "operation": "add",
            "userId": event["userId"],
            "item": {
                "productId": event["productId"],
                "quantity": event["quantity"]
            }
        }
    )

    print("[add_cart_item] Antwort von cartkvstorage:", response)

    return {
        "status": "added",
        "response": response
    }
