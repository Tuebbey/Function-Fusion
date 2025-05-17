# functions/webshop/checkout/handler.py

import asyncio

async def checkout(event, call_function):
    print("[checkout] Eingabe:", event)

    user_id = event.get("userId", "0")
    currency = event.get("userCurrency", "USD")
    address = event.get("address", {})
    email_addr = event.get("email", "")

    # Warenkorb abrufen
    cart = await call_function("getcart", {"userId": user_id})

    # Simuliere parallele CPU-lastige Aufgaben (wie Worker)
    w1 = asyncio.create_task(_simulate_cpu_load())
    w2 = asyncio.create_task(_simulate_cpu_load())

    # Produktdaten und Währungsumrechnung
    products_list = await call_function("listproducts", {})
    product_lookup = {p["id"]: p for p in products_list.get("products", [])}

    order_products = []
    for item in cart:
        prod = product_lookup.get(item["productId"])
        if not prod:
            continue
        new_price = await call_function("currency", {
            "from": prod["priceUsd"],
            "toCode": currency
        })
        prod["price"] = new_price
        order_products.append(prod)

    # Versandkosten
    shipment_price = await call_function("shipmentquote", {
        "userId": user_id,
        "items": cart
    })
    converted_price = await call_function("currency", {
        "from": shipment_price.get("costUsd"),
        "toCode": currency
    })

    # Versand auslösen
    await call_function("shiporder", {
        "address": address,
        "items": order_products
    })

    # E-Mail und Warenkorb leeren
    await call_function("email", {"message": "You are shipped", "to": email_addr})
    await call_function("emptycart", {"userId": user_id})

    # Warte auf parallele Tasks
    result1 = await w1
    result2 = await w2

    print("[checkout] abgeschlossen.")
    return [order_products, converted_price]


async def _simulate_cpu_load(base: int = 7):
    result = 0
    limit = base ** 7
    for i in range(limit, 0, -1):
        result += (i % 100) * (i % 50)  # vereinfachte Rechenlast
    return result
