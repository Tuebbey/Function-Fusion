import asyncio
import math
import concurrent.futures
import logging

logger = logging.getLogger("lambda-sim")

async def handler(event, context=None, call_function=None):
    """
    Handler für Funktion G - CPU-intensive Funktion
    
    Diese Funktion wird asynchron von C aufgerufen und führt CPU-intensive Berechnungen in zwei Threads aus.
    Sie verwendet eine höhere Basis (8.8) für ihre Berechnungen als Funktion F.
    """
    logger.info(f"Event for G: {event}")
    
    # Falls Kontext übergeben wurde, setze Funktionstyp für Performance-Modellierung
    if context and isinstance(context, dict) and "function_info" not in context:
        context["function_info"] = {
            "workload_type": "cpu_intensive", 
            "region": "us-east-1"
        }
    
    # Verwende einen festen Wert 8.8 wie im Original
    fixed_base = 8.8
    
    # Erstelle zwei Threads für CPU-intensive Berechnungen
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        future1 = executor.submit(cpu_intensive, fixed_base)
        future2 = executor.submit(cpu_intensive, fixed_base)
        
        r1 = future1.result()
        r2 = future2.result()
    
    return {
        "from": "G",
        "input": event,
        "cpu_results": [r1, r2]
    }

def cpu_intensive(base_number):
    """CPU-intensive Berechnung"""
    result = 0
    # G verwendet eine andere Berechnungsmethode als F
    limit = int(min(math.pow(base_number, 5), 10000))  # Begrenze für schnellere Tests
    
    for i in range(limit, 0, -1):
        result += math.atan(i) * math.tan(i)
    
    return result