import asyncio
import math
import threading
import logging
import concurrent.futures

logger = logging.getLogger("lambda-sim")

async def handler(event, context=None, call_function=None):
    """
    Handler für Funktion C - CPU-intensive Funktion mit asynchronen Aufrufen
    
    Diese Funktion wird asynchron von A aufgerufen und führt selbst asynchrone Aufrufe zu F und G durch.
    Sie führt außerdem CPU-intensive Berechnungen in zwei Threads aus.
    """
    logger.info(f"Event for C: {event}")
    
    # Falls Kontext übergeben wurde, setze Funktionstyp für Performance-Modellierung
    if context and isinstance(context, dict) and "function_info" not in context:
        context["function_info"] = {
            "workload_type": "cpu_intensive", 
            "region": "us-east-1"
        }
    
    calls = []
    
    # Starte asynchrone Aufrufe zu F und G
    calls.append(call_function("F", {"test": "event", "num": event.get("num", 7)}, "remote"))
    calls.append(call_function("G", {"test": "event", "num": event.get("num", 7)}, "remote"))
    
    num = event.get("num", 7)
    
    # Erstelle zwei Threads für CPU-intensive Berechnungen
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        future1 = executor.submit(cpu_intensive, num)
        future2 = executor.submit(cpu_intensive, num)
        
        r1 = future1.result()
        r2 = future2.result()
    
    # Warte auf Abschluss aller asynchronen Aufrufe
    results = await asyncio.gather(*calls)
    
    logger.info(f"Results are {results}")
    
    return {
        "function": "C",
        "results": results,
        "cpu_results": [r1, r2]
    }

def cpu_intensive(base_number):
    """CPU-intensive Berechnung"""
    result = 0
    # Reduzierte Komplexität für schnellere Tests, kann bei Bedarf erhöht werden
    for i in range(int(math.pow(10, 5)), -1, -1):
        result += math.atan(i) * math.tan(i)
    return result