# functions/webshop/getproduct/handler.py

async def get_product(event, call_function):
    print("[get_product] Eingabe:", event)

    # Alle Produkte abrufen
    products_response = await call_function("listproducts", {})

    # Gesuchte ID extrahieren
    product_id = event.get("id")

    # Produkt aus der Liste filtern
    products = products_response.get("products", [])
    result = next((p for p in products if p.get("id") == product_id), None)

    return result if result else []
