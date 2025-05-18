import asyncio
import math
import logging

logger = logging.getLogger("lambda-sim")

async def handler(event, context=None, call_function=None):
    """
    Handler für Funktion B - Führt einen synchronen Aufruf zu D durch
    
    Diese Funktion ist Teil der synchronen Aufrufkette und wird von A aufgerufen.
    Sie ruft wiederum synchron D auf.
    """
    logger.info(f"Event for B: {event}")
    
    # Falls Kontext übergeben wurde, setze Funktionstyp für Performance-Modellierung
    if context and isinstance(context, dict) and "function_info" not in context:
        context["function_info"] = {
            "workload_type": "cpu_intensive", 
            "region": "us-east-1"
        }
    
    checked = []
    
    # Synchroner Aufruf von D
    checked.append(await call_function("D", {"test": "event", "num": event.get("num", 7)}, "local"))
    
    # Simuliere Verzögerung durch Verarbeitung
    await asyncio.sleep(0.5)
    
    # Simuliere etwas CPU-Arbeit
    compute_result = eratosthenes(5000)
    
    logger.info(f"B: Checked are {checked}")
    
    return {
        "from": "B",
        "input": event,
        "checked": checked,
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