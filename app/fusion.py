# app/fusion.py
import asyncio
import time
import json
import uuid
from typing import Dict, List, Any, Optional, Callable, Tuple
from app.performance.model import PerformanceModel
from app.network.model import NetworkModel

class FusionStrategy:
    """Strategie-Konfiguration für eine Function Fusion"""
    def __init__(self, strategy_data: Dict[str, Any]):
        self.strategy = strategy_data.get("strategy", "local")
        self.url = strategy_data.get("url", None)
        self.retry_count = strategy_data.get("retry", 0)
        
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiert die Strategie in ein Dictionary"""
        return {
            "strategy": self.strategy,
            "url": self.url,
            "retry": self.retry_count
        }

class FunctionRule:
    """Konfiguration für eine Funktion innerhalb einer Fusion"""
    def __init__(self, rule_data: Dict[str, Any]):
        self.sync = FusionStrategy(rule_data.get("sync", {"strategy": "local"}))
        self.async_ = FusionStrategy(rule_data.get("async", {"strategy": "local"}))
        
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiert die Regel in ein Dictionary"""
        return {
            "sync": self.sync.to_dict(),
            "async": self.async_.to_dict()
        }

class FusionConfiguration:
    """Konfiguration für eine gesamte Fusion"""
    def __init__(self, name: str, config_data: Dict[str, Any] = None):
        self.name = name
        self.rules = {}
        self.memory_size = 128  # Standard-Speichergröße
        self.timeout = 3  # Standard-Timeout
        
        if config_data:
            self.memory_size = config_data.get("memory_size", self.memory_size)
            self.timeout = config_data.get("timeout", self.timeout)
            
            for source_func, targets in config_data.get("rules", {}).items():
                self.rules[source_func] = {}
                for target_func, rule_data in targets.items():
                    self.rules[source_func][target_func] = FunctionRule(rule_data)
                    
    def get_rule(self, source_func: str, target_func: str) -> FunctionRule:
        """Gibt die Regel für eine bestimmte Funktionskombination zurück"""
        if source_func not in self.rules or target_func not in self.rules.get(source_func, {}):
            # Standard-Regel zurückgeben, wenn keine spezifische existiert
            return FunctionRule({"sync": {"strategy": "local"}, "async": {"strategy": "local"}})
        
        return self.rules[source_func][target_func]

class ExecutionTraceNode:
    """Repräsentiert einen Knoten im Ausführungsgraphen"""
    def __init__(self, function_id: str, trace_id: str = None, parent_id: str = None):
        self.function_id = function_id
        self.trace_id = trace_id or str(uuid.uuid4())
        self.parent_id = parent_id
        self.start_time = None
        self.end_time = None
        self.duration = None
        self.status = "pending"  # pending, running, completed, failed
        self.result = None
        self.error = None
        self.strategy = "local"  # local oder remote
        self.mode = "sync"  # sync oder async
        
    def start(self, strategy: str = "local", mode: str = "sync"):
        """Markiert den Knoten als gestartet"""
        self.start_time = time.time()
        self.status = "running"
        self.strategy = strategy
        self.mode = mode
        return self
        
    def complete(self, result: Any):
        """Markiert den Knoten als erfolgreich abgeschlossen"""
        self.end_time = time.time()
        self.duration = self.end_time - self.start_time
        self.status = "completed"
        self.result = result
        return self
        
    def fail(self, error: Exception):
        """Markiert den Knoten als fehlgeschlagen"""
        self.end_time = time.time()
        self.duration = self.end_time - self.start_time
        self.status = "failed"
        self.error = str(error)
        return self
        
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiert den Knoten in ein Dictionary"""
        return {
            "function_id": self.function_id,
            "trace_id": self.trace_id,
            "parent_id": self.parent_id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration": self.duration,
            "status": self.status,
            "strategy": self.strategy,
            "mode": self.mode,
            "error": self.error
        }

class ExecutionTrace:
    """Verfolgt die Ausführung einer Function Fusion"""
    def __init__(self, fusion_id: str):
        self.fusion_id = fusion_id
        self.trace_id = str(uuid.uuid4())
        self.start_time = time.time()
        self.end_time = None
        self.duration = None
        self.nodes = {}  # function_id -> ExecutionTraceNode
        self.status = "running"  # running, completed, failed
        
    def add_node(self, function_id: str, parent_id: str = None) -> ExecutionTraceNode:
        """Fügt einen neuen Knoten zur Trace hinzu"""
        node = ExecutionTraceNode(function_id, self.trace_id, parent_id)
        self.nodes[function_id] = node
        return node
        
    def complete(self, status: str = "completed"):
        """Markiert die Trace als abgeschlossen"""
        self.end_time = time.time()
        self.duration = self.end_time - self.start_time
        self.status = status
        return self
        
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiert die Trace in ein Dictionary"""
        return {
            "fusion_id": self.fusion_id,
            "trace_id": self.trace_id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration": self.duration,
            "status": self.status,
            "nodes": {func_id: node.to_dict() for func_id, node in self.nodes.items()}
        }

