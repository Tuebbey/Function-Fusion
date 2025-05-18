# functions/webshop/searchproducts/handler.py

async def handler(event, context=None, call_function=None):
    print("[searchproducts] Eingabe:", event)

    # Hole Produktliste
    products_response = await call_function("listproducts", {}, True)
    products = products_response.get("products", [])
    query = event.get("query", "").lower()

    # Filtere Produkte basierend auf Suchbegriff im Namen oder in der Beschreibung
    filtered = [
        p for p in products
        if query in p.get("name", "").lower() or query in p.get("description", "").lower()
    ]

    return {"results": filtered}

