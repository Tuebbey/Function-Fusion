#!/usr/bin/env python3
"""
Function Fusion Test für Docker-Setup
Dieser Test demonstriert und misst Function Fusion mit dem Webshop-Beispiel
"""

import asyncio
import json
import logging
import os
import sys
import time
import random
import httpx
from datetime import datetime
from typing import Dict, List, Any, Optional

# Logging konfigurieren
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("fusion-test-docker")

class DockerFusionTester:
    """
    Testet Function Fusion Setups mit Docker-Containern
    """
    
    def __init__(self):
        self.base_url = "http://localhost"
        self.results = {}
        self.client = None
        
        # Function Service Mappings (Port zu Service)
        self.service_ports = {
            "frontend": 8001,
            "addcartitem": 8002,
            "cartkvstorage": 8003,
            "getcart": 8004,
            "emptycart": 8005,
            "listproducts": 8006,
            "getproduct": 8007,
            "searchproducts": 8008,
            "listrecommendations": 8009,
            "shipmentquote": 8010,
            "shiporder": 8011,
            "checkout": 8012,
            "payment": 8013,
            "currency": 8014,
            "supportedcurrencies": 8015,
            "getads": 8016,
            "email": 8017
        }
    
    async def setup(self):
        """Setup HTTP Client"""
        self.client = httpx.AsyncClient(timeout=120.0)
        logger.info("HTTP Client initialisiert")
    
    async def cleanup(self):
        """Cleanup HTTP Client"""
        if self.client:
            await self.client.aclose()
    
    async def invoke_function(self, service_name: str, payload: dict) -> dict:
        """
        Ruft eine einzelne Funktion über HTTP auf
        """
        port = self.service_ports.get(service_name)
        if not port:
            raise ValueError(f"Service {service_name} nicht gefunden")
        
        url = f"{self.base_url}:{port}/invoke"
        
        try:
            start_time = time.time()
            response = await self.client.post(url, json=payload)
            end_time = time.time()
            
            response.raise_for_status()
            result = response.json()
            
            # Füge Timing-Informationen hinzu
            result["execution_time_ms"] = (end_time - start_time) * 1000
            result["service"] = service_name
            
            return result
            
        except Exception as e:
            logger.error(f"Fehler beim Aufruf von {service_name}: {e}")
            return {"error": str(e), "service": service_name}
    
    async def test_individual_functions(self) -> Dict[str, Any]:
        """
        Test 1: Individuelle Funktionsaufrufe (keine Fusion)
        Simuliert jeden Container als separate Lambda-Funktion
        """
        logger.info("=== Test 1: Individuelle Funktionsaufrufe ===")
        
        test_event = {
            "userId": "user123",
            "productId": "prod456",
            "quantity": 2
        }
        
        results = {}
        
        # Test: Add to Cart (ohne Fusion)
        start_time = time.time()
        
        # Schritt 1: Add Cart Item
        add_result = await self.invoke_function("addcartitem", test_event)
        logger.info(f"Add to Cart: {add_result.get('execution_time_ms', 0):.2f}ms")
        
        # Schritt 2: Cart Storage (separater Aufruf)
        storage_event = {
            "operation": "add",
            "userId": test_event["userId"],
            "item": {
                "productId": test_event["productId"],
                "quantity": test_event["quantity"]
            }
        }
        storage_result = await self.invoke_function("cartkvstorage", storage_event)
        logger.info(f"Cart Storage: {storage_result.get('execution_time_ms', 0):.2f}ms")
        
        total_time = time.time() - start_time
        
        results["individual_calls"] = {
            "total_time_ms": total_time * 1000,
            "add_cart_time_ms": add_result.get('execution_time_ms', 0),
            "storage_time_ms": storage_result.get('execution_time_ms', 0),
            "overhead_ms": (total_time * 1000) - add_result.get('execution_time_ms', 0) - storage_result.get('execution_time_ms', 0),
            "steps": [add_result, storage_result]
        }
        
        logger.info(f"Gesamtzeit individuelle Aufrufe: {total_time * 1000:.2f}ms")
        return results
    
    async def test_fusion_simulation(self) -> Dict[str, Any]:
        """
        Test 2: Simulierte Function Fusion
        Ruft addcartitem auf, welches intern cartkvstorage aufruft
        """
        logger.info("=== Test 2: Simulierte Function Fusion ===")
        
        test_event = {
            "userId": "user123",
            "productId": "prod456", 
            "quantity": 2
        }
        
        start_time = time.time()
        
        # Add Cart Item ruft intern cartkvstorage auf
        fusion_result = await self.invoke_function("addcartitem", test_event)
        
        total_time = time.time() - start_time
        
        results = {
            "fusion_call": {
                "total_time_ms": total_time * 1000,
                "result": fusion_result
            }
        }
        
        logger.info(f"Gesamtzeit Fusion: {total_time * 1000:.2f}ms")
        return results
    
    async def test_complex_workflow(self) -> Dict[str, Any]:
        """
        Test 3: Komplexer Workflow - Checkout Prozess
        Testet längere Funktionsketten
        """
        logger.info("=== Test 3: Komplexer Checkout Workflow ===")
        
        results = {}
        
        # Test A: Individuell (Remote Calls)
        start_time = time.time()
        
        # 1. Add to Cart
        add_event = {"userId": "user789", "productId": "prod101", "quantity": 1}
        await self.invoke_function("addcartitem", add_event)
        
        # 2. Calculate Shipping  
        shipping_event = {"userId": "user789", "items": [{"productId": "prod101", "quantity": 1}]}
        await self.invoke_function("shipmentquote", shipping_event)
        
        # 3. Process Payment
        payment_event = {"amount": 100, "currency": "USD"}
        await self.invoke_function("payment", payment_event)
        
        individual_time = time.time() - start_time
        
        results["complex_individual"] = {
            "total_time_ms": individual_time * 1000
        }
        
        # Test B: Fusion (Lokale Calls)
        # Hier würde man die checkout Funktion verwenden, die intern alle Schritte macht
        start_time = time.time()
        
        checkout_event = {
            "userId": "user789",
            "productId": "prod101", 
            "quantity": 1,
            "userCurrency": "USD",
            "address": {"country": "Germany", "city": "Berlin"},
            "email": "test@example.com"
        }
        
        fusion_result = await self.invoke_function("checkout", checkout_event)
        fusion_time = time.time() - start_time
        
        results["complex_fusion"] = {
            "total_time_ms": fusion_time * 1000,
            "result": fusion_result
        }
        
        # Vergleich
        speedup = individual_time / fusion_time if fusion_time > 0 else 0
        results["comparison"] = {
            "individual_time_ms": individual_time * 1000,
            "fusion_time_ms": fusion_time * 1000,
            "speedup_factor": speedup,
            "time_saved_ms": (individual_time - fusion_time) * 1000
        }
        
        logger.info(f"Individuell: {individual_time * 1000:.2f}ms")
        logger.info(f"Fusion: {fusion_time * 1000:.2f}ms") 
        logger.info(f"Speedup: {speedup:.2f}x")
        
        return results
    
    async def test_network_effects(self) -> Dict[str, Any]:
        """
        Test 4: Netzwerkeffekte messen
        Misst die Auswirkungen der konfigurierten Latenz (100ms + 10ms Jitter)
        """
        logger.info("=== Test 4: Netzwerkeffekte ===")
        
        results = {}
        repetitions = 5
        
        # Teste einzelne Aufrufe mehrfach
        latencies = []
        
        for i in range(repetitions):
            start_time = time.time()
            await self.invoke_function("getcart", {"userId": "test"})
            latency = (time.time() - start_time) * 1000
            latencies.append(latency)
            logger.info(f"Durchlauf {i+1}: {latency:.2f}ms")
        
        avg_latency = sum(latencies) / len(latencies)
        min_latency = min(latencies)
        max_latency = max(latencies)
        
        results["network_effects"] = {
            "average_latency_ms": avg_latency,
            "min_latency_ms": min_latency,
            "max_latency_ms": max_latency,
            "latencies": latencies,
            "configured_base_latency_ms": 100,
            "configured_jitter_ms": 10
        }
        
        logger.info(f"Durchschnittliche Latenz: {avg_latency:.2f}ms")
        logger.info(f"Min: {min_latency:.2f}ms, Max: {max_latency:.2f}ms")
        
        return results
        
    async def test_different_regions(self) -> Dict[str, Any]:
        """
        Test 5: Regionseffekte testen
        Testet Services in verschiedenen Regionen
        """
        logger.info("=== Test 5: Regionseffekte ===")
        
        results = {}
        
        # Services in verschiedenen Regionen
        region_tests = [
            ("cartkvstorage", "us-east-1", {"operation": "get", "userId": "test-user"}),
            ("shipmentquote", "us-west-2", {"userId": "test-user", "items": []}),
            ("payment", "us-west-2", {"orderId": "xyz", "amount": 42.0}),
            ("currency", "eu-west-1", {"from": 1.0, "toCode": "EUR"})
        ]
        
        for service, region, event in region_tests:
            latencies = []
            
            for _ in range(3):
                start_time = time.time()
                await self.invoke_function(service, event)
                latency = (time.time() - start_time) * 1000
                latencies.append(latency)
            
            avg_latency = sum(latencies) / len(latencies)
            results[f"{service}_{region}"] = {
                "average_latency_ms": avg_latency,
                "region": region,
                "latencies": latencies
            }
            
            logger.info(f"{service} ({region}): {avg_latency:.2f}ms")
        
        return results
    
    async def test_io_performance_sampling(self, sampling_rate=0.01) -> Dict[str, Any]:
        """
        Test 6: I/O-Performance mit Sampling-Ansatz
        Führt reguläre Tests mit leichtgewichtigen I/O durch und verwendet FIO nur für eine Teilmenge
        
        Args:
            sampling_rate: Anteil der Tests, die FIO verwenden sollen (0.0-1.0)
        """
        logger.info(f"=== Test 6: I/O-Performance mit Sampling (Rate: {sampling_rate:.1%}) ===")
        
        results = {}
        runs = 10  # Anzahl der Testläufe
        
        # I/O-Konfigurationen für verschiedene Intensitäten
        io_configs = [
            {"iterations": 1, "file_size_kb": 10, "enable_fsync": False},  # Leicht
            {"iterations": 5, "file_size_kb": 50, "enable_fsync": True},   # Mittel
            {"iterations": 10, "file_size_kb": 100, "enable_fsync": True}  # Schwer
        ]
        
        # Tests für jede I/O-Konfiguration
        for config_index, io_config in enumerate(io_configs):
            config_name = f"io_intensity_{config_index}"
            results[config_name] = {
                "config": io_config,
                "direct_calls": [],
                "fusion_calls": [],
                "fio_samples": []
            }
            
            logger.info(f"Teste I/O-Konfiguration {config_index+1}/{len(io_configs)}: {io_config}")
            
            for i in range(runs):
                # Bestimme, ob dieser Test FIO verwenden soll
                use_fio = random.random() < sampling_rate
                
                # Erstelle die Parameter für den Test
                test_id = f"io_test_{config_index}_{i}_{int(time.time())}"
                params = {
                    "io_params": {
                        **io_config,
                        "enable_fio": use_fio
                    }
                }
                
                # Test 1: Direkte I/O-Operationen
                start_time = time.time()
                direct_result = await self.invoke_function("cartkvstorage", {
                    "operation": "add",
                    "userId": f"{test_id}_direct",
                    "item": {"productId": "perf_test", "quantity": 1},
                    **params
                })
                direct_time = (time.time() - start_time) * 1000
                
                # Extrahiere Performance-Daten
                direct_perf = self._extract_performance_data(direct_result)
                direct_perf["total_time_ms"] = direct_time
                results[config_name]["direct_calls"].append(direct_perf)
                
                # Test 2: Function Fusion
                start_time = time.time()
                fusion_result = await self.invoke_function("addcartitem", {
                    "userId": f"{test_id}_fusion",
                    "productId": "perf_test",
                    "quantity": 1,
                    **params
                })
                fusion_time = (time.time() - start_time) * 1000
                
                # Extrahiere Performance-Daten
                fusion_perf = self._extract_fusion_performance_data(fusion_result)
                fusion_perf["total_time_ms"] = fusion_time
                results[config_name]["fusion_calls"].append(fusion_perf)
                
                # Speichere FIO-Ergebnisse, falls vorhanden
                if use_fio and "fio_stats" in direct_perf:
                    results[config_name]["fio_samples"].append(direct_perf["fio_stats"])
                
                # Logge Fortschritt
                logger.info(f"  Lauf {i+1}/{runs}: " + 
                             f"Direkt {direct_time:.1f}ms, Fusion {fusion_time:.1f}ms " +
                             f"(FIO: {'Ja' if use_fio else 'Nein'})")
            
            # Berechne Durchschnittswerte für diese Konfiguration
            avg_direct = self._calculate_average_metrics(results[config_name]["direct_calls"])
            avg_fusion = self._calculate_average_metrics(results[config_name]["fusion_calls"])
            
            speedup = avg_direct["total_time_ms"] / avg_fusion["total_time_ms"] if avg_fusion["total_time_ms"] > 0 else 0
            
            results[config_name]["summary"] = {
                "avg_direct_time_ms": avg_direct["total_time_ms"],
                "avg_fusion_time_ms": avg_fusion["total_time_ms"],
                "speedup_factor": speedup,
                "fio_sample_count": len(results[config_name]["fio_samples"])
            }
            
            logger.info(f"Zusammenfassung für I/O-Konfiguration {config_index+1}:")
            logger.info(f"  Direkt: {avg_direct['total_time_ms']:.1f}ms")
            logger.info(f"  Fusion: {avg_fusion['total_time_ms']:.1f}ms")
            logger.info(f"  Speedup: {speedup:.2f}x")
        
        return results
    
    def _extract_performance_data(self, result):
        """Extrahiert Performance-Daten aus dem Ergebnis."""
        if isinstance(result, dict) and "body" in result:
            body = result["body"]
            if isinstance(body, dict) and "performance" in body:
                return body["performance"]
        return {}
    
    def _extract_fusion_performance_data(self, result):
        """Extrahiert Performance-Daten aus dem Fusion-Ergebnis."""
        if isinstance(result, dict) and "body" in result:
            body = result["body"]
            if isinstance(body, dict) and "response" in body:
                response = body["response"]
                if isinstance(response, dict) and "body" in response:
                    resp_body = response["body"]
                    if isinstance(resp_body, dict) and "performance" in resp_body:
                        return resp_body["performance"]
        return {}
    
    def _calculate_average_metrics(self, metrics_list):
        """Berechnet Durchschnittswerte für eine Liste von Metriken."""
        if not metrics_list:
            return {"total_time_ms": 0}
        
        result = {"total_time_ms": 0}
        for metrics in metrics_list:
            for key, value in metrics.items():
                if isinstance(value, (int, float)):
                    result[key] = result.get(key, 0) + value
        
        for key in result:
            result[key] /= len(metrics_list)
        
        return result
        
    async def run_all_tests(self) -> Dict[str, Any]:
        """
        Führt alle Tests aus und sammelt die Ergebnisse
        """
        logger.info("Starte Function Fusion Tests mit Docker Setup")
        
        all_results = {
            "timestamp": datetime.now().isoformat(),
            "test_type": "docker_fusion_test"
        }
        
        # Warte kurz, um sicherzustellen, dass alle Container bereit sind
        logger.info("Warte 5 Sekunden auf Container-Initialisierung...")
        await asyncio.sleep(5)
        
        # Führe alle Tests aus
        test_methods = [
            ("individual_functions", self.test_individual_functions),
            ("fusion_simulation", self.test_fusion_simulation), 
            ("complex_workflow", self.test_complex_workflow),
            ("network_effects", self.test_network_effects),
            ("region_effects", self.test_different_regions),
            ("io_performance", lambda: self.test_io_performance_sampling(0.2))  # 20% FIO-Sampling für Demo
        ]
        
        for test_name, test_method in test_methods:
            try:
                logger.info(f"\n--- Starte {test_name} ---")
                result = await test_method()
                all_results[test_name] = result
                logger.info(f"--- {test_name} abgeschlossen ---\n")
            except Exception as e:
                logger.error(f"Fehler bei {test_name}: {e}")
                all_results[test_name] = {"error": str(e)}
        
        # Speichere Ergebnisse
        os.makedirs("results", exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_file = f"results/docker_fusion_test_{timestamp}.json"
        
        with open(results_file, "w") as f:
            json.dump(all_results, f, indent=2)
        
        logger.info(f"Testergebnisse gespeichert in: {results_file}")
        
        # Zusammenfassung
        self._print_summary(all_results)
        
        return all_results
    
    def _print_summary(self, results: Dict[str, Any]):
        """
        Druckt eine Zusammenfassung der Testergebnisse
        """
        logger.info("\n" + "="*50)
        logger.info("ZUSAMMENFASSUNG DER TESTERGEBNISSE")
        logger.info("="*50)
        
        # Function Fusion Vergleich
        if "individual_functions" in results and "fusion_simulation" in results:
            individual_time = results["individual_functions"].get("individual_calls", {}).get("total_time_ms", 0)
            fusion_time = results["fusion_simulation"].get("fusion_call", {}).get("total_time_ms", 0)
            
            if fusion_time > 0:
                speedup = individual_time / fusion_time
                saved_time = individual_time - fusion_time
                
                logger.info(f"Einfacher Function Fusion Test:")
                logger.info(f"  Individuelle Aufrufe: {individual_time:.2f}ms")
                logger.info(f"  Function Fusion: {fusion_time:.2f}ms")
                logger.info(f"  Speedup: {speedup:.2f}x")
                logger.info(f"  Gesparte Zeit: {saved_time:.2f}ms")
        
        # Komplexer Workflow Vergleich
        if "complex_workflow" in results and "comparison" in results["complex_workflow"]:
            comp = results["complex_workflow"]["comparison"]
            logger.info(f"\nKomplexer Workflow Test:")
            logger.info(f"  Individuelle Aufrufe: {comp['individual_time_ms']:.2f}ms")
            logger.info(f"  Function Fusion: {comp['fusion_time_ms']:.2f}ms")
            logger.info(f"  Speedup: {comp['speedup_factor']:.2f}x")
            logger.info(f"  Gesparte Zeit: {comp['time_saved_ms']:.2f}ms")
        
        # Netzwerkeffekte
        if "network_effects" in results:
            net = results["network_effects"]["network_effects"]
            logger.info(f"\nNetzwerkeffekte:")
            logger.info(f"  Durchschnittliche Latenz: {net['average_latency_ms']:.2f}ms")
            logger.info(f"  Konfigurierte Latenz: {net['configured_base_latency_ms']}ms ± {net['configured_jitter_ms']}ms")
        
        # I/O-Performance (neu)
        if "io_performance" in results:
            logger.info("\nI/O-Performance Tests:")
            for config_name, config_data in results["io_performance"].items():
                if "summary" in config_data:
                    summary = config_data["summary"]
                    logger.info(f"  {config_name}:")
                    logger.info(f"    Direkt: {summary['avg_direct_time_ms']:.1f}ms")
                    logger.info(f"    Fusion: {summary['avg_fusion_time_ms']:.1f}ms")
                    logger.info(f"    Speedup: {summary['speedup_factor']:.2f}x")
                    logger.info(f"    FIO-Samples: {summary['fio_sample_count']}")
        
        logger.info("="*50)

async def main():
    """
    Hauptfunktion zum Ausführen der Function Fusion Tests
    """
    tester = DockerFusionTester()
    
    try:
        await tester.setup()
        results = await tester.run_all_tests()
        return results
    finally:
        await tester.cleanup()

if __name__ == "__main__":
    # Führe die Tests aus
    results = asyncio.run(main())
    print("\nTests abgeschlossen! Details in den Log-Ausgaben und results/ Verzeichnis.")