import json
import logging
import copy
import statistics
from typing import Dict, List, Any, Optional, Set, Tuple

logger = logging.getLogger("lambda-sim.enhanced-optimizer")

class EnhancedFusionOptimizer:
    """
    Erweiterter Function Fusion Optimizer mit zweiphasiger Optimierungsstrategie:
    1. Pfadoptimierung: Gruppiert Funktionen basierend auf synchronen/asynchronen Aufrufen
    2. Infrastrukturoptimierung: Optimiert Speicherkonfigurationen für jede Funktion
    """
    def __init__(self, lambda_runtime=None, fusion_engine=None, cost_model=None):
        """
        Initialisiert den erweiterten Optimizer.
        Args:
            lambda_runtime: Die Lambda-Runtime-Instanz (optional)
            fusion_engine: Die Fusion-Engine-Instanz (optional)
            cost_model: Das Kostenmodell für die Optimierung (optional)
        """
        self.lambda_runtime = lambda_runtime
        self.fusion_engine = fusion_engine
        self.cost_model = cost_model
        self.test_results = {}
        self.optimization_phases = {
            "path": {"completed": False, "result": None},
            "infrastructure": {"completed": False, "result": None}
        }
        # Verfügbare Speicherkonfigurationen für die Infrastrukturoptimierung
        self.memory_configurations = [128, 256, 512, 1024, 1536, 2048, 3008, 4096, 6144]
        # Gewichtungsfaktoren für die Optimierungsziele
        self.optimization_weights = {
            "latency": 0.7,  # Gewichtung für Latenz
            "cost": 0.3  # Gewichtung für Kosten
        }

    def set_test_results(self, results: Dict[str, List[Dict]]):
        """
        Setzt die Testergebnisse für die Optimierung.
        Args:
            results: Dictionary mit Setups und ihren Ausführungsdaten
        """
        self.test_results = results
        # Zurücksetzen des Optimierungsstatus
        self.optimization_phases = {
            "path": {"completed": False, "result": None},
            "infrastructure": {"completed": False, "result": None}
        }

    def set_optimization_weights(self, latency_weight: float, cost_weight: float):
        """
        Setzt die Gewichtungsfaktoren für die Optimierungsziele.
        Args:
            latency_weight: Gewichtungsfaktor für Latenz (0-1)
            cost_weight: Gewichtungsfaktor für Kosten (0-1)
        """
        total = latency_weight + cost_weight
        self.optimization_weights = {
            "latency": latency_weight / total,
            "cost": cost_weight / total
        }
        logger.info(f"Optimierungsgewichte gesetzt: Latenz={self.optimization_weights['latency']:.2f}, Kosten={self.optimization_weights['cost']:.2f}")

    def get_lowest_latency_configuration(self) -> str:
        """
        Findet die Konfiguration mit der niedrigsten Latenz.
        Returns:
            Key des Setups mit der niedrigsten mittleren Latenz
        """
        medians = {}
        
        for key in self.test_results.keys():
            durations = [inv["billedDuration"] for inv in self.test_results[key]]
            if durations:
                medians[key] = statistics.median(durations)
                
        min_key = ""
        min_value = float('inf')
        for key in medians:
            if medians[key] < min_value:
                min_key = key
                min_value = medians[key]
                
        return min_key

    def get_lowest_cost_configuration(self) -> str:
        """
        Findet die Konfiguration mit den niedrigsten Kosten.
        Nutzt das Kostenmodell, falls verfügbar.
        Returns:
            Key des Setups mit den niedrigsten Kosten
        """
        if not self.cost_model:
            logger.warning("Kein Kostenmodell verfügbar, fallback auf Latenz-basierte Optimierung")
            return self.get_lowest_latency_configuration()
            
        costs = {}
        for key in self.test_results.keys():
            setup_costs = []
            for inv in self.test_results[key]:
                # Extrahiere relevante Informationen für die Kostenberechnung
                memory_mb = inv.get("maxMemoryUsed", 128)
                duration_ms = inv.get("billedDuration", 0)
                # Berechne die Kosten für diese Ausführung
                execution_cost = self.cost_model.calculate_execution_cost(
                    memory_mb=memory_mb,
                    duration_ms=duration_ms
                )
                setup_costs.append(execution_cost)
                
            if setup_costs:
                costs[key] = statistics.mean(setup_costs)
                
        # Finde das Setup mit den niedrigsten Kosten
        min_key = ""
        min_value = float('inf')
        for key, cost in costs.items():
            if cost < min_value:
                min_key = key
                min_value = cost
                
        return min_key

    def get_optimal_configuration(self) -> str:
        """
        Findet die optimale Konfiguration basierend auf den gewichteten Faktoren
        Latenz und Kosten.
        Returns:
            Key des optimalen Setups
        """
        # Wenn keine Ergebnisse vorhanden sind, leeren String zurückgeben
        if not self.test_results:
            return ""
            
        # Wenn das Kostenmodell fehlt, optimiere nur für Latenz
        if not self.cost_model:
            return self.get_lowest_latency_configuration()
            
        # Berechne normalisierte Scores für Latenz und Kosten
        latency_scores = {}
        cost_scores = {}
        
        # Latenz-Scores berechnen
        durations = {}
        for key in self.test_results.keys():
            durations[key] = statistics.median([inv["billedDuration"] for inv in self.test_results[key]])
            
        max_duration = max(durations.values()) if durations else 1
        for key, duration in durations.items():
            # Normalisierte Latenz: Niedrigere Werte sind besser
            latency_scores[key] = 1 - (duration / max_duration)
            
        # Kosten-Scores berechnen
        costs = {}
        for key in self.test_results.keys():
            setup_costs = []
            for inv in self.test_results[key]:
                memory_mb = inv.get("maxMemoryUsed", 128)
                duration_ms = inv.get("billedDuration", 0)
                execution_cost = self.cost_model.calculate_execution_cost(
                    memory_mb=memory_mb,
                    duration_ms=duration_ms
                )
                setup_costs.append(execution_cost)
                
            costs[key] = statistics.mean(setup_costs) if setup_costs else float('inf')
            
        max_cost = max(costs.values()) if costs else 1
        for key, cost in costs.items():
            # Normalisierte Kosten: Niedrigere Werte sind besser
            cost_scores[key] = 1 - (cost / max_cost)
            
        # Kombinierte gewichtete Scores berechnen
        combined_scores = {}
        for key in self.test_results.keys():
            latency_score = latency_scores.get(key, 0)
            cost_score = cost_scores.get(key, 0)
            combined_scores[key] = (
                self.optimization_weights["latency"] * latency_score +
                self.optimization_weights["cost"] * cost_score
            )
            
        # Setup mit dem höchsten Score finden
        optimal_key = max(combined_scores.items(), key=lambda x: x[1])[0] if combined_scores else ""
        
        return optimal_key

    def analyze_call_patterns(self) -> Dict[str, Dict[str, bool]]:
        """
        Analysiert die Aufrufmuster aus den Testergebnissen.
        Returns:
            Dictionary mit Aufrufmustern zwischen Funktionen
        """
        call_patterns = {}
        
        # Analysiere jedes Testergebnis
        for setup, invocations in self.test_results.items():
            for invocation in invocations:
                # Extrahiere die Aufrufinformationen
                calls = invocation.get("calls", [])
                for call in calls:
                    caller = call.get("caller")
                    called = call.get("called")
                    is_sync = call.get("sync", False)
                    
                    # Ignoriere Selbstaufrufe
                    if caller == called:
                        continue
                        
                    # Initialisiere den Eintrag, falls nicht vorhanden
                    if caller not in call_patterns:
                        call_patterns[caller] = {}
                        
                    # Speichere den Aufrufstyp (synchron/asynchron)
                    call_patterns[caller][called] = is_sync
                    
        return call_patterns

    def path_optimize(self, call_patterns: Dict[str, Dict[str, bool]]) -> List[List[str]]:
        """
        Führt die Pfadoptimierung basierend auf den Aufrufmustern durch.
        Synchrone Aufrufe werden in eine Gruppe zusammengefasst,
        asynchrone Aufrufe in separaten Gruppen platziert.
        Args:
            call_patterns: Aufrufmuster zwischen Funktionen
        Returns:
            Liste von Funktionsgruppen
        """
        # Initialisiere Dictionary für Gruppen
        function_groups = {}
        
        # Initialisiere jede Funktion in einer eigenen Gruppe
        all_functions = set()
        for caller, callees in call_patterns.items():
            if caller:  # Stelle sicher, dass caller nicht None oder leer ist
                all_functions.add(caller)
                all_functions.update(callees.keys())
        
        # Entferne None oder leere Strings aus der Menge aller Funktionen
        all_functions = {func for func in all_functions if func}
        
        for func in all_functions:
            function_groups[func] = [func]
        
        # Iteriere über die Aufrufmuster und gruppiere synchrone Aufrufe
        for caller, callees in call_patterns.items():
            if not caller:  # Überspringe, wenn caller None oder leer ist
                continue
                
            for callee, is_sync in callees.items():
                if not callee:  # Überspringe, wenn callee None oder leer ist
                    continue
                    
                if is_sync:
                    # Synchonen Aufruf gruppieren
                    caller_group = None
                    callee_group = None
                    
                    # Finde die Gruppen von Aufrufer und Aufgerufenen
                    for group_key, group in function_groups.items():
                        if caller in group:
                            caller_group = group_key
                        if callee in group:
                            callee_group = group_key
                    
                    # Wenn sie bereits in derselben Gruppe sind, nichts tun
                    if caller_group == callee_group:
                        continue
                    
                    # Füge die Gruppen zusammen
                    if caller_group and callee_group:
                        merged_group = function_groups[caller_group] + function_groups[callee_group]
                        new_group_key = min(caller_group, callee_group)
                        function_groups[new_group_key] = merged_group
                        
                        # Lösche die alte Gruppe
                        old_group_key = max(caller_group, callee_group)
                        del function_groups[old_group_key]
        
        # Konvertiere das Dictionary in eine Liste von Gruppen
        result_groups = list(function_groups.values())
        
        # Entferne Duplikate innerhalb der Gruppen
        for i, group in enumerate(result_groups):
            result_groups[i] = list(set(group))
        
        # Prüfe auf leere Gruppen und entferne sie
        result_groups = [group for group in result_groups if group]
        
        return result_groups

    def infrastructure_optimize(self, path_groups: List[List[str]]) -> Dict[str, int]:
        """
        Führt die Infrastrukturoptimierung durch.
        Für jede Funktionsgruppe wird die optimale Speicherkonfiguration ermittelt.
        Args:
            path_groups: Funktionsgruppen aus der Pfadoptimierung
        Returns:
            Dictionary mit Funktionsgruppen und ihren optimalen Speicherkonfigurationen
        """
        if not self.test_results or not self.lambda_runtime:
            logger.warning("Keine Testergebnisse oder Lambda-Runtime verfügbar für Infrastrukturoptimierung")
            return {}

        memory_optimizations = {}
        # Für jede Funktionsgruppe
        for group in path_groups:
            # Filtere None-Werte und leere Strings aus der Gruppe
            valid_group = [func_id for func_id in group if func_id]
            
            # Überspringe leere Gruppen
            if not valid_group:
                logger.warning(f"Leere oder ungültige Gruppe übersprungen: {group}")
                continue
                
            group_key = ".".join(sorted(valid_group))
            best_memory = 128  # Standardwert
            best_score = -float('inf')

            # Teste verschiedene Speicherkonfigurationen
            for memory_size in self.memory_configurations:
                # Berechne den Score für diese Konfiguration
                score = self._evaluate_memory_configuration(valid_group, memory_size)
                if score > best_score:
                    best_score = score
                    best_memory = memory_size

            # Speichere die beste Konfiguration
            memory_optimizations[group_key] = best_memory
            logger.info(f"Optimale Speicherkonfiguration für Gruppe {group_key}: {best_memory}MB (Score: {best_score:.4f})")

        return memory_optimizations

    def _evaluate_memory_configuration(self, function_group: List[str], memory_size: int) -> float:
        """
        Bewertet eine Speicherkonfiguration für eine Funktionsgruppe.
        Args:
            function_group: Liste von Funktionsnamen
            memory_size: Speichergröße in MB
        Returns:
            Score für die Konfiguration (höher ist besser)
        """
        if not self.cost_model:
            # Bei fehlendem Kostenmodell einfache Heuristik verwenden
            # Bevorzuge mittlere Speichergrößen (Balance aus Leistung und Kosten)
            memory_efficiency = 1.0 - abs((memory_size - 1024) / 6144)
            return memory_efficiency
            
        # Erwartete durchschnittliche Ausführungszeit mit diesem Speicher berechnen
        estimated_duration = 0
        for func_name in function_group:
            if func_name in self.lambda_runtime.functions:
                # Basisausführungszeit extrahieren oder schätzen
                base_time = 0.1  # Standardwert in Sekunden
                func_type = self.lambda_runtime.functions[func_name].get("function_type", "cpu_intensive")
                
                # Ausführungszeit mit diesem Speicher simulieren
                if hasattr(self.lambda_runtime, "performance_model"):
                    simulated_time = self.lambda_runtime.performance_model.simulate_execution_time(
                        base_time, memory_size, func_type
                    )
                    estimated_duration += simulated_time * 1000  # in ms umrechnen
                    
        # Geschätzte Kosten berechnen
        estimated_cost = self.cost_model.calculate_execution_cost(
            memory_mb=memory_size,
            duration_ms=estimated_duration
        )
        
        # Normalisierte Werte berechnen (niedrigere Werte sind besser)
        # Wir nehmen an, dass die höchste Speicherkonfiguration die schnellste ist
        max_memory = max(self.memory_configurations)
        speed_factor = memory_size / max_memory  # Höherer Speicher = höhere Geschwindigkeit
        
        # Wir nehmen an, dass die niedrigste Speicherkonfiguration die billigste ist
        min_memory = min(self.memory_configurations)
        cost_factor = min_memory / memory_size  # Niedrigerer Speicher = niedrigere Kosten
        
        # Gewichteter Score berechnen
        score = (
            self.optimization_weights["latency"] * speed_factor +
            self.optimization_weights["cost"] * cost_factor
        )
        
        return score

    def optimize(self, null_if_already_tested: bool = False) -> Tuple[List[List[str]], Dict[str, int]]:
        """
        Führt beide Optimierungsphasen durch:
        1. Pfadoptimierung
        2. Infrastrukturoptimierung
        Args:
            null_if_already_tested: Wenn True, gibt None zurück, wenn das Setup bereits getestet wurde
        Returns:
            Tuple mit (optimierten Funktionsgruppen, optimierten Speicherkonfigurationen)
        """
        # Phase 1: Pfadoptimierung
        logger.info("Starte Pfadoptimierung...")
        call_patterns = self.analyze_call_patterns()
        path_groups = self.path_optimize(call_patterns)
        
        # Überprüfe, ob path_groups gültige Ergebnisse enthält
        if not path_groups:
            logger.warning("Pfadoptimierung hat keine gültigen Gruppen ergeben.")
            # Erstelle eine Standard-Gruppe mit allen Funktionen, um Fehler zu vermeiden
            all_functions = set()
            for setup in self.test_results.keys():
                for invocation in self.test_results[setup]:
                    for call in invocation.get("calls", []):
                        caller = call.get("caller")
                        called = call.get("called")
                        if caller:
                            all_functions.add(caller)
                        if called:
                            all_functions.add(called)
            
            # Verwende alle gefundenen Funktionen als eine Gruppe, wenn keine optimierten Gruppen gefunden wurden
            if all_functions:
                path_groups = [list(all_functions)]
                logger.info(f"Standard-Gruppe erstellt mit allen Funktionen: {path_groups}")
            else:
                logger.error("Keine Funktionen gefunden. Optimierung nicht möglich.")
                return [], {}
        
        logger.info(f"Pfadoptimierung abgeschlossen. Optimierte Gruppen: {path_groups}")
        self.optimization_phases["path"]["completed"] = True
        self.optimization_phases["path"]["result"] = path_groups
        
        # Phase 2: Infrastrukturoptimierung
        logger.info("Starte Infrastrukturoptimierung...")
        memory_configs = self.infrastructure_optimize(path_groups)
        logger.info(f"Infrastrukturoptimierung abgeschlossen. Speicherkonfigurationen: {memory_configs}")
        self.optimization_phases["infrastructure"]["completed"] = True
        self.optimization_phases["infrastructure"]["result"] = memory_configs
        
        return path_groups, memory_configs

    def get_configuration_as_list(self, setup: str) -> List[List[str]]:
        """
        Konvertiert einen Setup-String in eine Liste von Fusion-Gruppen.
        Args:
            setup: Setup-String (z.B. "A.B,C,D")
        Returns:
            Liste von Fusion-Gruppen (z.B. [["A", "B"], ["C"], ["D"]])
        """
        return [group.split(".") for group in setup.split(",")]

    def get_setup_string(self, groups: List[List[str]]) -> str:
        """
        Konvertiert eine Liste von Fusion-Gruppen in einen Setup-String.
        Args:
            groups: Liste von Fusion-Gruppen
        Returns:
            Setup-String
        """
        return ",".join(".".join(sorted(group)) for group in groups)

    def save_optimization_results(self, filename: str) -> None:
        """
        Speichert die Optimierungsergebnisse in einer JSON-Datei.
        Args:
            filename: Dateiname
        """
        if not (self.optimization_phases["path"]["completed"] and self.optimization_phases["infrastructure"]["completed"]):
            logger.warning("Keine vollständigen Optimierungsergebnisse zum Speichern vorhanden")
            return
            
        results = {
            "path_groups": self.optimization_phases["path"]["result"],
            "memory_configurations": self.optimization_phases["infrastructure"]["result"],
            "optimization_weights": self.optimization_weights,
            "setup_string": self.get_setup_string(self.optimization_phases["path"]["result"])
        }
        
        try:
            with open(filename, 'w') as f:
                json.dump(results, f, indent=2)
            logger.info(f"Optimierungsergebnisse gespeichert in: {filename}")
        except Exception as e:
            logger.error(f"Fehler beim Speichern der Optimierungsergebnisse: {str(e)}")

    def load_optimization_results(self, filename: str) -> Dict[str, Any]:
        """
        Lädt Optimierungsergebnisse aus einer JSON-Datei.
        Args:
            filename: Dateiname
        Returns:
            Geladene Optimierungsergebnisse
        """
        try:
            with open(filename, 'r') as f:
                results = json.load(f)
                
            self.optimization_phases["path"]["completed"] = True
            self.optimization_phases["path"]["result"] = results.get("path_groups", [])
            self.optimization_phases["infrastructure"]["completed"] = True
            self.optimization_phases["infrastructure"]["result"] = results.get("memory_configurations", {})
            self.optimization_weights = results.get("optimization_weights", self.optimization_weights)
            
            logger.info(f"Optimierungsergebnisse geladen aus: {filename}")
            return results
        except Exception as e:
            logger.error(f"Fehler beim Laden der Optimierungsergebnisse: {str(e)}")
            return {}