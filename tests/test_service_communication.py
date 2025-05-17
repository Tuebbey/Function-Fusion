# tests/test_service_communication.py

import asyncio
import os
import sys
import json
import logging
import time
from datetime import datetime
from typing import Dict, List, Any

# Füge das Root-Verzeichnis zum Python-Pfad hinzu
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Importiere die notwendigen Module
from app.runtime import runtime
from app.fusion_enhanced import enhanced_fusion_engine
from app.communication.service_model import ServiceCommunicationModel
from app.optimizer.communication_aware_optimizer import CommunicationAwareOptimizer
from evaluation.improved_cost_model import ImprovedCostModel

# Logger konfigurieren
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("service-comm-test")

# Test-Handler-Funktionen
async def api_gateway_handler(event, context=None, call_function=None):
    """Eine Funktion, die über API Gateway aufgerufen wird."""
    logger.info(f"API Gateway Handler aufgerufen mit: {event}")
    
    # Simuliere einige Verarbeitungen
    await asyncio.sleep(0.1)  # 100ms Basisverarbeitung
    
    # Rufe eine weitere Funktion über HTTP auf
    if call_function:
        result = await call_function("http_handler", {"data": "from_api_gateway"}, True)
        return {
            "source": "api_gateway_handler",
            "processed_data": event,
            "nested_result": result
        }
    else:
        return {
            "source": "api_gateway_handler",
            "processed_data": event
        }

async def http_handler(event, context=None, call_function=None):
    """Eine Funktion, die über HTTP aufgerufen wird."""
    logger.info(f"HTTP Handler aufgerufen mit: {event}")
    
    # Simuliere einige Verarbeitungen
    await asyncio.sleep(0.08)  # 80ms Basisverarbeitung
    
    # Rufe eine Event-Service-Funktion auf
    if call_function:
        await call_function("event_handler", {"data": "from_http_handler"}, False)
    
    return {
        "source": "http_handler",
        "processed_data": event,
        "timestamp": time.time()
    }

async def event_handler(event, context=None, call_function=None):
    """Eine Funktion, die über einen Event-Service aufgerufen wird."""
    logger.info(f"Event Handler aufgerufen mit: {event}")
    
    # Simuliere einige Verarbeitungen
    await asyncio.sleep(0.12)  # 120ms Basisverarbeitung
    
    # Diese Funktion ruft keinen weiteren Service auf
    return {
        "source": "event_handler",
        "processed_data": event,
        "timestamp": time.time()
    }

async def direct_handler(event, context=None, call_function=None):
    """Eine Funktion, die direkt aufgerufen wird."""
    logger.info(f"Direct Handler aufgerufen mit: {event}")
    
    # Simuliere einige Verarbeitungen
    await asyncio.sleep(0.05)  # 50ms Basisverarbeitung
    
    # Rufe eine weitere Funktion direkt auf
    if call_function:
        result = await call_function("api_gateway_handler", {"data": "from_direct_handler"}, True)
        return {
            "source": "direct_handler",
            "processed_data": event,
            "nested_result": result
        }
    else:
        return {
            "source": "direct_handler",
            "processed_data": event
        }

