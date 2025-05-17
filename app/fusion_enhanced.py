# app/fusion_enhanced.py

import asyncio
import time
import json
import uuid
import logging
from typing import Dict, List, Any, Optional, Callable, Tuple

from app.fusion import FusionEngine, ExecutionTrace, FusionConfiguration, FusionStrategy, FunctionRule
from app.communication.service_model import ServiceCommunicationModel

logger = logging.getLogger("lambda-sim.fusion-enhanced")

class EnhancedFusionEngine(FusionEngine):
    """
    Erweiterte Fusion Engine mit Integration des Service-zu-Service Kommunikationsmodells.
    Erbt von der Basis-FusionEngine und erweitert deren Funktionalität.
    """
    
    def __init__(self):
        # Initialisiere die Basisklasse
        super().__init__()
        
        # Service-Kommunikationsmodell initialisieren
        self.service_model = ServiceCommunicationModel()
        
        # Erweiterte Konfiguration
        self.enhanced_config = {
            "enable_service_mesh": False,
            "default_communication_type": "direct",  # "direct", "http", "api_gateway", "event"
            "default_serialization": "json",
            "default_auth_type": "none",
            "enable_communication_stats": True,
            "communication_stats": {
                "total_latency": 0,
                "total_cost": 0,
                "calls_by_type": {
                    "direct": 0,
                    "http": 0,
                    "api_gateway": 0,
                    "event": 0
                }
            }
        }
        
        # Kommunikationskonfiguration für Funktionen
        self.function_comm_config = {}

    def configure_communication(self, config: Dict[str, Any]) -> None:
        """
        Konfiguriert die Service-zu-Service-Kommunikation.

        Args:
            config: Konfigurationsparameter
        """
        if "enable_service_mesh" in config:
            self.enhanced_config["enable_service_mesh"] = config["enable_service_mesh"]
            # Service Mesh auch im Kommunikationsmodell aktivieren
            self.service_model.config["service_mesh"]["enabled"] = config["enable_service_mesh"]
            
        if "default_communication_type" in config:
            self.enhanced_config["default_communication_type"] = config["default_communication_type"]
            
        if "default_serialization" in config:
            self.enhanced_config["default_serialization"] = config["default_serialization"]
            
        if "default_auth_type" in config:
            self.enhanced_config["default_auth_type"] = config["default_auth_type"]
            
        logger.info(f"Kommunikationskonfiguration aktualisiert: {self.enhanced_config}")

    def set_function_communication_config(self, function_id: str, comm_config: Dict[str, Any]) -> None:
        """
        Setzt spezifische Kommunikationseinstellungen für eine einzelne Funktion.

        Args:
            function_id: ID der Funktion
            comm_config: Kommunikationskonfiguration
        """
        self.function_comm_config[function_id] = comm_config
        logger.info(f"Kommunikationskonfiguration für Funktion {function_id} gesetzt: {comm_config}")

    def get_function_communication_config(self, function_id: str) -> Dict[str, Any]:
        """
        Gibt die Kommunikationskonfiguration für eine Funktion zurück.

        Args:
            function_id: ID der Funktion

        Returns:
            Kommunikationskonfiguration
        """
        return self.function_comm_config.get(function_id, {})

    async def execute(self, name: str, event: dict, runtime, trace_id: str = None,
                     execution_mode: str = "sync", performance_model=None, network_model=None,
                     communication_model=None):
        """
        Führt eine registrierte Fusion aus mit Berücksichtigung des Kommunikationsmodells.
        
        Erweitert die Basisimplementierung um Service-zu-Service Kommunikationsaspekte.

        Args:
            name: Name der Fusion
            event: Eingabedaten für die Fusion
            runtime: Lambda-Runtime zur Ausführung der Funktionen
            trace_id: Optionale Trace-ID für Protokollierung
            execution_mode: 'sync' oder 'async'
            performance_model: Optionales Performance-Modell
            network_model: Optionales Netzwerk-Modell
            communication_model: Optionales Kommunikationsmodell

        Returns:
            Bei sync: Ergebnis der Fusion-Ausführung
            Bei async: Task-ID für späteres Abrufen des Ergebnisses
        """
        if name not in self.fusions:
            raise ValueError(f"[FusionEngine] Fusion '{name}' nicht gefunden.")
            
        # Performance- und Netzwerkmodell an Runtime übergeben
        if performance_model:
            runtime.performance_model = performance_model
        elif not hasattr(runtime, "performance_model"):
            runtime.performance_model = self.performance_model
            
        if network_model:
            runtime.network_model = network_model
        elif not hasattr(runtime, "network_model"):
            runtime.network_model = self.network_model
            
        # Kommunikationsmodell setzen, wenn übergeben
        if communication_model:
            self.service_model = communication_model
            
        # Trace erstellen
        trace = ExecutionTrace(name)
        if trace_id:
            trace.trace_id = trace_id
        self.traces[trace.trace_id] = trace
        
        logger.info(f"[EnhancedFusionEngine] Starte Fusion: {name} (Trace-ID: {trace.trace_id}, Modus: {execution_mode})")
        
        # Asynchrone Ausführung
        if execution_mode == "async":
            # Task erstellen und zurückgeben
            task = asyncio.create_task(
                self._execute_fusion_enhanced(name, event, runtime, trace, performance_model)
            )
            # Task-ID zurückgeben (hier ist es die trace_id)
            return {"task_id": trace.trace_id}
        
        # Synchrone Ausführung
        return await self._execute_fusion_enhanced(name, event, runtime, trace, performance_model)
        
    async def _execute_fusion_enhanced(self, name: str, event: dict, runtime, trace: ExecutionTrace,
                                     performance_model=None):
        """Interne Methode zur Ausführung einer Fusion mit erweitertem Kommunikationsmodell"""
        data = event
        function_chain = self.fusions[name]
        config = self.configurations.get(name, FusionConfiguration(name))
        
        # Statistik für diese Ausführung
        execution_stats = {
            "communication": {
                "total_latency": 0,
                "total_cost": 0,
                "calls": []
            }
        }
        
        # Sequentiell durch die Kette ausführen
        for i in range(len(function_chain)):
            current_func = function_chain[i]
            
            # Trace-Node für diese Funktion erstellen
            node = trace.add_node(current_func)
            
            # Bestimme Ausführungsstrategie und Funktionstyp
            strategy = "local"  # Standardmäßig lokale Ausführung
            function_type = "cpu_intensive"  # Standard-Funktionstyp
            
            # Bestimme das Ziel, wenn es einen nächsten Schritt gibt
            target_region = "us-east-1"  # Standard-Region
            if i < len(function_chain) - 1:
                next_func = function_chain[i + 1]
                rule = config.get_rule(current_func, next_func)
                strategy = rule.sync.strategy
                
                # Erweiterte Informationen aus der Funktion oder Konfiguration auslesen
                if hasattr(runtime.functions.get(current_func, {}), "function_type"):
                    function_type = runtime.functions[current_func].get("function_type", "cpu_intensive")
                if hasattr(runtime.functions.get(current_func, {}), "region"):
                    target_region = runtime.functions[current_func].get("region", "us-east-1")
            
            # Ermittle die zu verwendende Kommunikationsmethode
            comm_type = self._determine_communication_type(current_func, i, len(function_chain))
            
            logger.info(f"[EnhancedFusionEngine] → Schritt {i+1}/{len(function_chain)}: {current_func} " +
                     f"(Strategie: {strategy}, Typ: {function_type}, Komm: {comm_type}) mit Input: {data}")
            
            # Funktion ausführen mit der richtigen Strategie
            try:
                # Trace aktualisieren
                node.start(strategy, "sync")
                
                # Function-spezifische I/O-Operationen bestimmen
                io_operations = None
                if current_func in runtime.functions and "io_operations" in runtime.functions[current_func]:
                    io_operations = runtime.functions[current_func]["io_operations"]
                
                # Kommunikationsoverhead berechnen, wenn nicht direkt
                comm_overhead_ms = 0
                comm_cost = 0
                
                if comm_type != "direct" and i > 0:  # Nur für non-direkte Aufrufe und nicht für die erste Funktion
                    # Kommunikationsparameter bestimmen
                    comm_params = self._get_communication_params(
                        current_func, 
                        data,
                        target_region=target_region,
                        function_type=function_type
                    )
                    
                    # Kommunikation simulieren
                    comm_result = self.service_model.simulate_communication(comm_type, comm_params)
                    
                    # Overhead hinzufügen
                    comm_overhead_ms = comm_result.get("latency_ms", 0)
                    comm_cost = comm_result.get("cost", 0)
                    
                    # Zur Statistik hinzufügen
                    execution_stats["communication"]["total_latency"] += comm_overhead_ms
                    execution_stats["communication"]["total_cost"] += comm_cost
                    execution_stats["communication"]["calls"].append({
                        "from": function_chain[i-1] if i > 0 else "external",
                        "to": current_func,
                        "type": comm_type,
                        "latency_ms": comm_overhead_ms,
                        "cost": comm_cost,
                        "details": comm_result.get("details", {})
                    })
                    
                    # Kommunikations-Overhead als Verzögerung simulieren
                    if comm_overhead_ms > 0:
                        await asyncio.sleep(comm_overhead_ms / 1000)  # In Sekunden umrechnen
                
                # Globale Statistik aktualisieren
                if self.enhanced_config["enable_communication_stats"]:
                    self.enhanced_config["communication_stats"]["total_latency"] += comm_overhead_ms
                    self.enhanced_config["communication_stats"]["total_cost"] += comm_cost
                    self.enhanced_config["communication_stats"]["calls_by_type"][comm_type] += 1
                
                # Funktion aufrufen mit erweiterten Parametern
                data = await runtime.invoke(
                    current_func,
                    data,
                    execution_mode=strategy,
                    source_region="us-east-1",  # Standard, könnte aus der vorherigen Funktion stammen
                    function_type=function_type
                )
                
                # Trace aktualisieren
                node.complete(data)
            except Exception as e:
                error_msg = f"[EnhancedFusionEngine] Fehler bei Ausführung von {current_func}: {str(e)}"
                logger.error(error_msg)
                # Trace aktualisieren
                node.fail(e)
                
                # Trace abschließen
                trace.complete("failed")
                # Bei Fehler die Ausführung abbrechen
                return {
                    "status": "error",
                    "fusion": name,
                    "error": str(e),
                    "trace_id": trace.trace_id,
                    "execution_time": trace.duration,
                    "communication_stats": execution_stats["communication"]
                }
        
        # Trace abschließen
        trace.complete("completed")
        logger.info(f"[EnhancedFusionEngine] Ergebnis: {data}")
        
        # Abschlussstatistik
        billing_summary = self.service_model.get_billing_summary() if self.enhanced_config["enable_communication_stats"] else {}
        
        return {
            "status": "success",
            "fusion": name,
            "result": data,
            "trace_id": trace.trace_id,
            "execution_time": trace.duration,
            "communication_stats": execution_stats["communication"],
            "billing_summary": billing_summary
        }
        
    def _determine_communication_type(self, function_id: str, position: int, chain_length: int) -> str:
        """
        Ermittelt den zu verwendenden Kommunikationstyp für eine Funktion.
        
        Args:
            function_id: ID der Funktion
            position: Position in der Funktionskette
            chain_length: Gesamtlänge der Funktionskette
            
        Returns:
            Kommunikationstyp ("direct", "http", "api_gateway", "event")
        """
        # Funktion-spezifische Konfiguration hat Vorrang
        func_config = self.get_function_communication_config(function_id)
        if "communication_type" in func_config:
            return func_config["communication_type"]
        
        # Erste Funktion ist immer direkt (eintretender Aufruf)
        if position == 0:
            return "direct"
            
        # Standardeinstellung aus der globalen Konfiguration
        return self.enhanced_config["default_communication_type"]
    
    def _get_communication_params(self, function_id: str, data: Dict[str, Any], 
                                target_region: str, function_type: str) -> Dict[str, Any]:
        """
        Erzeugt Parameter für die Kommunikationssimulation.
        
        Args:
            function_id: ID der Zielfunktion
            data: Zu übertragende Daten
            target_region: Zielregion
            function_type: Funktionstyp
            
        Returns:
            Parameter für die Kommunikationssimulation
        """
        # Funktion-spezifische Konfiguration
        func_config = self.get_function_communication_config(function_id)
        
        # Basisparameter
        params = {
            "region": target_region,
            "function_type": function_type,
            "time_of_day": None  # Aktuelle Zeit verwenden
        }
        
        # Payload-Größe abschätzen
        try:
            payload_size = len(json.dumps(data)) / 1024  # KB
        except:
            payload_size = 1.0  # 1 KB als Standard
            
        params["payload_size_kb"] = payload_size
        
        # Parameter je nach Kommunikationstyp
        comm_type = self._determine_communication_type(function_id, 1, 2)  # Position ist hier nicht wichtig
        
        if comm_type == "api_gateway":
            params.update({
                "deployment_type": func_config.get("api_gateway_type", "regional"),
                "auth_type": func_config.get("auth_type", self.enhanced_config["default_auth_type"])
            })
        elif comm_type == "event":
            params.update({
                "service": func_config.get("event_service", "sqs"),
                "operation": func_config.get("event_operation", "send")
            })
        elif comm_type == "http":
            params.update({
                "use_keep_alive": func_config.get("use_keep_alive", True),
                "serialization_format": func_config.get("serialization", self.enhanced_config["default_serialization"]),
                "compression": func_config.get("compression", "none"),
                "auth_overhead_ms": 0 if func_config.get("auth_type", "none") == "none" else 10,
                "use_mtls": self.enhanced_config["enable_service_mesh"] and func_config.get("use_mtls", False),
                "tracing_enabled": func_config.get("tracing_enabled", False),
                "circuit_breaker_enabled": func_config.get("circuit_breaker_enabled", False),
                "transfer_type": "intra_region" if target_region == "us-east-1" else "inter_region"
            })
        
        return params
            
    def get_communication_stats(self) -> Dict[str, Any]:
        """
        Gibt Statistiken zur Kommunikation zurück.
        
        Returns:
            Dictionary mit Kommunikationsstatistiken
        """
        if not self.enhanced_config["enable_communication_stats"]:
            return {"stats_disabled": True}
            
        return {
            **self.enhanced_config["communication_stats"],
            "billing_summary": self.service_model.get_billing_summary()
        }
        
    def reset_communication_stats(self) -> None:
        """Setzt die Kommunikationsstatistiken zurück."""
        self.enhanced_config["communication_stats"] = {
            "total_latency": 0,
            "total_cost": 0,
            "calls_by_type": {
                "direct": 0,
                "http": 0,
                "api_gateway": 0,
                "event": 0
            }
        }
        # Service Model zurücksetzen
        self.service_model.api_requests_count = 0
        self.service_model.event_messages_count = {"sns": 0, "sqs": 0, "eventbridge": 0, "kinesis": 0}
        self.service_model.data_transferred_gb = {"intra_region": 0, "inter_region": 0, "internet": 0}

# Globale Instanz
enhanced_fusion_engine = EnhancedFusionEngine()