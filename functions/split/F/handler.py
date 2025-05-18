import asyncio
import math
import concurrent.futures
import logging

logger = logging.getLogger("lambda-sim")

async def handler(event, context=None, call_function=None):
    """
    Handler für Funktion F - CPU-intensive Funktion
    
    Diese Funktion wird asynchron von C aufgerufen und führt CPU-intensive Berechnungen in zwei Threads aus.
    """
    logger.info(f"Event for F: {event}")
    
    # Falls Kontext übergeben wurde, setze Funktionstyp für Performance-Modellierung
    if context and isinstance(context, dict) and "function_info" not in context:
        context["function_info"] = {
            "workload_type": "cpu_intensive", 
            "region": "us-east-1"
        }
    
    num = event.get("num", 7)
    
    # Erstelle zwei Threads für CPU-intensive Berechnungen
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        future1 = executor.submit(cpu_intensive, num)
        future2 = executor.submit(cpu_intensive, num)
        
        r1 = future1.result()
        r2 = future2.result()
    
    return {
        "from": "F",
        "cpu_results": [r1, r2]
    }

def cpu_intensive(base_number):
    """CPU-intensive Berechnung"""
    result = 0
    # Komplexe Berechnung
    for i in range(int(math.pow(10, 6)), int(math.pow(10, 6) - 10000), -1):
        result += math.atan(i % 100) * math.tan(i % 100)
    return result