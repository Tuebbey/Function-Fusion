# app/evaluation/experiment_runner.py
import asyncio
import json
import time
import os
import random
from typing import Dict, List, Any, Optional, Callable
import logging
import itertools
import datetime

# Logger konfigurieren
logger = logging.getLogger("test-runner")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

class FusionTestRunner:
    """
    Führt automatisierte Tests für verschiedene Function Fusion Setups durch.
    Diese Klasse ermöglicht:
    - Automatische Generierung verschiedener Fusion-Konfigurationen
    - Batch-Ausführung von Tests
    - Erfassung und Analyse von Performance-Daten
    """
    def __init__(self, runtime, fusion_engine, cost_model=None, performance_model=None):
        """
        Initialisiert den TestRunner.
        Args:
            runtime: Lambda-Runtime-Instanz
            fusion_engine: Fusion-Engine-Instanz
            cost_model: Optionales Kostenmodell
            performance_model: Optionales Performance-Modell
        """
        self.runtime = runtime
        self.fusion_engine = fusion_engine
        self.cost_model = cost_model
        self.performance_model = performance_model
        self.results = {}
        
    def _generate_fusion_configurations(self,
                                       functions: List[str],
                                       strategy_space: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Generiert alle möglichen Fusion-Konfigurationen für die gegebenen Funktionen.
        Args:
            functions: Liste von Funktionsnamen
            strategy_space: Liste von möglichen Strategien (z.B. ["local", "remote"])
        Returns:
            Liste von Konfigurationen
        """
        if not strategy_space:
            strategy_space = ["local", "remote"]
            
        # Erstelle alle möglichen Kombinationen von Strategien für jede Funktion
        all_configs = []
        
        # Für n Funktionen und 2 Strategien gibt es 2^(n-1) mögliche Kombinationen
        # für die Fusionen zwischen aufeinanderfolgenden Funktionen
        n = len(functions) - 1  # Anzahl der möglichen Fusionen
        if n <= 0:
            return []
            
        # Generiere alle möglichen Kombinationen
        for strategies in itertools.product(strategy_space, repeat=n):
            config_name = "config_" + "_".join(strategies)
            
            # Erstelle die Konfiguration
            rules = {}
            for i in range(n):
                source_func = functions[i]
                target_func = functions[i+1]
                
                if source_func not in rules:
                    rules[source_func] = {}
                    
                rules[source_func][target_func] = {
                    "sync": {"strategy": strategies[i]},
                    "async": {"strategy": "remote"}  # Standard für async
                }
                
            config = {
                "name": config_name,
                "rules": rules
            }
            all_configs.append(config)
            
        return all_configs
        
    def register_fusion_configurations(self,
                                      functions: List[str],
                                      strategy_space: Optional[List[str]] = None) -> Dict[str, str]:
        """
        Registriert alle Fusion-Konfigurationen in der Fusion-Engine.
        Args:
            functions: Liste von Funktionsnamen
            strategy_space: Liste von möglichen Strategien
        Returns:
            Dictionary mit Konfigurationsnamen und Fusion-IDs
        """
        configs = self._generate_fusion_configurations(functions, strategy_space)
        fusion_ids = {}
        
        for config in configs:
            fusion_name = config["name"]
            
            # Registriere die Fusion
            try:
                fusion_id = self.fusion_engine.register_fusion(
                    fusion_name,
                    functions,
                    config
                )
                fusion_ids[fusion_name] = fusion_id
                logger.info(f"Fusion registriert: {fusion_name}")
                
            except Exception as e:
                logger.error(f"Fehler bei Registrierung von {fusion_name}: {str(e)}")
                
        return fusion_ids
        
    async def execute_test(self,
                         fusion_id: str,
                         test_event: Dict[str, Any],
                         repetitions: int = 1,
                         mode: str = "sync",
                         function_type: str = "cpu_intensive",
                         source_region: str = "us-east-1",
                         with_io: bool = False) -> Dict[str, Any]:
        """
        Führt einen einzelnen Test für eine bestimmte Fusion aus.
        
        Args:
            fusion_id: ID der zu testenden Fusion
            test_event: Testeingabe
            repetitions: Anzahl der Wiederholungen
            mode: Ausführungsmodus ("sync" oder "async")
            function_type: Funktionstyp für die Simulation
            source_region: Quellregion für die Simulation
            with_io: Ob I/O-Operationen simuliert werden sollen
            
        Returns:
            Testergebnisse
        """
        results = []
        
        for i in range(repetitions):
            logger.info(f"\n▶ Starte Test: Test {i+1}/{repetitions} für Fusion {fusion_id} "
                       f"(Modus: {mode}, Typ: {function_type}, Region: {source_region})")
            
            start_time = time.time()
            
            try:
                # I/O-Operationen simulieren, falls gewünscht
                io_operations = None
                if with_io and self.performance_model:
                    # Einfache I/O-Operationen für den Test
                    io_operations = [
                        {"operation_type": "read", "storage_type": "dynamodb", "data_size_kb": 5.0},
                        {"operation_type": "write", "storage_type": "dynamodb", "data_size_kb": 2.0}
                    ]
                    
                    # I/O-Operationen für die Test-Funktionen setzen
                    for func_name in self.fusion_engine.fusions.get(fusion_id, []):
                        if func_name in self.runtime.functions:
                            self.runtime.functions[func_name]["io_operations"] = io_operations
                            self.runtime.functions[func_name]["function_type"] = function_type
                            self.runtime.functions[func_name]["region"] = source_region
                
                if mode == "async":
                    task_info = await self.fusion_engine.execute(
                        fusion_id, test_event, self.runtime, 
                        execution_mode="async",
                        performance_model=self.performance_model
                    )
                    # Warte auf das Ergebnis
                    task_id = task_info.get("task_id")
                    await asyncio.sleep(0.1) # Kurze Pause
                    # Ergebnis abrufen
                    result = await self.fusion_engine.get_task_result(task_id)
                else:
                    result = await self.fusion_engine.execute(
                        fusion_id, test_event, self.runtime, 
                        execution_mode="sync",
                        performance_model=self.performance_model
                    )
                
                end_time = time.time()
                execution_time = end_time - start_time
                
                # Ergebnis formatieren
                trace_id = result.get("trace_id")
                trace_data = None
                if trace_id:
                    trace_data = self.fusion_engine.get_trace(trace_id)
                
                formatted_result = {
                    "status": result.get("status"),
                    "execution_time": execution_time,
                    "trace_id": trace_id,
                    "trace_data": trace_data,
                    "result": result.get("result"),
                    "error": result.get("error") if result.get("status") == "error" else None,
                    "function_type": function_type,
                    "source_region": source_region,
                    "with_io": with_io
                }
                results.append(formatted_result)
                logger.info(f" Ergebnis ({fusion_id}): {result}")
                
            except Exception as e:
                end_time = time.time()
                execution_time = end_time - start_time
                results.append({
                    "status": "error",
                    "execution_time": execution_time,
                    "error": str(e),
                    "function_type": function_type,
                    "source_region": source_region,
                    "with_io": with_io
                })
                logger.error(f" Fehler bei Test {fusion_id}: {str(e)}")
        
        # Zusammenfassung erstellen
        summary = {
            "fusion_id": fusion_id,
            "test_event": test_event,
            "repetitions": repetitions,
            "mode": mode,
            "function_type": function_type,
            "source_region": source_region,
            "with_io": with_io,
            "results": results,
            "avg_execution_time": sum(r["execution_time"] for r in results) / len(results) if results else 0,
            "success_rate": sum(1 for r in results if r["status"] == "success") / len(results) if results else 0
        }
        
        return summary
        
    async def run_batch_tests(self,
                            functions: List[str],
                            test_event: Dict[str, Any],
                            strategy_space: Optional[List[str]] = None,
                            repetitions: int = 3,
                            modes: Optional[List[str]] = None,
                            function_types: Optional[List[str]] = None,
                            regions: Optional[List[str]] = None,
                            with_io_options: Optional[List[bool]] = None) -> Dict[str, Any]:
        """
        Führt Batch-Tests für alle möglichen Fusion-Konfigurationen aus.
        
        Args:
            functions: Liste von Funktionsnamen
            test_event: Testeingabe
            strategy_space: Liste von möglichen Strategien
            repetitions: Anzahl der Wiederholungen pro Test
            modes: Liste von Testmodi ("sync", "async")
            function_types: Liste von Funktionstypen
            regions: Liste von Regionen
            with_io_options: Liste von IO-Simulationsoptionen
            
        Returns:
            Zusammenfassung aller Tests
        """
        if not modes:
            modes = ["sync"]
        
        if not function_types:
            function_types = ["cpu_intensive"]
            
        if not regions:
            regions = ["us-east-1"]
            
        if with_io_options is None:
            with_io_options = [False]
        
        # Alle Konfigurationen registrieren
        fusion_ids = self.register_fusion_configurations(functions, strategy_space)
        all_results = {}
        
        # Jeden Test für jede Konfiguration ausführen
        for fusion_name, fusion_id in fusion_ids.items():
            for mode in modes:
                for function_type in function_types:
                    for region in regions:
                        for with_io in with_io_options:
                            test_id = f"{fusion_name}_{mode}_{function_type}_{region}_io{with_io}"
                            
                            logger.info(f"\n===== Test ausführen: {test_id} =====")
                            result = await self.execute_test(
                                fusion_id,
                                test_event,
                                repetitions,
                                mode,
                                function_type,
                                region,
                                with_io
                            )
                            all_results[test_id] = result
        
        # Analyse der Ergebnisse
        analysis = self._analyze_results(all_results)
        
        # Ergebnisse speichern
        self.results = {
            "test_configurations": {
                "functions": functions,
                "strategy_space": strategy_space or ["local", "remote"],
                "repetitions": repetitions,
                "modes": modes,
                "function_types": function_types,
                "regions": regions,
                "with_io_options": with_io_options,
                "test_event": test_event
            },
            "results": all_results,
            "analysis": analysis
        }
        
        return self.results
    
    def _analyze_results(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analysiert die Testergebnisse und identifiziert die besten Konfigurationen.
        Berücksichtigt verschiedene Szenarien (Regionen, Funktionstypen, I/O).
        
        Args:
            results: Dictionary mit Testergebnissen
            
        Returns:
            Analyseergebnisse
        """
        # Gruppieren nach Funktionstyp, Region und I/O-Nutzung
        grouped_results = {}
        
        for config_name, result in results.items():
            function_type = result.get("function_type", "cpu_intensive")
            region = result.get("source_region", "us-east-1")
            with_io = result.get("with_io", False)
            mode = result.get("mode", "sync")
            
            group_key = f"{function_type}_{region}_io{with_io}_{mode}"
            
            if group_key not in grouped_results:
                grouped_results[group_key] = {}
                
            grouped_results[group_key][config_name] = result
        
        # Analyse pro Gruppe
        group_analysis = {}
        
        for group_key, group_results in grouped_results.items():
            # Finde die schnellste Konfiguration
            fastest_config = None
            fastest_time = float('inf')
            
            # Finde die zuverlässigste Konfiguration
            most_reliable_config = None
            highest_success_rate = -1
            
            # Finde die kostengünstigste Konfiguration (falls Kostenmodell verfügbar)
            cheapest_config = None
            lowest_cost = float('inf')
            
            for config_name, result in group_results.items():
                avg_time = result.get("avg_execution_time", float('inf'))
                success_rate = result.get("success_rate", 0)
                
                # Kosten berechnen, falls Kostenmodell verfügbar
                cost = float('inf')
                if self.cost_model:
                    # Vereinfachte Kostenberechnung
                    function_chain = self.fusion_engine.fusions.get(result.get("fusion_id", ""))
                    if function_chain:
                        # Basis-Parameter für Kostenberechnung
                        memory_mb = 128  # Standard
                        durations_ms = []
                        remote_invocations = []
                        
                        # Extrahiere Ausführungsdetails
                        for func_id in function_chain:
                            # Ausführungszeit und Remote-Status extrahieren
                            for r in result.get("results", []):
                                if r.get("status") == "success":
                                    trace_data = r.get("trace_data", {})
                                    nodes = trace_data.get("nodes", {})
                                    
                                    if func_id in nodes:
                                        node = nodes[func_id]
                                        durations_ms.append((node.get("duration", 0) or 0) * 1000)  # In ms umwandeln
                                        remote_invocations.append(node.get("strategy", "local") == "remote")
                        
                        # Wenn wir Details haben, berechne die Kosten
                        if durations_ms and len(durations_ms) == len(remote_invocations):
                            cost_calc = self.cost_model.calculate_fusion_cost(
                                memory_mb, durations_ms, remote_invocations
                            )
                            cost = cost_calc.get("total_billable_cost", float('inf'))
                
                # Update Bests
                if avg_time < fastest_time:
                    fastest_time = avg_time
                    fastest_config = config_name
                    
                if success_rate > highest_success_rate:
                    highest_success_rate = success_rate
                    most_reliable_config = config_name
                    
                if cost < lowest_cost:
                    lowest_cost = cost
                    cheapest_config = config_name
            
            # Gruppenergebnisse speichern
            group_analysis[group_key] = {
                "fastest_configuration": {
                    "name": fastest_config,
                    "avg_execution_time": fastest_time
                },
                "most_reliable_configuration": {
                    "name": most_reliable_config,
                    "success_rate": highest_success_rate
                },
                "cheapest_configuration": {
                    "name": cheapest_config,
                    "estimated_cost": lowest_cost if lowest_cost != float('inf') else None
                }
            }
        
        # Gesamtanalyse
        overall_fastest = None
        overall_fastest_time = float('inf')
        overall_most_reliable = None
        overall_highest_success_rate = -1
        overall_cheapest = None
        overall_lowest_cost = float('inf')
        
        for group_key, analysis in group_analysis.items():
            fastest = analysis["fastest_configuration"]
            if fastest["avg_execution_time"] < overall_fastest_time:
                overall_fastest_time = fastest["avg_execution_time"]
                overall_fastest = {
                    "name": fastest["name"],
                    "avg_execution_time": fastest["avg_execution_time"],
                    "scenario": group_key
                }
                
            reliable = analysis["most_reliable_configuration"]
            if reliable["success_rate"] > overall_highest_success_rate:
                overall_highest_success_rate = reliable["success_rate"]
                overall_most_reliable = {
                    "name": reliable["name"],
                    "success_rate": reliable["success_rate"],
                    "scenario": group_key
                }
                
            cheapest = analysis["cheapest_configuration"]
            if cheapest["estimated_cost"] is not None and cheapest["estimated_cost"] < overall_lowest_cost:
                overall_lowest_cost = cheapest["estimated_cost"]
                overall_cheapest = {
                    "name": cheapest["name"],
                    "estimated_cost": cheapest["estimated_cost"],
                    "scenario": group_key
                }
        
        # Vergleiche mit der ursprünglichen Fusionize-Heuristik
        # (synchron = lokal, asynchron = remote)
        heuristic_validation = {}
        
        for group_key, analysis in group_analysis.items():
            # Finde die Konfiguration, die den Heuristic-Regeln entspricht
            heuristic_config_name = next(
                (name for name in grouped_results[group_key].keys() if "local" in name),
                None
            )
            
            if heuristic_config_name:
                heuristic_result = grouped_results[group_key][heuristic_config_name]
                fastest_config_name = analysis["fastest_configuration"]["name"]
                fastest_result = grouped_results[group_key][fastest_config_name]
                
                heuristic_is_optimal = heuristic_config_name == fastest_config_name
                time_difference = 0
                
                if heuristic_result and fastest_result:
                    heuristic_time = heuristic_result.get("avg_execution_time", 0)
                    fastest_time = fastest_result.get("avg_execution_time", 0)
                    
                    if fastest_time > 0:
                        time_difference = ((heuristic_time - fastest_time) / fastest_time) * 100
                
                heuristic_validation[group_key] = {
                    "heuristic_config": heuristic_config_name,
                    "fastest_config": fastest_config_name,
                    "heuristic_is_optimal": heuristic_is_optimal,
                    "performance_difference_percent": time_difference
                }
        
        # Gesamtergebnis
        return {
            "overall_fastest_configuration": overall_fastest,
            "overall_most_reliable_configuration": overall_most_reliable,
            "overall_cheapest_configuration": overall_cheapest,
            "group_analysis": group_analysis,
            "heuristic_validation": heuristic_validation,
            "heuristic_success_rate": sum(1 for v in heuristic_validation.values() if v["heuristic_is_optimal"]) / len(heuristic_validation) if heuristic_validation else 0
        }
    
    def save_results(self, filename: str):
        """
        Speichert die Testergebnisse in einer JSON-Datei.
        Args:
            filename: Name der Zieldatei
        """
        if not self.results:
            logger.warning("Keine Ergebnisse zum Speichern vorhanden")
            return
            
        # Erstelle Verzeichnis, falls es nicht existiert
        os.makedirs(os.path.dirname(filename) or ".", exist_ok=True)
        
        try:
            with open(filename, 'w') as f:
                json.dump(self.results, f, indent=2)
                
            logger.info(f"Ergebnisse gespeichert in: {filename}")
        except Exception as e:
            logger.error(f"Fehler beim Speichern der Ergebnisse: {str(e)}")
            
    def load_results(self, filename: str) -> Dict[str, Any]:
        """
        Lädt Testergebnisse aus einer JSON-Datei.
        Args:
            filename: Name der Quelldatei
        Returns:
            Geladene Ergebnisse
        """
        try:
            with open(filename, 'r') as f:
                self.results = json.load(f)
                
            logger.info(f"Ergebnisse geladen aus: {filename}")
            return self.results
        except Exception as e:
            logger.error(f"Fehler beim Laden der Ergebnisse: {str(e)}")
            return {}