import asyncio
import math
import logging

logger = logging.getLogger("lambda-sim")

async def handler(event, context=None, call_function=None):
    """
    Handler für Funktion A - Startet sowohl synchrone als auch asynchrone Aufrufe
    
    Diese Funktion enthält:
    - Einen synchronen Aufruf von B (wartet auf das Ergebnis)
    - Einen asynchronen Aufruf von C (wartet nicht auf das Ergebnis)
    """
    logger.info(f"Event for A: {event}")
    
    # Falls Kontext übergeben wurde, setze Funktionstyp für Performance-Modellierung
    if context and isinstance(context, dict) and "function_info" not in context:
        context["function_info"] = {
            "workload_type": "cpu_intensive", 
            "region": "us-east-1"
        }
    
    # Starte asynchronen Aufruf von C
    c_call = call_function("C", {"test": "event", "num": event.get("num", 7)}, "remote")
    
    # Führe synchronen Aufruf von B aus und warte auf Ergebnis
    b_result = await call_function("B", {"test": "event", "num": event.get("num", 7)}, "local")
    
    # Warte auf Abschluss des asynchronen Aufrufs
    c_result = await c_call
    
    # Ergebnisse protokollieren
    logger.info(f"Results are {c_result}")
    logger.info(f"Checked are {b_result}")
    
    # Simuliere etwas CPU-Arbeit
    compute_result = eratosthenes(10000)
    
    return {
        "from": "A",
        "traceId": event.get("traceId"),
        "results": c_result,
        "checked": b_result,
        "compute_size": len(compute_result) if compute_result else 0
    }

def eratosthenes(limit):
    """Berechnet alle Primzahlen bis zum angegebenen Limit"""
    primes = []
    if limit >= 2:
        # Initialisiere Array mit allen Zahlen von 2 bis limit
        nums = list(range(2, limit + 1))
        
        sqrtlmt = int(math.sqrt(limit)) - 2
        for i in range(sqrtlmt + 1):
            p = nums[i]
            if p:
                # Markiere alle Vielfachen von p als 0
                for j in range(p * p - 2, len(nums), p):
                    nums[j] = 0
                    
        # Sammle alle Nicht-Null-Elemente als Primzahlen
        primes = [p for p in nums if p]
    
    return primes