class FusionEngine:
    def __init__(self):
        # Registry: Fusion-Name → Funktionskette
        self.fusions = {}
        # Konfigurationen: Fusion-Name → Konfiguration
        self.configurations = {}
        # Execution Traces: trace_id → ExecutionTrace
        self.traces = {}
        # Ausführungsoptionen
        self.config = {
            "remote_delay": 0.05,  # Zusätzliche Verzögerung für Remote-Ausführung
            "log_traces": True,    # Traces protokollieren
            "support_dag": False,   # Unterstützung für DAG (noch nicht implementiert)
            "memory_performance_factor": 0.5  # Faktor für Memory-Size Performance-Simulation
        }
        
    def register_fusion(self, name: str, function_chain: list, config: Dict[str, Any] = None):
        """
        Registriert eine neue Fusion.
        
        name: Name der Fusion
        function_chain: Liste von Funktionsnamen als Strings
        config: Optionale Konfiguration für die Fusion
        """
        self.fusions[name] = function_chain
        
        # Konfiguration erstellen oder vorhandene verwenden
        if config:
            self.configurations[name] = FusionConfiguration(name, config)
        else:
            self.configurations[name] = FusionConfiguration(name)
            
        print(f"[FusionEngine] Neue Fusion registriert: {name} -> {function_chain}")
        return name
        
    def load_configuration_from_file(self, file_path: str):
        """Lädt eine Fusion-Konfiguration aus einer JSON-Datei"""
        try:
            with open(file_path, 'r') as f:
                config_data = json.load(f)
                
            # Iteriere durch alle Konfigurationen
            for timestamp, trace_config in config_data.items():
                trace_name = trace_config.get("traceName", timestamp)
                
                # Iteriere durch alle Regeln
                for source_func, rules in trace_config.get("rules", {}).items():
                    # Wenn die Fusion bereits existiert
                    for fusion_name, function_chain in self.fusions.items():
                        if source_func in function_chain:
                            if fusion_name not in self.configurations:
                                self.configurations[fusion_name] = FusionConfiguration(fusion_name)
                                
                            # Regeln zur Konfiguration hinzufügen
                            self.configurations[fusion_name].rules[source_func] = {}
                            for target_func, rule_data in rules.items():
                                self.configurations[fusion_name].rules[source_func][target_func] = FunctionRule(rule_data)
                                
            print(f"[FusionEngine] Konfiguration aus {file_path} geladen")
        except Exception as e:
            print(f"[FusionEngine] Fehler beim Laden der Konfiguration: {str(e)}")

                    # Performance- und Netzwerkmodelle
        self.performance_model = PerformanceModel()
        self.network_model = NetworkModel()
            
    async def execute(self, name: str, event: dict, runtime, trace_id: str = None,
                    execution_mode: str = "sync", performance_model=None, network_model=None):
        """
        Führt eine registrierte Fusion aus.
        Berücksichtigt die Ausführungsstrategie (lokal/remote) und den Ausführungsmodus (sync/async).
        
        Args:
            name: Name der Fusion
            event: Eingabedaten für die Fusion
            runtime: Lambda-Runtime zur Ausführung der Funktionen
            trace_id: Optionale Trace-ID für Protokollierung
            execution_mode: 'sync' oder 'async'
            performance_model: Optionales Performance-Modell
            network_model: Optionales Netzwerk-Modell
            
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
        # # Das Performance-Modell in der Runtime registrieren, falls vorhanden
        # if performance_model and not hasattr(runtime, "performance_model"):
        #     runtime.performance_model = performance_model
        
        # Trace erstellen
        trace = ExecutionTrace(name)
        if trace_id:
            trace.trace_id = trace_id
        self.traces[trace.trace_id] = trace
        
        print(f"[FusionEngine] Starte Fusion: {name} (Trace-ID: {trace.trace_id}, Modus: {execution_mode})")
        
        # Asynchrone Ausführung
        if execution_mode == "async":
            # Task erstellen und zurückgeben
            task = asyncio.create_task(
                self._execute_fusion(name, event, runtime, trace, performance_model)
            )
            # Task-ID zurückgeben (hier ist es die trace_id)
            return {"task_id": trace.trace_id}
        
        # Synchrone Ausführung
        return await self._execute_fusion(name, event, runtime, trace, performance_model)
        
    async def _execute_fusion(self, name: str, event: dict, runtime, trace: ExecutionTrace, 
                             performance_model=None):
        """Interne Methode zur Ausführung einer Fusion"""
        data = event
        function_chain = self.fusions[name]
        config = self.configurations.get(name, FusionConfiguration(name))
        
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
            
            print(f"[FusionEngine] → Schritt {i+1}/{len(function_chain)}: {current_func} " +
                 f"(Strategie: {strategy}, Typ: {function_type}) mit Input: {data}")
            
            # Funktion ausführen mit der richtigen Strategie
            try:
                # Trace aktualisieren
                node.start(strategy, "sync")
                
                # Function-spezifische I/O-Operationen bestimmen
                io_operations = None
                if current_func in runtime.functions and "io_operations" in runtime.functions[current_func]:
                    io_operations = runtime.functions[current_func]["io_operations"]
                
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
                error_msg = f"[FusionEngine] Fehler bei Ausführung von {current_func}: {str(e)}"
                print(error_msg)
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
                    "execution_time": trace.duration
                }
        
        # Trace abschließen
        trace.complete("completed")
        print(f"[FusionEngine] Ergebnis: {data}")
        return {
            "status": "success",
            "fusion": name,
            "result": data,
            "trace_id": trace.trace_id,
            "execution_time": trace.duration
        }
        
    async def get_task_result(self, task_id: str) -> Dict[str, Any]:
        """
        Holt das Ergebnis einer asynchronen Fusion-Ausführung.
        
        Args:
            task_id: ID der Task (entspricht der Trace-ID)
            
        Returns:
            Ergebnis der Fusion-Ausführung oder Status-Information
        """
        if task_id not in self.traces:
            return {"status": "unknown", "error": f"Task mit ID {task_id} nicht gefunden"}
            
        trace = self.traces[task_id]
        
        if trace.status == "running":
            return {
                "status": "running",
                "fusion": trace.fusion_id,
                "trace_id": trace.trace_id,
                "start_time": trace.start_time,
                "elapsed_time": time.time() - trace.start_time
            }
            
        # Ergebnis der letzten Funktion holen
        last_function = None
        for node in trace.nodes.values():
            if node.status == "completed" and (not last_function or node.end_time > trace.nodes[last_function].end_time):
                last_function = node.function_id
                
        if last_function and trace.nodes[last_function].status == "completed":
            result = trace.nodes[last_function].result
        else:
            result = None
            
        return {
            "status": trace.status,
            "fusion": trace.fusion_id,
            "result": result,
            "trace_id": trace.trace_id,
            "execution_time": trace.duration,
            "error": next((node.error for node in trace.nodes.values() if node.error), None)
        }
        
    def get_trace(self, trace_id: str) -> Dict[str, Any]:
        """
        Gibt Trace-Informationen für eine bestimmte Trace-ID zurück.
        
        Args:
            trace_id: ID der Trace
            
        Returns:
            Trace-Informationen als Dictionary
        """
        if trace_id not in self.traces:
            return {"status": "unknown", "error": f"Trace mit ID {trace_id} nicht gefunden"}
            
        return self.traces[trace_id].to_dict()

# Globale Instanz verfügbar machen
fusion_engine = FusionEngine()