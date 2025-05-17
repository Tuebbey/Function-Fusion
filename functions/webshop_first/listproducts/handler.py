# functions/webshop/listproducts/handler.py

PRODUCTS = [
    {
        "id": "1",
        "name": "T-Shirt",
        "description": "For those who know how to code like a boss!",
        "picture": "programmer_tshirt.jpg",
        "priceUsd": {
            "currencyCode": "USD",
            "units": 24,
            "nanos": 990000000
        },
        "categories": ["clothing", "programming"]
    },
    {
        "id": "2",
        "name": "Coffee Mug",
        "description": "For those all-nighters coding sessions.",
        "picture": "coffee_mug.jpg",
        "priceUsd": {
            "currencyCode": "USD",
            "units": 14,
            "nanos": 990000000
        },
        "categories": ["kitchen", "programming"]
    },
    # 🧩 Hier kannst du den Rest der Produkte aus dem Original einfügen
]

async def list_products(event, call_function):
    print("[list_products] Event empfangen:", event)
    return {"products": PRODUCTS}
