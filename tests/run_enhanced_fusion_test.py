#!/usr/bin/env python3
"""
Erweitertes Testskript für Function Fusion mit Zweiphasen-Optimierung,
Kostenmodellierung und kontinuierlicher Überwachung
"""
import asyncio
import json
import logging
import os
import sys
import time
import argparse
from typing import Dict, List, Any, Optional

# Füge das Root-Verzeichnis zum Python-Pfad hinzu
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Logging-Konfiguration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("enhanced-fusion-test")

# Stellen Sie sicher, dass das Verzeichnis für die Ergebnisse existiert
os.makedirs("results", exist_ok=True)

# Importiere die notwendigen Module
from app.runtime import runtime
from app.fusion import fusion_engine
from app.optimizer.enhanced_fusion_optimizer import EnhancedFusionOptimizer
from evaluation.improved_cost_model import ImprovedCostModel
from app.optimizer.continuous_optimizer import ContinuousOptimizer
from app.performance.model import PerformanceModel
from app.network.model import NetworkModel

# Handler-Funktionen importieren
from functions.split.A.handler import handler as a_handler
from functions.split.B.handler import handler as b_handler
from functions.split.C.handler import handler as c_handler
from functions.split.D.handler import handler as d_handler
from functions.split.E.handler import handler as e_handler
from functions.split.F.handler import handler as f_handler
from functions.split.G.handler import handler as g_handler

