import asyncio
import math
import logging

logger = logging.getLogger("lambda-sim")

async def handler(event, context=None, call_function=None):
    """
    Handler für Funktion D - Teil der synchronen Aufrufkette
    
    Diese Funktion wird synchron von B aufgerufen und ruft wiederum synchron E auf.
    """
    logger.info(f"Event for D: {event}")
    
    # Falls Kontext übergeben wurde, setze Funktionstyp für Performance-Modellierung
    if context and isinstance(context, dict) and "function_info" not in context:
        context["function_info"] = {
            "workload_type": "cpu_intensive", 
            "region": "us-east-1"
        }
    
    checked = []
    
    # Synchroner Aufruf von E
    checked.append(await call_function("E", {"test": "event", "num": event.get("num", 7)}, "local"))
    
    # Simuliere Verzögerung
    await asyncio.sleep(0.5)
    
    # Führe eine leichte CPU-intensive Operation aus
    compute_result = cpu_intensive(4)
    
    logger.info(f"Checked are {checked}")
    
    return {
        "from": "D",
        "input": event,
        "checked": checked,
        "compute_result": compute_result
    }

def cpu_intensive(base_number):
    """CPU-intensive Berechnung"""
    result = 0
    # Leichtere Berechnung als in C
    for i in range(int(math.pow(10, 4)), -1, -1):
        result += math.atan(i) * math.tan(i)
    return result