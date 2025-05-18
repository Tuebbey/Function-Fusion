#!/usr/bin/env python3
"""
Haupt-Skript zum Ausführen eines Function Fusion Tests
Mit erweiterter Performance- und Netzwerksimulation
"""
import asyncio
import json
import logging
import os
import sys
from typing import Dict, List, Any, Optional
import time

# Füge das Root-Verzeichnis zum Python-Pfad hinzu,
# damit wir Module aus dem Hauptverzeichnis importieren können
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Logging-Konfiguration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("fusion-test")

# Stellen Sie sicher, dass das Verzeichnis für die Ergebnisse existiert
os.makedirs("results", exist_ok=True)

# Importiere die notwendigen Module aus deiner bestehenden Struktur
from app.runtime import runtime
from app.fusion import fusion_engine, FusionConfiguration
from app.optimizer.function_fusion_optimizer import iterate_on_lowest_latency, get_configuration_with_lowest_latency
from app.performance.model import PerformanceModel
from app.network.model import NetworkModel

# Handler-Funktionen importieren - angepasst an deine Ordnerstruktur
from functions.split.A.handler import handler as a_handler
from functions.split.B.handler import handler as b_handler
from functions.split.C.handler import handler as c_handler
from functions.split.D.handler import handler as d_handler
from functions.split.E.handler import handler as e_handler
from functions.split.F.handler import handler as f_handler
from functions.split.G.handler import handler as g_handler

# Eine einfache Funktion, um die Duration einer Ausführung zu messen
async def measure_execution_time(func, *args, **kwargs):
    """Misst die Ausführungszeit einer Funktion in Millisekunden."""
    start_time = time.time()
    result = await func(*args, **kwargs)
    end_time = time.time()
    duration_ms = (end_time - start_time) * 1000
    return result, duration_ms

async def register_handlers():
    """Registriert alle Handler-Funktionen in der Runtime."""
    logger.info("Registriere Handler-Funktionen...")
    
    # Verbesserte Registrierung mit Funktionstypen und Regionen
    runtime.register("A", a_handler, memory=128, timeout=3, region="us-east-1", function_type="cpu_intensive")
    runtime.register("B", b_handler, memory=128, timeout=3, region="us-east-1", function_type="cpu_intensive")
    runtime.register("C", c_handler, memory=256, timeout=5, region="us-east-1", function_type="cpu_intensive") # Mehr Ressourcen für CPU-intensive Funktion
    runtime.register("D", d_handler, memory=128, timeout=3, region="us-east-1", function_type="cpu_intensive")
    runtime.register("E", e_handler, memory=128, timeout=3, region="us-east-1", function_type="cpu_intensive")
    runtime.register("F", f_handler, memory=256, timeout=5, region="us-east-1", function_type="cpu_intensive") # Mehr Ressourcen für CPU-intensive Funktion
    runtime.register("G", g_handler, memory=256, timeout=5, region="us-east-1", function_type="cpu_intensive") # Mehr Ressourcen für CPU-intensive Funktion
    
    logger.info("Alle Handler erfolgreich registriert.")

