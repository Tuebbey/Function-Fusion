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
            "add-cart-item": 8002,
            "cart-kv-storage": 8003,
            "get-cart": 8004,
            "empty-cart": 8005,
            "list-products": 8006,
            "get-product": 8007,
            "search-products": 8008,
            "list-recommendations": 8009,
            "shipment-quote": 8010,
            "ship-order": 8011,
            "checkout": 8012,
            "payment": 8013,
            "currency": 8014,
            "supported-currencies": 8015,
            "get-ads": 8016,
            "email": 8017
        }
    
    async def setup(self):
        """Setup HTTP Client"""
        self.client = httpx.AsyncClient(timeout=30.0)
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
        add_result = await self.invoke_function("add-cart-item", test_event)
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
        storage_result = await self.invoke_function("cart-kv-storage", storage_event)
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
        Ruft add-cart-item auf, welches intern cart-kv-storage aufruft
        """
        logger.info("=== Test 2: Simulierte Function Fusion ===")
        
        test_event = {
            "userId": "user123",
            "productId": "prod456", 
            "quantity": 2
        }
        
        start_time = time.time()
        
        # Add Cart Item ruft intern cart-kv-storage auf
        fusion_result = await self.invoke_function("add-cart-item", test_event)
        
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
        await self.invoke_function("add-cart-item", add_event)
        
        # 2. Calculate Shipping  
        shipping_event = {"userId": "user789", "items": [{"productId": "prod101", "quantity": 1}]}
        await self.invoke_function("shipment-quote", shipping_event)
        
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
            await self.invoke_function("get-cart", {"userId": "test"})
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
            ("cart-kv-storage", "us-east-1", {"operation": "get", "userId": "test-user"}),
            ("shipment-quote", "us-west-2", {"userId": "test-user", "items": []}),
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
            ("region_effects", self.test_different_regions)
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
            individual_time = results["individual_functions"].get("total_time_ms", 0)
            fusion_time = results["fusion_simulation"]["fusion_call"].get("total_time_ms", 0)
            
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