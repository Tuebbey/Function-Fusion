# functions/webshop/email/handler.py

import asyncio
import random

async def email(event, call_function):
    print("[email] Eingabe:", event)

    # Simuliere Verzögerung durch parallele Rechenlast
    w1 = asyncio.create_task(_simulate_cpu_load())
    await w1

    # Zufälliger Erfolg (90% Chance auf Erfolg)
    return {
        "success": random.random() > 0.1
    }


async def _simulate_cpu_load(base: int = 7):
    result = 0
    limit = base ** 7
    for i in range(limit, 0, -1):
        result += (i % 100) * (i % 50)  # vereinfachte Rechenlast
    return result
