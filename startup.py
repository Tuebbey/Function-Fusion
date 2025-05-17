# startup.py

import asyncio
from app.runtime import runtime
from app.fusion import fusion_engine
from functions.demo.demo import add_one, square

# Demo-Funktionen registrieren
runtime.register("add_one", add_one)
runtime.register("square", square)

# Beispiel-Fusion registrieren
fusion_engine.register_fusion("demo_fusion", ["add_one", "square"])

# Beispiel: Webshop-Funktionen (wenn implementiert)
from functions.webshop_first.addcartitem.addcartitem import add_cart_item
from functions.webshop_first.cartkvstorage.cartkvstorage import cartkvstorage

runtime.register("add_cart_item", add_cart_item)
runtime.register("cartkvstorage", cartkvstorage)

fusion_engine.register_fusion("fusion_add_and_store", ["add_cart_item", "cartkvstorage"])

# Async-Test-Wrapper
async def test_fusion():
    event = {"value": 2}
    result = await fusion_engine.execute("demo_fusion", event, runtime)
    print("Fusionsergebnis demo_fusion(2):", result)

# Starte async Funktion
if __name__ == "__main__":
    import asyncio
    asyncio.run(test_fusion())
