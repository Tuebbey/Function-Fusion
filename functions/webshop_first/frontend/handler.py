# functions/webshop/frontend/handler.py

async def frontend(event, call_function):
    print("[frontend] Eingabe:", event)

    operation = event.get("operation", "get")
    user_id = event.get("userId", "0")
    currency = event.get("currency", "USD")

    if operation == "get":
        supported = await call_function("supportedcurrencies", {})
        products_list = await call_function("listproducts", {})

        products_currency = []
        for pr in products_list.get("products", []):
            new_price = await call_function("currency", {
                "from": pr["priceUsd"],
                "toCode": currency
            })
            pr["price"] = new_price
            products_currency.append(pr)

        ads = await call_function("getads", {})
        cart = await call_function("getcart", {"userId": user_id})
        recommendations = await call_function("listrecommendations", {
            "productIds": [p["productId"] for p in cart],
            "userId": user_id
        })

        return {
            "ads": ads,
            "supportedCurrencies": supported,
            "recommendations": recommendations,
            "cart": cart,
            "productsList": products_currency
        }

    elif operation == "cart":
        cart = await call_function("getcart", {"userId": user_id})
        shipping = await call_function("shipmentquote", {
            "userId": user_id,
            "items": cart
        })
        return {
            "cart": cart,
            "shippingCost": shipping
        }

    elif operation == "checkout":
        return await call_function("checkout", {
            "userId": user_id,
            "creditCard": {
                "creditCardNumber": event.get("creditCardNumber", "000000")
            }
        })

    elif operation == "addcart":
        item = await call_function("addcartitem", {
            "userId": user_id,
            "productId": event.get("productId", "0"),
            "quantity": event.get("quantity", 1)
        })
        cart = await call_function("getcart", {"userId": user_id})
        return {
            "newItem": item,
            "cart": cart
        }

    elif operation == "emptycart":
        await call_function("emptycart", {"userId": user_id})
        return {"userId": user_id}

    else:
        return {"error": "The operation specified does not exist."}