class ServiceCommunicationTester:
    def __init__(self):
        # Verzeichnis für Testergebnisse
        self.results_dir = os.path.join(os.path.dirname(__file__), "../results/service_comm_tests")
        os.makedirs(self.results_dir, exist_ok=True)
        
        # Modelle initialisieren
        self.service_model = ServiceCommunicationModel()
        self.cost_model = ImprovedCostModel(provider="aws_lambda")
        
        # Testresultate
        self.results = {}
    
    async def setup_environment(self):
        """Richtet die Testumgebung ein."""
        logger.info("Testumgebung wird eingerichtet...")
        
        # Handler-Funktionen registrieren
        runtime.register("api_gateway_handler", api_gateway_handler, memory=256, timeout=5)
        runtime.register("http_handler", http_handler, memory=128, timeout=3)
        runtime.register("event_handler", event_handler, memory=128, timeout=3)
        runtime.register("direct_handler", direct_handler, memory=128, timeout=3)
        
        # Fusion Engine mit dem Service-Kommunikationsmodell konfigurieren
        enhanced_fusion_engine.service_model = self.service_model
        
        # Fusion-Setups erstellen
        self._create_fusion_setups()
        
        logger.info("Testumgebung erfolgreich eingerichtet.")
    
    def _create_fusion_setups(self):
        """Erstellt verschiedene Fusion-Setups für die Tests."""
        # Verschiedene Kommunikationsmuster konfigurieren
        
        # Setup 1: Alle Funktionen in einer Gruppe (direkte Aufrufe)
        enhanced_fusion_engine.register_fusion(
            "all_direct_fusion",
            ["direct_handler", "api_gateway_handler", "http_handler", "event_handler"]
        )
        
        # Setup 2: Jede Funktion in einer eigenen Gruppe (alle Remote-Aufrufe)
        enhanced_fusion_engine.register_fusion(
            "all_remote_fusion",
            ["direct_handler"]
        )
        enhanced_fusion_engine.register_fusion(
            "api_gateway_group",
            ["api_gateway_handler"]
        )
        enhanced_fusion_engine.register_fusion(
            "http_group",
            ["http_handler"]
        )
        enhanced_fusion_engine.register_fusion(
            "event_group",
            ["event_handler"]
        )
        
        # Setup 3: Gemischte Gruppen
        enhanced_fusion_engine.register_fusion(
            "mixed_fusion_1",
            ["direct_handler", "api_gateway_handler"]  # Diese beiden in einer Gruppe
        )
        enhanced_fusion_engine.register_fusion(
            "mixed_fusion_2",
            ["http_handler", "event_handler"]  # Diese beiden in einer anderen Gruppe
        )
        
        # Setup 4: Optimierte Gruppierung (basierend auf Synchronizität)
        enhanced_fusion_engine.register_fusion(
            "optimized_fusion_1",
            ["direct_handler", "api_gateway_handler", "http_handler"]  # Synchrone Aufrufe zusammen
        )
        enhanced_fusion_engine.register_fusion(
            "optimized_fusion_2",
            ["event_handler"]  # Asynchrone Funktion separat
        )
        
        # Kommunikationseinstellungen konfigurieren
        enhanced_fusion_engine.configure_communication({
            "enable_service_mesh": False,
            "default_communication_type": "http",
            "default_serialization": "json",
            "default_auth_type": "none",
            "enable_communication_stats": True
        })
        
        # Funktionsspezifische Kommunikationseinstellungen
        enhanced_fusion_engine.set_function_communication_config(
            "api_gateway_handler", 
            {
                "communication_type": "api_gateway",
                "api_gateway_type": "regional",
                "auth_type": "api_key"
            }
        )
        
        enhanced_fusion_engine.set_function_communication_config(
            "http_handler", 
            {
                "communication_type": "http",
                "serialization": "json",
                "compression": "gzip",
                "use_keep_alive": True
            }
        )
        
        enhanced_fusion_engine.set_function_communication_config(
            "event_handler", 
            {
                "communication_type": "event",
                "event_service": "sqs",
                "event_operation": "send"
            }
        )
    
    async def run_basic_communication_tests(self):
        """Führt grundlegende Tests für verschiedene Kommunikationstypen durch."""
        logger.info("Starte grundlegende Kommunikationstests...")
        
        # Test 1: Direkte API Gateway Kommunikation simulieren
        api_gateway_params = {
            "deployment_type": "regional",
            "auth_type": "api_key",
            "region": "us-east-1",
            "payload_size_kb": 5.0,
            "time_of_day": 14.0  # 14:00 Uhr (Nachmittag, Spitzenzeit)
        }
        
        api_result = self.service_model.simulate_communication("api_gateway", api_gateway_params)
        logger.info(f"API Gateway Kommunikation: {api_result}")
        
        # Test 2: HTTP Kommunikation simulieren
        http_params = {
            "use_keep_alive": True,
            "payload_size_kb": 10.0,
            "serialization_format": "json",
            "compression": "gzip",
            "auth_overhead_ms": 5.0,
            "region": "us-east-1",
            "time_of_day": 14.0
        }
        
        http_result = self.service_model.simulate_communication("http", http_params)
        logger.info(f"HTTP Kommunikation: {http_result}")
        
        # Test 3: Event-basierte Kommunikation simulieren
        event_params = {
            "service": "sqs",
            "operation": "send",
            "payload_size_kb": 2.0,
            "region": "us-east-1",
            "time_of_day": 14.0
        }
        
        event_result = self.service_model.simulate_communication("event", event_params)
        logger.info(f"Event-basierte Kommunikation: {event_result}")
        
        # Test 4: Direkte Kommunikation simulieren
        direct_result = self.service_model.simulate_communication("direct", {})
        logger.info(f"Direkte Kommunikation: {direct_result}")
        
        # Ergebnisse speichern
        self.results["basic_communication_tests"] = {
            "api_gateway": api_result,
            "http": http_result,
            "event": event_result,
            "direct": direct_result
        }
        
        logger.info("Grundlegende Kommunikationstests abgeschlossen.")
        return self.results["basic_communication_tests"]
    
    async def run_fusion_execution_tests(self):
        """Führt Tests mit verschiedenen Fusion-Setups durch, um Kommunikationseinflüsse zu messen."""
        logger.info("Starte Fusion-Ausführungstests...")
        
        test_event = {"data": "test_input", "timestamp": time.time()}
        results = {}
        
        # Test 1: Alle Funktionen direkt (in einer Gruppe)
        logger.info("Test 1: Alle Funktionen direkt (in einer Gruppe)")
        direct_result = await enhanced_fusion_engine.execute(
            "all_direct_fusion",
            test_event,
            runtime
        )
        results["all_direct"] = direct_result
        logger.info(f"Gesamtausführungszeit: {direct_result.get('execution_time', 0):.3f}s")
        logger.info(f"Kommunikationslatenz: {direct_result.get('communication_stats', {}).get('total_latency', 0):.2f}ms")
        
        # Test 2: Alle Funktionen remote (in separaten Gruppen)
        logger.info("Test 2: Funktionskette mit Remote-Aufrufen")
        
        # Wir starten mit direct_handler und folgen der Aufrufkette
        remote_result = await enhanced_fusion_engine.execute(
            "all_remote_fusion",
            test_event,
            runtime
        )
        results["all_remote"] = remote_result
        logger.info(f"Gesamtausführungszeit: {remote_result.get('execution_time', 0):.3f}s")
        logger.info(f"Kommunikationslatenz: {remote_result.get('communication_stats', {}).get('total_latency', 0):.2f}ms")
        
        # Test 3: Gemischtes Setup 1
        logger.info("Test 3: Gemischtes Setup 1")
        mixed1_result = await enhanced_fusion_engine.execute(
            "mixed_fusion_1",
            test_event,
            runtime
        )
        results["mixed_1"] = mixed1_result
        logger.info(f"Gesamtausführungszeit: {mixed1_result.get('execution_time', 0):.3f}s")
        logger.info(f"Kommunikationslatenz: {mixed1_result.get('communication_stats', {}).get('total_latency', 0):.2f}ms")
        
        # Test 4: Optimiertes Setup
        logger.info("Test 4: Optimiertes Setup")
        optimized_result = await enhanced_fusion_engine.execute(
            "optimized_fusion_1",
            test_event,
            runtime
        )
        results["optimized"] = optimized_result
        logger.info(f"Gesamtausführungszeit: {optimized_result.get('execution_time', 0):.3f}s")
        logger.info(f"Kommunikationslatenz: {optimized_result.get('communication_stats', {}).get('total_latency', 0):.2f}ms")
        
        # Ergebnisse speichern
        self.results["fusion_execution_tests"] = results
        
        # Kommunikationsstatistiken abrufen
        comm_stats = enhanced_fusion_engine.get_communication_stats()
        self.results["communication_stats"] = comm_stats
        logger.info(f"Gesamtkommunikationsstatistiken: {comm_stats}")
        
        logger.info("Fusion-Ausführungstests abgeschlossen.")
        return results
    
    async def run_optimizer_tests(self):
        """Testet den kommunikationsbewussten Optimizer."""
        logger.info("Starte Optimizer-Tests...")
        
        # Optimizer mit dem Service-Kommunikationsmodell initialisieren
        optimizer = CommunicationAwareOptimizer(
            lambda_runtime=runtime,
            fusion_engine=enhanced_fusion_engine,
            cost_model=self.cost_model,
            communication_model=self.service_model
        )
        
        # Gewichtungen setzen
        optimizer.set_communication_weights(
            latency=0.4,
            cost=0.3,
            comm_latency=0.2,
            comm_cost=0.1
        )
        
        # Kommunikationsstrategien konfigurieren
        optimizer.set_communication_strategies({
            "sync_local": "direct",
            "sync_remote": "http",
            "async_local": "event",
            "async_remote": "api_gateway"
        })
        
        # Testdaten für den Optimizer erstellen
        # Wir verwenden die Ergebnisse der vorherigen Tests
        test_results = {
            "all_direct": [self.results["fusion_execution_tests"]["all_direct"]],
            "all_remote": [self.results["fusion_execution_tests"]["all_remote"]],
            "mixed_1": [self.results["fusion_execution_tests"]["mixed_1"]],
            "optimized": [self.results["fusion_execution_tests"]["optimized"]]
        }
        
        # Testdaten in den Optimizer laden
        optimizer.set_test_results(test_results)
        
        # Optimierung durchführen
        logger.info("Starte dreistufige Optimierung...")
        path_groups, memory_configs, comm_settings = optimizer.optimize()
        
        # Optimale Konfiguration ermitteln
        optimal_config = optimizer.get_optimal_configuration_with_communication()
        logger.info(f"Optimale Konfiguration: {optimal_config}")
        
        # Ergebnisse speichern
        optimization_result = {
            "path_groups": path_groups,
            "memory_configs": memory_configs,
            "communication_settings": comm_settings,
            "optimal_config": optimal_config
        }
        
        self.results["optimizer_tests"] = optimization_result
        
        # Optimierungsergebnisse speichern
        result_path = os.path.join(self.results_dir, "optimization_results.json")
        optimizer.save_optimization_results(result_path)
        logger.info(f"Optimierungsergebnisse gespeichert in: {result_path}")
        
        logger.info("Optimizer-Tests abgeschlossen.")
        return optimization_result
    
    async def run_communication_benchmark(self):
        """Führt Benchmark-Tests für verschiedene Kommunikationstypen durch."""
        logger.info("Starte Kommunikations-Benchmark...")
        
        benchmark_results = {}
        repetitions = 10  # Anzahl der Wiederholungen pro Kommunikationstyp
        
        # Benchmark für API Gateway
        logger.info("Benchmark für API Gateway...")
        api_latencies = []
        api_costs = []
        
        for i in range(repetitions):
            payload_size = 1.0 + (i * 2)  # Unterschiedliche Payload-Größen von 1KB bis 21KB
            api_params = {
                "deployment_type": "regional",
                "auth_type": "api_key",
                "region": "us-east-1",
                "payload_size_kb": payload_size,
                "time_of_day": 14.0
            }
            
            result = self.service_model.simulate_communication("api_gateway", api_params)
            api_latencies.append(result["latency_ms"])
            api_costs.append(result["cost"])
            
            logger.info(f"  Durchlauf {i+1}/{repetitions}: Latenz={result['latency_ms']:.2f}ms, Kosten=${result['cost']:.8f}")
        
        benchmark_results["api_gateway"] = {
            "mean_latency": sum(api_latencies) / len(api_latencies),
            "min_latency": min(api_latencies),
            "max_latency": max(api_latencies),
            "mean_cost": sum(api_costs) / len(api_costs),
            "total_cost": sum(api_costs),
            "raw_data": {"latencies": api_latencies, "costs": api_costs}
        }
        
        # Benchmark für HTTP
        logger.info("Benchmark für HTTP...")
        http_latencies = []
        http_costs = []
        
        serialization_formats = ["json", "xml", "protobuf", "avro"]
        compression_types = ["none", "gzip", "brotli"]
        
        for i in range(repetitions):
            # Rotiere durch verschiedene Serialisierungs- und Kompressionsformate
            serialization = serialization_formats[i % len(serialization_formats)]
            compression = compression_types[i % len(compression_types)]
            
            http_params = {
                "use_keep_alive": i % 2 == 0,  # Abwechselnd Keep-Alive an/aus
                "payload_size_kb": 5.0,
                "serialization_format": serialization,
                "compression": compression,
                "auth_overhead_ms": 5 if i % 3 == 0 else 0,  # Gelegentlich Auth-Overhead
                "region": "us-east-1",
                "time_of_day": 14.0
            }
            
            result = self.service_model.simulate_communication("http", http_params)
            http_latencies.append(result["latency_ms"])
            http_costs.append(result["cost"])
            
            logger.info(f"  Durchlauf {i+1}/{repetitions}: Format={serialization}, Kompression={compression}, " +
                      f"Latenz={result['latency_ms']:.2f}ms, Kosten=${result['cost']:.8f}")
        
        benchmark_results["http"] = {
            "mean_latency": sum(http_latencies) / len(http_latencies),
            "min_latency": min(http_latencies),
            "max_latency": max(http_latencies),
            "mean_cost": sum(http_costs) / len(http_costs),
            "total_cost": sum(http_costs),
            "raw_data": {"latencies": http_latencies, "costs": http_costs}
        }
        
        # Benchmark für Event-Services
        logger.info("Benchmark für Event-Services...")
        event_latencies = {}
        event_costs = {}
        
        services = ["sqs", "sns", "eventbridge", "kinesis"]
        operations = {
            "sqs": ["send", "receive"],
            "sns": ["publish", "deliver"],
            "eventbridge": ["publish", "route"],
            "kinesis": ["write", "read"]
        }
        
        for service in services:
            event_latencies[service] = []
            event_costs[service] = []
            
            for i in range(repetitions):
                # Verwende verschiedene Operationen für jeden Service
                operation = operations[service][i % len(operations[service])]
                
                event_params = {
                    "service": service,
                    "operation": operation,
                    "payload_size_kb": 2.0 + (i * 0.5),  # Variiere Payload-Größe
                    "region": "us-east-1",
                    "time_of_day": 14.0
                }
                
                result = self.service_model.simulate_communication("event", event_params)
                event_latencies[service].append(result["latency_ms"])
                event_costs[service].append(result["cost"])
                
                logger.info(f"  Service={service}, Operation={operation}, " +
                          f"Latenz={result['latency_ms']:.2f}ms, Kosten=${result['cost']:.8f}")
        
        # Ergebnisse für Event-Services aggregieren
        event_results = {}
        for service in services:
            event_results[service] = {
                "mean_latency": sum(event_latencies[service]) / len(event_latencies[service]),
                "min_latency": min(event_latencies[service]),
                "max_latency": max(event_latencies[service]),
                "mean_cost": sum(event_costs[service]) / len(event_costs[service]),
                "total_cost": sum(event_costs[service]),
                "raw_data": {"latencies": event_latencies[service], "costs": event_costs[service]}
            }
        
        benchmark_results["event_services"] = event_results
        
        # Benchmarkergebnisse speichern
        self.results["benchmark"] = benchmark_results
        
        # Gesamtergebnisse für alle Kommunikationstypen
        self._analyze_benchmark_results(benchmark_results)
        
        logger.info("Kommunikations-Benchmark abgeschlossen.")
        return benchmark_results
    
    def _analyze_benchmark_results(self, results):
        """Analysiert die Benchmark-Ergebnisse und generiert zusammenfassende Statistiken."""
        logger.info("Analyse der Benchmark-Ergebnisse:")
        
        # API Gateway vs. HTTP Vergleich
        api_latency = results["api_gateway"]["mean_latency"]
        http_latency = results["http"]["mean_latency"]
        
        logger.info(f"Durchschnittliche API Gateway Latenz: {api_latency:.2f}ms")
        logger.info(f"Durchschnittliche HTTP Latenz: {http_latency:.2f}ms")
        logger.info(f"Verhältnis API Gateway/HTTP: {api_latency/http_latency:.2f}x")
        
        # Event-Services Vergleich
        event_services = results["event_services"]
        latencies = [event_services[service]["mean_latency"] for service in event_services]
        costs = [event_services[service]["mean_cost"] for service in event_services]
        
        fastest_service = min(event_services.items(), key=lambda x: x[1]["mean_latency"])
        cheapest_service = min(event_services.items(), key=lambda x: x[1]["mean_cost"])
        
        logger.info(f"Schnellster Event-Service: {fastest_service[0]} ({fastest_service[1]['mean_latency']:.2f}ms)")
        logger.info(f"Günstigster Event-Service: {cheapest_service[0]} (${cheapest_service[1]['mean_cost']:.8f})")
        
        # Kosten-Latenz-Tradeoffs
        for service_type in ["api_gateway", "http"]:
            cost = results[service_type]["mean_cost"]
            latency = results[service_type]["mean_latency"]
            cost_per_latency = cost / latency if latency > 0 else 0
            
            logger.info(f"{service_type} Kosten/Latenz-Verhältnis: ${cost_per_latency:.10f}/ms")
    
    async def save_results(self):
        """Speichert alle Testergebnisse."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        result_file = os.path.join(self.results_dir, f"service_comm_test_results_{timestamp}.json")
        
        try:
            with open(result_file, 'w') as f:
                # Konvertiere alle nicht-JSON-serialisierbaren Werte (z.B. Zeitstempel)
                def json_serializable(obj):
                    if isinstance(obj, (datetime, time.struct_time)):
                        return obj.__str__()
                    return str(obj)
                
                json.dump(self.results, f, indent=2, default=json_serializable)
            
            logger.info(f"Testergebnisse gespeichert in: {result_file}")
            return result_file
        except Exception as e:
            logger.error(f"Fehler beim Speichern der Testergebnisse: {str(e)}")
            return None

async def main():
    """Hauptfunktion zum Ausführen aller Tests."""
    logger.info("==== Service-zu-Service Kommunikationstests ====")
    
    tester = ServiceCommunicationTester()
    
    # Testumgebung einrichten
    await tester.setup_environment()
    
    # Tests ausführen
    await tester.run_basic_communication_tests()
    await tester.run_fusion_execution_tests()
    await tester.run_optimizer_tests()
    await tester.run_communication_benchmark()
    
    # Ergebnisse speichern
    result_file = await tester.save_results()
    
    logger.info(f"Alle Tests abgeschlossen. Ergebnisse wurden in {result_file} gespeichert.")

if __name__ == "__main__":
    asyncio.run(main())