async def create_fusion_setups():
    """Erstellt verschiedene Fusion-Setups für die Tests."""
    logger.info("Erstelle Fusion-Setups...")
    
    # Liste aller möglichen Fusion-Setups, die wir testen wollen
    setups = [
        "A,B,C,D,E,F,G",  # Jede Funktion in einer eigenen Gruppe
        "A.B.C.D.E.F.G",  # Alle Funktionen in einer Gruppe
        "A.B.D.E,C,F,G",  # Synchrone Funktionen (A,B,D,E) zusammen, asynchrone getrennt
        "A.B,C,D,E,F,G",  # Nur A und B zusammen
        "A.B.D,C,E,F,G",  # A, B und D zusammen
        "A.B.D.E.F.G,C",  # Alle außer C zusammen
        "A.B.D.E.G,C,F",  # A,B,D,E,G zusammen, C und F separat
        "A,B.D.E,C,F,G",  # B,D,E zusammen, Rest separat
        "A,B,C,D.E,F,G"   # D und E zusammen, Rest separat
    ]

    # Erstelle für jedes Setup eine Fusion-Konfiguration
    for setup in setups:
        fusion_groups = setup.split(",")
        for group in fusion_groups:
            functions = group.split(".")
            
            # Erstelle eine spezifische Konfiguration für diese Gruppe
            config = {
                "memory_size": 128,  # Standard-Speichergröße
                "timeout": 5,        # Standard-Timeout
                "rules": {}          # Wird später spezifiziert
            }
            
            # Registriere die Fusion mit dieser Konfiguration
            fusion_id = f"fusion_{group.replace('.', '_')}"
            fusion_engine.register_fusion(fusion_id, functions, config)
            logger.info(f"Fusion {fusion_id} mit Funktionen {functions} registriert.")
    
    logger.info("Alle Fusion-Setups erstellt.")

async def run_tests(repetitions=3, performance_model=None, network_model=None):
    """Führt Tests für jedes Fusion-Setup durch."""
    logger.info(f"Starte Tests mit {repetitions} Wiederholungen pro Setup...")
    
    # Standard-Event für alle Tests
    test_event = {"test": "event", "num": 7}
    
    # Speichert die Ergebnisse
    fusion_results = {}
    
    # Bestimme alle registrierten Fusion-IDs
    fusion_ids = list(fusion_engine.fusions.keys())
    logger.info(f"Gefundene Fusion-IDs: {fusion_ids}")
    
    # Führe Tests für jede Fusion-ID durch
    for fusion_id in fusion_ids:
        logger.info(f"Teste {fusion_id}...")
        
        # Setup-Identifier extrahieren
        setup_key = fusion_id.replace("fusion_", "").replace("_", ".")
        
        # Initialisiere die Ergebnisliste für dieses Setup
        if setup_key not in fusion_results:
            fusion_results[setup_key] = []
        
        # Führe mehrere Tests durch
        for i in range(repetitions):
            logger.info(f" Durchlauf {i+1}/{repetitions}")
            
            try:
                # Führe die Fusion aus und messe die Zeit
                result, duration_ms = await measure_execution_time(
                    fusion_engine.execute,
                    fusion_id,
                    test_event,
                    runtime,
                    performance_model=performance_model,
                    network_model=network_model
                )
                
                # Extrahiere die relevanten Daten
                trace_id = result.get("trace_id", "unknown")
                trace_data = fusion_engine.get_trace(trace_id) if trace_id != "unknown" else {}
                
                # Sammle Daten über die Aufrufe
                calls = []
                for func_id, node in trace_data.get("nodes", {}).items():
                    # Ermittle den Aufrufer
                    caller = node.get("parent_id", "unknown")
                    
                    # Füge den Aufruf hinzu
                    calls.append({
                        "called": func_id,
                        "caller": caller,
                        "local": node.get("strategy", "local") == "local",
                        "sync": node.get("mode", "sync") == "sync",
                        "time": node.get("duration", 0) * 1000  # in ms
                    })
                
                # Füge das Ergebnis hinzu
                fusion_results[setup_key].append({
                    "traceId": trace_id,
                    "fusionGroup": setup_key,
                    "source": "A",  # Annahme: A ist immer der Startpunkt
                    "currentFunction": "A",
                    "billedDuration": duration_ms,
                    "maxMemoryUsed": 128,  # Simulierte Speichernutzung
                    "isRootInvocation": True,
                    "startTimestamp": trace_data.get("start_time", 0) * 1000,
                    "endTimestamp": trace_data.get("end_time", 0) * 1000,
                    "internalDuration": duration_ms,
                    "calls": calls
                })
                
                logger.info(f" Ausführungszeit: {duration_ms:.2f}ms")
                
            except Exception as e:
                logger.error(f" Fehler bei der Ausführung von {fusion_id}: {str(e)}")
                
                # Füge einen Fehlereintrag hinzu
                fusion_results[setup_key].append({
                    "traceId": "error",
                    "fusionGroup": setup_key,
                    "source": "A",
                    "currentFunction": "A",
                    "billedDuration": 10000,  # Hoher Wert für Fehler
                    "error": str(e),
                    "calls": []
                })
    
    # Erstelle das results Verzeichnis im gleichen Verzeichnis wie das Skript
    results_dir = os.path.join(os.path.dirname(__file__), "../results")
    os.makedirs(results_dir, exist_ok=True)
    
    # Speichere die Ergebnisse mit absolutem Pfad
    results_path = os.path.join(results_dir, "fusion_test_results.json")
    with open(results_path, "w") as f:
        json.dump(fusion_results, f, indent=2)
    
    logger.info(f"Alle Tests abgeschlossen. Ergebnisse in {results_path} gespeichert.")
    return fusion_results

