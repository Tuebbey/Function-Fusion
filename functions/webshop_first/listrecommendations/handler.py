# functions/webshop/listrecommendations/handler.py

import random

async def list_recommendations(event, call_function):
    print("[list_recommendations] Eingabe:", event)

    # Alle Produkte laden
    products_response = await call_function("listproducts", {})
    all_products = products_response.get("products", [])

    # IDs der Produkte, die der Nutzer hat
    input_ids = event.get("productIds", [])

    # Produkte des Nutzers + ihre Kategorien sammeln
    user_products = [p for p in all_products if p.get("id") in input_ids]
    user_categories = {cat for p in user_products for cat in p.get("categories", [])}

    # Empfehlungen: Produkte, die in derselben Kategorie sind, aber nicht im Warenkorb
    recommendations = [
        p for p in all_products
        if p.get("id") not in input_ids and user_categories.intersection(p.get("categories", []))
    ]

    # Zufällig mischen und zwei zurückgeben
    random.shuffle(recommendations)
    return recommendations[:2]
