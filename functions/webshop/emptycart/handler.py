# functions/webshop/emptycart/handler.py

async def handler(event, context=None, call_function=None):
    print("[empty_cart] Eingabe:", event)

    await call_function("cartkvstorage", {
        "operation": "empty",
        "userId": event["userId"]
    })

    return True

