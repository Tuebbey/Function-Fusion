# functions/webshop/checkout/handler.py

import asyncio

async def handler(event, context=None, call_function=None):
    print("[checkout] Eingabe:", event)

    user_id = event.get("userId", "0")
    currency = event.get("userCurrency", "USD")
    address = event.get("address", {})
    email_addr = event.get("email", "")

    # Warenkorb abrufen - KORRIGIERT
    cart_response = await call_function("getcart", {"userId": user_id})
    print(f"[checkout] getcart Antwort: {cart_response}")

    # Extrahiere die Items aus der Antwort mit Fallbacks für verschiedene Strukturen
    cart = []
    if isinstance(cart_response, dict):
        # Variante 1: {"body": {"items": [...]}}
        if "body" in cart_response and isinstance(cart_response["body"], dict):
            cart = cart_response["body"].get("items", [])
        # Variante 2: {"items": [...]}
        elif "items" in cart_response:
            cart = cart_response["items"]
    
    print(f"[checkout] Extrahierte Cart-Items: {cart}")
    
    # Überprüfen, ob cart eine Liste ist
    if not isinstance(cart, list):
        cart = []
        print("[checkout] WARNUNG: Cart-Inhalt ist keine Liste!")

    # Simuliere parallele CPU-lastige Aufgaben (wie Worker)
    w1 = asyncio.create_task(_simulate_cpu_load())
    w2 = asyncio.create_task(_simulate_cpu_load())

    # Produktdaten und Währungsumrechnung
    products_list = await call_function("listproducts", {})
    # Debug-Ausgabe für products_list
    print(f"[checkout] products_list Antwort: {products_list}")
    
    # Produktliste sicher extrahieren
    products = []
    if isinstance(products_list, dict):
        products = products_list.get("products", [])
        if "body" in products_list and isinstance(products_list["body"], dict):
            products = products_list["body"].get("products", products)
    
    # Sicherer product_lookup erstellen
    product_lookup = {}
    for p in products:
        if isinstance(p, dict) and "id" in p:
            product_lookup[p["id"]] = p

    order_products = []
    for item in cart:
        # Sicherstellen, dass item ein Dict ist und productId enthält
        if not isinstance(item, dict) or "productId" not in item:
            print(f"[checkout] Ungültiges Cart-Item übersprungen: {item}")
            continue
            
        prod = product_lookup.get(item["productId"])
        if not prod:
            print(f"[checkout] Produkt nicht gefunden: {item['productId']}")
            continue
            
        # Sicherstellen, dass priceUsd existiert
        if "priceUsd" not in prod:
            print(f"[checkout] Produkt hat keinen priceUsd: {prod}")
            continue
            
        new_price = await call_function("currency", {
            "from": prod["priceUsd"],
            "toCode": currency
        })
        prod["price"] = new_price
        order_products.append(prod)

    # Versandkosten - KORRIGIERT
    shipment_price = await call_function("shipmentquote", {
        "userId": user_id,
        "items": cart
    })
    
    print(f"[checkout] shipment_price Antwort: {shipment_price}")
    
    # Kostenwert sicher extrahieren
    cost_usd = 0
    if isinstance(shipment_price, dict):
        # Direkter Zugriff
        cost_usd = shipment_price.get("costUsd", 0)
        # Oder in body
        if "body" in shipment_price and isinstance(shipment_price["body"], dict):
            cost_usd = shipment_price["body"].get("costUsd", cost_usd)
    
    converted_price = await call_function("currency", {
        "from": cost_usd,
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