# Eine Funktion zum Messen der Ausführungszeit
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
    runtime.register("C", c_handler, memory=256, timeout=5, region="us-east-1", function_type="cpu_intensive")
    runtime.register("D", d_handler, memory=128, timeout=3, region="us-east-1", function_type="cpu_intensive")
    runtime.register("E", e_handler, memory=128, timeout=3, region="us-east-1", function_type="cpu_intensive")
    runtime.register("F", f_handler, memory=256, timeout=5, region="us-east-1", function_type="cpu_intensive")
    runtime.register("G", g_handler, memory=256, timeout=5, region="us-east-1", function_type="cpu_intensive")
    
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
                for node_id, node in trace_data.get("nodes", {}).items():
                    # Ermittle den Aufrufer
                    caller = node.get("parent_id", "unknown")
                    
                    # Füge den Aufruf hinzu
                    calls.append({
                        "called": node_id,
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

async def perform_enhanced_optimization(test_results, cost_model):
    """Führt die verbesserte zweistufige Optimierung durch."""
    logger.info("Starte erweiterte zweistufige Optimierung...")
    
    # Erstelle den erweiterten Optimizer
    enhanced_optimizer = EnhancedFusionOptimizer(lambda_runtime=runtime, fusion_engine=fusion_engine, cost_model=cost_model)
    
    # Setze die Testergebnisse
    enhanced_optimizer.set_test_results(test_results)
    
    # Optional: Setze Gewichtungsfaktoren für Latenz und Kosten
    enhanced_optimizer.set_optimization_weights(latency_weight=0.7, cost_weight=0.3)
    
    # Führe die Optimierung durch
    logger.info("Phase 1: Starte Pfadoptimierung...")
    path_groups, memory_configs = enhanced_optimizer.optimize()
    
    # Speichere die Optimierungsergebnisse
    results_dir = os.path.join(os.path.dirname(__file__), "../results")
    results_path = os.path.join(results_dir, "enhanced_optimization_results.json")
    
    enhanced_optimizer.save_optimization_results(results_path)
    logger.info(f"Optimierungsergebnisse gespeichert in: {results_path}")
    
    # Zeige die Ergebnisse an
    optimal_config = enhanced_optimizer.get_optimal_configuration()
    logger.info(f"Optimale Konfiguration: {optimal_config}")
    logger.info(f"Optimale Funktionsgruppen: {path_groups}")
    logger.info(f"Optimale Speicherkonfigurationen: {memory_configs}")
    
    return path_groups, memory_configs, optimal_config

async def start_continuous_optimization(test_results, cost_model, run_duration=60):
    """Startet die kontinuierliche Optimierung für eine begrenzte Zeit."""
    logger.info(f"Starte kontinuierliche Optimierung für {run_duration} Sekunden...")
    
    # Erstelle den Enhanced Optimizer
    enhanced_optimizer = EnhancedFusionOptimizer(lambda_runtime=runtime, fusion_engine=fusion_engine, cost_model=cost_model)
    enhanced_optimizer.set_test_results(test_results)
    
    # Erstelle den Continuous Optimizer
    continuous_optimizer = ContinuousOptimizer(
        lambda_runtime=runtime,
        fusion_engine=fusion_engine,
        enhanced_optimizer=enhanced_optimizer,
        cost_model=cost_model
    )
    
    # Starte die kontinuierliche Überwachung (kürzeres Intervall für Demo-Zwecke)
    continuous_optimizer.start_monitoring(interval_seconds=2.0)
    
    # Generiere ein paar Workload-Änderungen für die Demo
    workload_changes = [
        {"time": 10, "type": "cpu", "intensity": 0.5},
        {"time": 25, "type": "memory", "intensity": 0.7},
        {"time": 40, "type": "mixed", "intensity": 0.9}
    ]
    
    # Ausführung für die angegebene Dauer
    start_time = time.time()
    try:
        # Hauptschleife mit Workload-Änderungen
        while time.time() - start_time < run_duration:
            current_time = time.time() - start_time
            
            # Prüfe, ob eine Workload-Änderung fällig ist
            for change in workload_changes:
                if change.get("time") <= current_time and not change.get("applied", False):
                    logger.info(f"Zeit: {current_time:.1f}s - Simuliere Workload-Änderung: {change['type']}")
                    continuous_optimizer.simulate_workload_change(
                        workload_type=change["type"],
                        intensity=change["intensity"]
                    )
                    change["applied"] = True
            
            # Warte kurz
            await asyncio.sleep(1.0)
            
            # Zeige aktuellen Status alle 5 Sekunden an
            if int(current_time) % 5 == 0:
                metrics = continuous_optimizer._get_current_metrics()
                if metrics and "latency" in metrics:
                    latency = metrics["latency"].get("average", 0)
                    logger.info(f"Zeit: {current_time:.1f}s - Aktuelle Durchschnittslatenz: {latency:.2f}ms")
        
        # Am Ende einen Bericht generieren
        logger.info("Generiere Abschlussbericht...")
        report = continuous_optimizer.generate_report(include_recommendations=True)
        
        # Speichere den Bericht
        results_dir = os.path.join(os.path.dirname(__file__), "../results")
        report_path = os.path.join(results_dir, "continuous_optimization_report.json")
        
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2)
        
        logger.info(f"Kontinuierliche Optimierung abgeschlossen. Bericht gespeichert in: {report_path}")
        
        # Zeige Empfehlungen an
        if "recommendations" in report and report["recommendations"]:
            logger.info("Empfehlungen:")
            for i, rec in enumerate(report["recommendations"]):
                priority = rec.get("priority", "medium").upper()
                message = rec.get("message", "")
                logger.info(f"  {i+1}. [{priority}] {message}")
    
    finally:
        # Stoppe die Überwachung
        continuous_optimizer.stop_monitoring()
    
    return continuous_optimizer.get_optimization_history()

async def main(args):
    """Hauptfunktion zur Ausführung der Tests mit verbesserten Funktionen."""
    logger.info("Starte erweiterte Function Fusion Tests...")
    
    # Erstelle Performance- und Netzwerkmodelle
    performance_model = PerformanceModel({
        "memory_cpu_ratio": 1769,
        "base_cpu_factor": 0.5,
        "workload_factors": {
            "cpu_intensive": 1.0,
            "memory_intensive": 0.7,
            "io_intensive": 0.3
        },
        "cold_start_enabled": False  # Cold Starts werden deaktiviert, wie gewünscht
    })
    
    network_model = NetworkModel({
        "region_latency": {
            ("us-east-1", "us-east-1"): 1,  # Intra-region
            ("us-east-1", "us-west-2"): 65,
            ("us-east-1", "eu-west-1"): 85,
        },
        "network_failure_rate": 0.001  # 0.1% Fehlerwahrscheinlichkeit für realistische Tests
    })
    
    # Erstelle das Kostenmodell
    cost_model = ImprovedCostModel(
        provider="aws_lambda",
        apply_free_tier=False
    )
    
    # Registriere Handler-Funktionen
    await register_handlers()
    
    # Erstelle Fusion-Setups
    await create_fusion_setups()
    
    # Führe die Tests durch (weniger Wiederholungen für schnellere Demonstration)
    test_results = await run_tests(
        repetitions=args.repetitions,
        performance_model=performance_model,
        network_model=network_model
    )
    
    if args.optimize:
        # Phase 1 & 2: Führe die zweistufige Optimierung durch
        path_groups, memory_configs, optimal_config = await perform_enhanced_optimization(
            test_results, cost_model
        )
    
    if args.continuous:
        # Phase 3: Starte die kontinuierliche Optimierung
        optimization_history = await start_continuous_optimization(
            test_results,
            cost_model,
            run_duration=args.duration
        )
    
    logger.info("Enhanced Function Fusion Tests abgeschlossen.")

if __name__ == "__main__":
    # Kommandozeilenargumente
    parser = argparse.ArgumentParser(description="Erweiterte Function Fusion Tests")
    parser.add_argument("--optimize", action="store_true", help="Führe die zweistufige Optimierung durch")
    parser.add_argument("--continuous", action="store_true", help="Starte die kontinuierliche Optimierung")
    parser.add_argument("--duration", type=int, default=60, help="Dauer der kontinuierlichen Optimierung in Sekunden")
    parser.add_argument("--repetitions", type=int, default=3, help="Anzahl der Wiederholungen pro Test")
    args = parser.parse_args()
    
    # Führe das asyncio event-loop aus
    asyncio.run(main(args))