async def optimize_fusion_setup(test_results):
    """Optimiert das Fusion-Setup basierend auf den Testergebnissen."""
    logger.info("Starte Optimierung des Fusion-Setups...")
    
    # Findet das Setup mit der niedrigsten Latenz
    lowest_latency_setup = get_configuration_with_lowest_latency(test_results)
    logger.info(f"Setup mit niedrigster Latenz: {lowest_latency_setup}")
    
    # Iterative Verbesserung
    improved_setup = iterate_on_lowest_latency(test_results)
    if improved_setup:
        logger.info(f"Optimiertes Setup gefunden: {improved_setup}")
    else:
        logger.info("Keine weitere Optimierung möglich.")
    
    # Erstelle das results Verzeichnis im gleichen Verzeichnis wie das Skript
    results_dir = os.path.join(os.path.dirname(__file__), "../results")
    os.makedirs(results_dir, exist_ok=True)
    
    # Schreibe die Optimierungsergebnisse mit absolutem Pfad
    results_path = os.path.join(results_dir, "optimization_results.json")
    with open(results_path, "w") as f:
        json.dump({
            "lowest_latency_setup": lowest_latency_setup,
            "improved_setup": improved_setup
        }, f, indent=2)
    
    logger.info(f"Optimierungsergebnisse in {results_path} gespeichert.")
    return improved_setup

async def main():
    """Hauptfunktion, die alle Testschritte ausführt."""
    logger.info("Starte Function Fusion Test...")
    
    # Erstelle angepasste Performance- und Netzwerkmodelle
    performance_model = PerformanceModel({
        # Angepasste Konfiguration für die Tests
        "memory_cpu_ratio": 1769,
        "base_cpu_factor": 0.5,
        "workload_factors": {
            "cpu": 1.0,
            "memory": 0.7,
            "io": 0.3
        },
        # Cold-Start aktivieren für realistischere Simulation
        "cold_start_enabled": True,
        "cold_start_base": 0.3  # Basis-Cold-Start-Zeit (s)
    })
    
    network_model = NetworkModel({
        # Angepasste Konfiguration für die Tests
        "region_latency": {
            ("us-east-1", "us-east-1"): 1,  # Intra-region
            ("us-east-1", "us-west-2"): 65,
            ("us-east-1", "eu-west-1"): 85,
        },
        "network_failure_rate": 0.005  # 0.5% Fehlerwahrscheinlichkeit für realistische Tests
    })
    
    # Registriere Handler
    await register_handlers()
    
    # Erstelle Fusion-Setups
    await create_fusion_setups()
    
    # Führe Tests durch mit den angepassten Modellen
    test_results = await run_tests(
        repetitions=3, 
        performance_model=performance_model,
        network_model=network_model
    )
    
    # Optimiere das Setup
    optimal_setup = await optimize_fusion_setup(test_results)
    
    logger.info("Function Fusion Test abgeschlossen.")
    return optimal_setup

if __name__ == "__main__":
    # Führe das asyncio event-loop aus
    optimal_setup = asyncio.run(main())
    print(f"\nOptimales Fusion-Setup: {optimal_setup}")