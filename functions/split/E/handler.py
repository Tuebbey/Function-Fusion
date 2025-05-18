import asyncio
import math
import logging

logger = logging.getLogger("lambda-sim")

async def handler(event, context=None, call_function=None):
    """
    Handler für Funktion E - Endpunkt der synchronen Aufrufkette
    
    Diese Funktion ist der Endpunkt der synchronen Aufrufkette und führt keine weiteren Aufrufe durch.
    """
    logger.info(f"Event for E: {event}")
    
    # Falls Kontext übergeben wurde, setze Funktionstyp für Performance-Modellierung
    if context and isinstance(context, dict) and "function_info" not in context:
        context["function_info"] = {
            "workload_type": "cpu_intensive", 
            "region": "us-east-1"
        }
    
    # Simuliere Verzögerung durch Verarbeitung
    await asyncio.sleep(0.5)
    
    # Führe eine einfache CPU-Operation aus
    compute_result = cpu_intensive(3)
    
    return {
        "from": "E",
        "input": event,
        "compute_result": compute_result
    }

def cpu_intensive(base_number):
    """CPU-intensive Berechnung"""
    result = 0
    # Leichte Berechnung
    for i in range(int(math.pow(10, 3)), -1, -1):
        result += math.atan(i) * math.tan(i)
    return result