async def add_cart_item(event, call_function):
    print("[add_cart_item] Eingabe:", event)

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
