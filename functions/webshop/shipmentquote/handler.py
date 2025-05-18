# functions/webshop/shipmentquote/handler.py

async def handler(event, context=None, call_function=None):
    print("[shipmentquote] Eingabe:", event)

    cart = event.get("items", [])
    total_qty = sum(item.get("quantity", 0) for item in cart)
    total_price = total_qty * 1.5  # USD pro Stück

    return {
        "costUsd": {
            "currencyCode": "USD",
            "units": int(total_price),
            "nanos": 0
        }
    }


