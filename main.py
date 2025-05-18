# main.py

import asyncio
from fastapi import FastAPI
from app.runtime import runtime
from app.fusion import fusion_engine
from functions.example_functions import add_one, square
from app.api import router

# FastAPI-App initialisieren
app = FastAPI(title="Lambda Simulator")

# Registriere Beispiel-Funktionen
runtime.register("add_one", add_one)
runtime.register("square", square)

# Registriere API-Routen
app.include_router(router)

# Async-Testfunktion zum Start
async def run_startup_tests():
    print("[Startup-Test] Starte Testfunktionen...")
    
    # Beispiel-Funktion ausführen
    test_output = await runtime.invoke("add_one", {"value": 3})
    print(f"Testausgabe add_one(3): {test_output}")

    # Beispiel-Fusion registrieren und ausführen
    fusion_engine.register_fusion("demo_fusion", ["add_one", "square"])
    fusion_result = await fusion_engine.execute("demo_fusion", {"value": 2}, runtime)
    print(f"Fusionsergebnis demo_fusion(2): {fusion_result}")

# Führt Startup-Testfunktion beim Serverstart aus
@app.on_event("startup")
async def startup_event():
    await run_startup_tests()
