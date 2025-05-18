# functions/webshop/emptycart/handler.py

async def empty_cart(event, call_function):
    print("[empty_cart] Eingabe:", event)

    await call_function("cartkvstorage", {
        "operation": "empty",
        "userId": event["userId"]
    })

    return True
