# functions/webshop/getcart/handler.py

async def handler(event, context=None, call_function=None):
    print("[get_cart] Eingabe:", event)

    # Hole den Cart aus cartkvstorage
    raw_cart = await call_function("cartkvstorage", {
        "operation": "get",
        "userId": event["userId"]
    })

    # Transformiere die Einträge ins richtige Format
    cart = []
    for item in raw_cart:
        cart.append({
            "itemId": item["itemId"]["S"],
            "userId": item["userId"]["S"],
            "quantity": int(item["quantity"]["N"])
        })

    return cart


