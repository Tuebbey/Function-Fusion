#!/usr/bin/env python3
"""
Erweiterte Function Fusion Tests mit Docker und dem bestehenden Framework
Nutzt das bestehende Runtime und Fusion Engine während Docker für Netzwerksimulation verwendet wird
"""

import asyncio
import json
import logging
import os
import sys
import time
import httpx
from datetime import datetime
from typing import Dict, List, Any, Optional

# Füge das Root-Verzeichnis zum Python-Pfad hinzu
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.runtime import runtime
from app.fusion import fusion_engine
from app.optimizer.enhanced_fusion_optimizer import EnhancedFusionOptimizer
from evaluation.improved_cost_model import ImprovedCostModel
from app.fusion_enhanced import enhanced_fusion_engine

# Handler-Funktionen direkt importieren (da Docker die Netzwerkeffekte simuliert)
from functions.webshop.addcartitem.handler import handler as add_cart_handler
from functions.webshop.cartkvstorage.handler import handler as storage_handler
from functions.webshop.shipmentquote.handler import handler as shipping_handler
from functions.webshop.checkout.handler import handler as checkout_handler
from functions.webshop.payment.handler import handler as payment_handler

# Logging konfigurieren
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fusion-test-framework")

class FrameworkFusionTester:
    """
    Nutzt das bestehende Framework für Function Fusion Tests
    mit Docker für realistische Netzwerksimulation
    """
    
    def __init__(self):
        self.cost_model = ImprovedCostModel(provider="aws_lambda")
        self.optimizer = EnhancedFusionOptimizer(
            lambda_runtime=runtime,
            fusion_engine=enhanced_fusion_engine,
            cost_model=self.cost_model
        )
        
        # Basis-URL für Docker Services
        self.docker_services = {
            "add_cart_item": "http://localhost:8002",
            "cartkvstorage": "http://localhost:8003", 
            "shipmentquote": "http://localhost:8010",
            "checkout": "http://localhost:8012",
            "payment": "http://localhost:8013"
        }
        
        self.client = None
        self.test_results = {}
    
    async def setup(self):
        """Setup der Test-Umgebung"""
        self.client = httpx.AsyncClient(timeout=30.0)
        
        # Registriere Functions für das Framework
        # Mit Docker-basierten Call-Functions für realistische Netzwerksimulation
        logger.info("Registriere Functions im Framework...")
        
        # Wrapper für Docker-basierte Function Calls
        async def docker_call_function(service_name: str, event: dict, sync: bool = True):
            if service_name in self.docker_services:
                url = f"{self.docker_services[service_name]}/invoke"
                payload = {"name": service_name, "event": event}
                
                try:
                    response = await self.client.post(url, json=payload)
                    response.raise_for_status()
                    result = response.json()
                    return result.get("body", result)
                except Exception as e:
                    logger.error(f"Docker-Aufruf für {service_name} fehlgeschlagen: {e}")
                    return {"error": str(e)}
            else:
                # Fallback zu lokalen Handlers
                return event
        
        # Registriere Functions mit Hybrid-Ansatz (lokale Handler + Docker Calls)
        runtime.register("add_cart_item", add_cart_handler, memory=128, timeout=3)
        runtime.register("cartkvstorage", storage_handler, memory=128, timeout=3)
        runtime.register("shipmentquote", shipping_handler, memory=128, timeout=3)
        runtime.register("checkout", checkout_handler, memory=256, timeout=5)
        runtime.register("payment", payment_handler, memory=256, timeout=5)
        
        # Konfiguriere Enhanced Fusion Engine mit Docker-Call-Function
        enhanced_fusion_engine.docker_call_function = docker_call_function
    
    async def cleanup(self):
        """Cleanup"""
        if self.client:
            await self.client.aclose()
    
    async def create_fusion_configurations(self):
        """Erstelle verschiedene Fusion-Konfigurationen zum Testen"""
        logger.info("Erstelle Fusion-Konfigurationen...")
        
        # Konfiguration 1: Alle Functions einzeln (Remote Calls)
        enhanced_fusion_engine.register_fusion(
            "all_remote",
            ["add_cart_item", "cartkvstorage", "shipmentquote", "payment"]
        )
        
        # Konfiguration 2: Cart-Operationen zusammen
        enhanced_fusion_engine.register_fusion(
            "cart_fusion", 
            ["add_cart_item", "cartkvstorage"]
        )
        
        # Konfiguration 3: Checkout-Workflow komplett zusammen
        enhanced_fusion_engine.register_fusion(
            "checkout_fusion",
            ["add_cart_item", "cartkvstorage", "shipmentquote", "checkout", "payment"]
        )
        
        # Konfiguration 4: Synchrone Calls zusammen, async separat
        enhanced_fusion_engine.register_fusion(
            "sync_async_optimized",
            ["add_cart_item", "cartkvstorage", "shipmentquote"]
        )
        enhanced_fusion_engine.register_fusion(
            "async_group",
            ["payment"]
        )
    
    async def run_test_scenario(self, fusion_name: str, test_event: dict, repetitions: int = 3) -> dict:
        """Führt ein Testszenario aus"""
        logger.info(f"Teste Fusion: {fusion_name}")
        
        results = []
        
        for i in range(repetitions):
            start_time = time.time()
            
            try:
                # Verwende Enhanced Fusion Engine
                result = await enhanced_fusion_engine.execute(
                    fusion_name,
                    test_event,
                    runtime,
                    execution_mode="sync"
                )
                
                end_time = time.time()
                duration_ms = (end_time - start_time) * 1000
                
                execution_result = {
                    "iteration": i + 1,
                    "duration_ms": duration_ms,
                    "status": result.get("status", "unknown"),
                    "trace_id": result.get("trace_id"),
                    "result": result
                }
                
                results.append(execution_result)
                logger.info(f"  Durchlauf {i+1}: {duration_ms:.2f}ms")
                
            except Exception as e:
                logger.error(f"Fehler bei Durchlauf {i+1}: {e}")
                results.append({
                    "iteration": i + 1,
                    "error": str(e),
                    "duration_ms": 0
                })
        
        # Berechne Statistiken
        successful_results = [r for r in results if "error" not in r]
        
        if successful_results:
            durations = [r["duration_ms"] for r in successful_results]
            stats = {
                "avg_duration_ms": sum(durations) / len(durations),
                "min_duration_ms": min(durations),
                "max_duration_ms": max(durations),
                "success_rate": len(successful_results) / len(results),
                "total_iterations": len(results)
            }
        else:
            stats = {
                "avg_duration_ms": 0,
                "min_duration_ms": 0,
                "max_duration_ms": 0,
                "success_rate": 0,
                "total_iterations": len(results)
            }
        
        return {
            "fusion_name": fusion_name,
            "statistics": stats,
            "detailed_results": results
        }
    
    async def run_comprehensive_tests(self) -> dict:
        """Führt umfassende Tests mit verschiedenen Fusionen durch"""
        logger.info("=== Starte umfassende Function Fusion Tests ===")
        
        # Test-Event
        test_event = {
            "userId": "test-user-123",
            "productId": "product-456",
            "quantity": 2,
            "userCurrency": "USD",
            "address": {"country": "Germany", "city": "Berlin"},
            "email": "test@example.com"
        }
        
        # Teste verschiedene Fusionen
        fusion_tests = [
            "all_remote",
            "cart_fusion",
            "checkout_fusion", 
            "sync_async_optimized"
        ]
        
        all_results = {}
        
        for fusion_name in fusion_tests:
            try:
                result = await self.run_test_scenario(fusion_name, test_event, repetitions=5)
                all_results[fusion_name] = result
                
                # Für Optimizer verwenden
                self.test_results[fusion_name] = [{
                    "billedDuration": result["statistics"]["avg_duration_ms"],
                    "maxMemoryUsed": 128,
                    "status": "success"
                }]
                
            except Exception as e:
                logger.error(f"Fehler bei Fusion {fusion_name}: {e}")
                all_results[fusion_name] = {"error": str(e)}
        
        return all_results
    
    async def run_optimization_analysis(self) -> dict:
        """Führt Optimierungsanalyse durch"""
        logger.info("=== Starte Optimierungsanalyse ===")
        
        # Setze Testergebnisse im Optimizer
        self.optimizer.set_test_results(self.test_results)
        
        # Optimiere
        path_groups, memory_configs = self.optimizer.optimize()
        
        # Finde optimale Konfiguration
        optimal_config = self.optimizer.get_optimal_configuration()
        
        # Weitere Analysen
        fastest_config = self.optimizer.get_lowest_latency_configuration()
        
        analysis_results = {
            "optimized_path_groups": path_groups,
            "optimized_memory_configs": memory_configs, 
            "optimal_configuration": optimal_config,
            "fastest_configuration": fastest_config,
            "test_results_summary": {}
        }
        
        # Erstelle Zusammenfassung der Testergebnisse
        for fusion_name, results in self.test_results.items():
            if results and len(results) > 0:
                avg_duration = sum(r["billedDuration"] for r in results) / len(results)
                analysis_results["test_results_summary"][fusion_name] = {
                    "average_duration_ms": avg_duration,
                    "test_count": len(results)
                }
        
        logger.info(f"Optimale Konfiguration: {optimal_config}")
        logger.info(f"Schnellste Konfiguration: {fastest_config}")
        
        return analysis_results
    
    async def run_cost_analysis(self) -> dict:
        """Führt Kostenanalyse durch"""
        logger.info("=== Starte Kostenanalyse ===")
        
        cost_analysis = {}
        
        for fusion_name, results in self.test_results.items():
            if not results:
                continue
                
            # Erstelle Fusion-Setup für Kostenmodell
            fusion_setup = {
                "groups": [[fusion_name]],  # Vereinfachung
                "memory_configurations": {fusion_name: 128}
            }
            
            # Konvertiere Testergebnisse für Kostenmodell
            execution_data = []
            for result in results:
                execution_data.append({
                    "function": fusion_name,
                    "duration_ms": result["billedDuration"],
                    "memory_mb": result.get("maxMemoryUsed", 128),
                    "caller": None,
                    "is_sync": True
                })
            
            # Berechne Kosten
            try:
                cost_result = self.cost_model.calculate_fusion_cost(
                    fusion_setup, 
                    execution_data
                )
                cost_analysis[fusion_name] = cost_result
            except Exception as e:
                logger.error(f"Kostenfehler für {fusion_name}: {e}")
                cost_analysis[fusion_name] = {"error": str(e)}
        
        return cost_analysis
    
    async def save_results(self, comprehensive_results: dict, optimization_results: dict, cost_results: dict):
        """Speichere alle Ergebnisse"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        combined_results = {
            "timestamp": timestamp,
            "test_type": "framework_fusion_test_with_docker",
            "comprehensive_tests": comprehensive_results,
            "optimization_analysis": optimization_results,
            "cost_analysis": cost_results
        }
        
        os.makedirs("results", exist_ok=True)
        results_file = f"results/framework_fusion_test_{timestamp}.json"
        
        with open(results_file, "w") as f:
            json.dump(combined_results, f, indent=2)
        
        logger.info(f"Ergebnisse gespeichert in: {results_file}")
        return results_file
    
    def print_summary(self, results: dict):
        """Drucke Zusammenfassung"""
        logger.info("\n" + "="*60)
        logger.info("FUNCTION FUSION TEST ZUSAMMENFASSUNG")
        logger.info("="*60)
        
        # Leistungsvergleich
        if "comprehensive_tests" in results:
            logger.info("\nLeistungsvergleich:")
            logger.info("-" * 30)
            
            for fusion_name, data in results["comprehensive_tests"].items():
                if "statistics" in data:
                    stats = data["statistics"]
                    logger.info(f"{fusion_name:20} | {stats['avg_duration_ms']:8.2f}ms | " +
                              f"Success: {stats['success_rate']*100:5.1f}%")
        
        # Optimierung
        if "optimization_analysis" in results:
            opt = results["optimization_analysis"]
            logger.info(f"\nOptimales Setup: {opt.get('optimal_configuration', 'N/A')}")
            logger.info(f"Schnellstes Setup: {opt.get('fastest_configuration', 'N/A')}")
        
        # Kosten (falls vorhanden)
        if "cost_analysis" in results:
            logger.info("\nKostenanalyse:")
            logger.info("-" * 30)
            for fusion_name, cost_data in results["cost_analysis"].items():
                if "total_cost" in cost_data:
                    logger.info(f"{fusion_name:20} | ${cost_data['total_cost']:.6f}")
        
        logger.info("="*60)

async def main():
    """Hauptfunktion"""
    tester = FrameworkFusionTester()
    
    try:
        # Setup
        await tester.setup()
        
        # Erstelle Fusion-Konfigurationen
        await tester.create_fusion_configurations()
        
        # Führe umfassende Tests durch
        comprehensive_results = await tester.run_comprehensive_tests()
        
        # Optimierungsanalyse
        optimization_results = await tester.run_optimization_analysis()
        
        # Kostenanalyse
        cost_results = await tester.run_cost_analysis()
        
        # Speichere Ergebnisse
        results_file = await tester.save_results(
            comprehensive_results,
            optimization_results, 
            cost_results
        )
        
        # Drucke Zusammenfassung
        all_results = {
            "comprehensive_tests": comprehensive_results,
            "optimization_analysis": optimization_results,
            "cost_analysis": cost_results
        }
        tester.print_summary(all_results)
        
        return results_file
        
    except Exception as e:
        logger.error(f"Testfehler: {e}")
        raise
    finally:
        await tester.cleanup()

if __name__ == "__main__":
    results_file = asyncio.run(main())
    print(f"\n✅ Tests abgeschlossen! Ergebnisse in: {results_file}")