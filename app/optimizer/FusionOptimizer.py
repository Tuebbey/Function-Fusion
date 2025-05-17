# src/utils/FusionOptimizer.py
import os
import json
import time
import asyncio
import importlib
import inspect
import random
import math
from typing import Dict, List, Any, Set, Optional
import logging
from app.runtime import LambdaRuntime
from app.fusion import FusionEngine, FusionDefinition

logger = logging.getLogger("lambda-sim.optimizer")

class FusionOptimizer:
    """
    Optimiert Function Fusions für bessere Performance und Ressourcennutzung.
    Der FusionOptimizer analysiert Function Fusions, identifiziert Optimierungspotenziale
    und erstellt Ausführungspläne, die synchrone und asynchrone Verarbeitung kombinieren.
    """
    def __init__(self, lambda_runtime: LambdaRuntime, fusion_engine: FusionEngine):
        self.lambda_runtime = lambda_runtime
        self.fusion_engine = fusion_engine
        self.dependency_graph = {}  # Speichert Abhängigkeiten zwischen Funktionen
        self.execution_stats = {}  # Speichert Ausführungsstatistiken
        self.optimization_cache = {}  # Caching von Optimierungsergebnissen
        self.performance_model = None  # Performance-Modell für Simulationen

    def set_performance_model(self, performance_model):
        """Setzt das Performance-Modell für genauere Simulationen"""
        self.performance_model = performance_model
        
    async def analyze_dependencies(self, fusion_id: str) -> Dict[str, Set[str]]:
        """
        Analysiert Abhängigkeiten zwischen Funktionen in einer Fusion.
        Args:
            fusion_id: ID der zu analysierenden Fusion
        Returns:
            Ein Dictionary mit Funktions-IDs als Schlüssel und abhängigen Funktionen als Werte
        """
        try:
            fusion = self.fusion_engine.get_fusion(fusion_id)
            dependencies = {}
            
            # Analysiere die Funktionen in der Fusion
            for i, func_id in enumerate(fusion.function_chain):
                function = self.lambda_runtime.get_function(func_id)
                
                # Extrahiere den Funktionscode
                func_code = inspect.getsource(function.handler) if hasattr(function.handler, "__code__") else ""
                
                # Finde mögliche Abhängigkeiten zu anderen Funktionen
                dependencies[func_id] = set()
                
                # In der einfachsten Form: jede Funktion hängt von der vorherigen ab
                if i > 0:
                    dependencies[func_id].add(fusion.function_chain[i-1])
                
                # Fortgeschrittene Analyse: Suche nach Datenabhängigkeiten im Code
                # Diese Implementation ist vereinfacht und kann in realen Anwendungen erweitert werden
                for j, other_func_id in enumerate(fusion.function_chain):
                    if j == i:
                        continue  # Überspringe die Funktion selbst
                        
                    other_function = self.lambda_runtime.get_function(other_func_id)
                    
                    # Prüfe, ob die aktuelle Funktion auf Ausgaben der anderen Funktion zugreift
                    # Dies ist eine sehr einfache Heuristik und kann verbessert werden
                    if other_function.name in func_code:
                        dependencies[func_id].add(other_func_id)
            
            self.dependency_graph[fusion_id] = dependencies
            return dependencies
        except Exception as e:
            logger.error(f"Fehler bei der Abhängigkeitsanalyse: {str(e)}")
            return {}

    async def optimize_fusion(self, fusion_id: str) -> Dict[str, Any]:
        """
        Optimiert eine Function Fusion für verbesserte Performance.
        Args:
            fusion_id: ID der zu optimierenden Fusion
        Returns:
            Optimierungsergebnisse
        """
        start_time = time.time()
        result = {
            "fusion_id": fusion_id,
            "optimizations": []
        }
        
        # Prüfe, ob ein aktuelles Optimierungsergebnis im Cache liegt
        if fusion_id in self.optimization_cache:
            cached_result = self.optimization_cache[fusion_id]
            if time.time() - cached_result.get("timestamp", 0) < 300:  # 5 Minuten Cache-Gültigkeit
                logger.info(f"Verwende Cache-Ergebnis für Fusion {fusion_id}")
                return cached_result
        
        try:
            # 1. Analysiere Abhängigkeiten
            dependencies = await self.analyze_dependencies(fusion_id)
            
            # 2. Identifiziere parallele Ausführungsmöglichkeiten
            parallel_execution_groups = await self._identify_parallel_groups(fusion_id, dependencies)
            result["parallel_groups"] = parallel_execution_groups
            
            # 3. Optimiere Funktionsreihenfolge
            fusion = self.fusion_engine.get_fusion(fusion_id)
            optimized_chain = await self._optimize_function_order(fusion, dependencies)
            
            if optimized_chain != fusion.function_chain:
                result["optimizations"].append({
                    "type": "reordering",
                    "original_chain": fusion.function_chain.copy(),
                    "optimized_chain": optimized_chain
                })
            
            # 4. Analyse der Ausführungszeiten
            execution_times = await self._analyze_execution_times(fusion_id)
            result["execution_times"] = execution_times
            
            # 5. Asynchrone Optimierung
            async_optimization = await self.optimize_async_execution(fusion_id)
            result["async_optimization"] = async_optimization
            
            # 6. Speichere Optimierungskonfiguration
            config_path = os.path.join("optimizations", f"{fusion_id}.json")
            os.makedirs("optimizations", exist_ok=True)
            
            optimization_config = {
                "timestamp": time.time(),
                "fusion_id": fusion_id,
                "parallel_groups": parallel_execution_groups,
                "optimized_chain": optimized_chain,
                "execution_times": execution_times,
                "async_execution_plan": async_optimization.get("async_execution_plan", {})
            }
            
            with open(config_path, "w") as f:
                json.dump(optimization_config, f, indent=2)
                
            result["config_path"] = config_path
            result["duration"] = time.time() - start_time
            
            # Cache-Ergebnis speichern
            self.optimization_cache[fusion_id] = {
                **result,
                "timestamp": time.time()
            }
            
            return result
        except Exception as e:
            logger.error(f"Fehler bei der Optimierung: {str(e)}")
            result["error"] = str(e)
            result["duration"] = time.time() - start_time
            return result

    async def _identify_parallel_groups(self, fusion_id: str, dependencies: Dict[str, Set[str]]) -> List[List[str]]:
        """
        Identifiziert Gruppen von Funktionen, die parallel ausgeführt werden können.
        """
        fusion = self.fusion_engine.get_fusion(fusion_id)
        groups = []
        current_group = []
        
        # Einfacher Algorithmus zur Gruppierung unabhängiger Funktionen
        for i, func_id in enumerate(fusion.function_chain):
            # Wenn die aktuelle Funktion von keiner der Funktionen in der aktuellen Gruppe abhängt,
            # kann sie parallel ausgeführt werden
            can_parallelize = True
            for group_func_id in current_group:
                if group_func_id in dependencies.get(func_id, set()):
                    can_parallelize = False
                    break
            
            if can_parallelize:
                current_group.append(func_id)
            else:
                if current_group:
                    groups.append(current_group)
                current_group = [func_id]
        
        if current_group:
            groups.append(current_group)
            
        return groups

    async def _optimize_function_order(self, fusion: FusionDefinition, dependencies: Dict[str, Set[str]]) -> List[str]:
        """
        Optimiert die Reihenfolge der Funktionen basierend auf Abhängigkeiten.
        Diese Implementierung verwendet eine vereinfachte topologische Sortierung,
        um eine optimale Ausführungsreihenfolge zu finden.
        """
        # Kopie der Funktionskette erstellen
        function_chain = fusion.function_chain.copy()
        
        # Topologische Sortierung
        # 1. Finde alle Funktionen ohne Abhängigkeiten
        result = []
        no_dependencies = []
        
        # Erstelle ein Abhängigkeitsdiagramm für die topologische Sortierung
        graph = {}
        for func_id in function_chain:
            graph[func_id] = []
            
        for func_id, deps in dependencies.items():
            for dep in deps:
                if dep in function_chain:
                    graph[dep].append(func_id)
        
        # Finde Funktionen ohne eingehende Abhängigkeiten
        for func_id in function_chain:
            has_incoming = False
            for deps in dependencies.values():
                if func_id in deps:
                    has_incoming = True
                    break
            
            if not has_incoming:
                no_dependencies.append(func_id)
        
        # 2. Entferne diese Funktionen nacheinander und aktualisiere die Abhängigkeiten
        while no_dependencies:
            # Nehme eine Funktion ohne Abhängigkeiten
            func_id = no_dependencies.pop(0)
            result.append(func_id)
            
            # Entferne ausgehende Kanten
            for neighbor in graph.get(func_id, []):
                # Prüfe, ob der Nachbar keine weiteren eingehenden Kanten hat
                has_other_deps = False
                for other_id in function_chain:
                    if other_id != func_id and other_id in dependencies.get(neighbor, set()):
                        has_other_deps = True
                        break
                
                if not has_other_deps and neighbor not in result and neighbor not in no_dependencies:
                    no_dependencies.append(neighbor)
        
        # 3. Wenn nicht alle Funktionen einsortiert wurden, gibt es Zyklen
        # In diesem Fall behalten wir die ursprüngliche Reihenfolge für die verbleibenden Funktionen bei
        if len(result) < len(function_chain):
            remaining = [f for f in function_chain if f not in result]
            logger.warning(f"Zyklische Abhängigkeiten in Fusion {fusion.id} gefunden. Behalte ursprüngliche Reihenfolge für: {remaining}")
            result.extend(remaining)
            
        return result

    async def _analyze_execution_times(self, fusion_id: str) -> Dict[str, float]:
        """
        Analysiert die Ausführungszeiten der Funktionen in einer Fusion.
        Nutzt das erweiterte Performance-Modell für realistischere Schätzungen.
        """
        fusion = self.fusion_engine.get_fusion(fusion_id)
        execution_times = {}
        
        # Performance-Modell verwenden, falls verfügbar
        for func_id in fusion.function_chain:
            function = self.lambda_runtime.get_function(func_id)
            
            # Funktions-Metadaten extrahieren
            memory_mb = function.get("memory", 128)
            function_type = function.get("function_type", "cpu_intensive")
            region = function.get("region", "us-east-1")
            io_operations = function.get("io_operations", None)
            
            # Wenn Performance-Modell verfügbar, realistischere Zeiten simulieren
            if self.performance_model:
                # Basiszeit (ohne Overhead) - in einer realen Umgebung könnte 
                # dies aus historischen Daten kommen
                base_time = 0.1  # 100ms als Basis
                
                # Simuliere Ausführungszeit mit realistischem Modell
                sim_time, details = self.performance_model.simulate_execution_time(
                    base_execution_time=base_time,
                    memory_mb=memory_mb,
                    is_remote=False,  # Für reine Funktionsausführung ohne Remote-Overhead
                    function_type=function_type,
                    target_region=region,
                    io_operations=io_operations
                )
                execution_times[func_id] = sim_time
            else:
                # Fallback auf historische Daten oder Standardwerte
                execution_times[func_id] = self.execution_stats.get(func_id, 0.1)  # 100ms als Standard
                
        return execution_times

    def track_execution(self, fusion_id: str, function_id: str, duration: float):
        """
        Verfolgt die Ausführungszeit einer Funktion für zukünftige Optimierungen.
        """
        if fusion_id not in self.execution_stats:
            self.execution_stats[fusion_id] = {}
            
        if function_id not in self.execution_stats[fusion_id]:
            self.execution_stats[fusion_id][function_id] = []
            
        self.execution_stats[fusion_id][function_id].append(duration)
        
        # Berechne den gleitenden Durchschnitt
        func_stats = self.execution_stats[fusion_id][function_id]
        self.execution_stats[function_id] = sum(func_stats) / len(func_stats)

    async def optimize_async_execution(self, fusion_id: str) -> Dict[str, Any]:
        """
        Optimiert eine Fusion für asynchrone Ausführung.
        Berücksichtigt die IO-Operationen und regionale Faktoren bei der Optimierung.
        
        Args:
            fusion_id: ID der zu optimierenden Fusion
            
        Returns:
            Optimierungsergebnisse mit asynchronen Ausführungsempfehlungen
        """
        start_time = time.time()
        result = {
            "fusion_id": fusion_id,
            "async_optimizations": []
        }
        
        try:
            fusion = self.fusion_engine.get_fusion(fusion_id)
            
            # Analysiere Datenabhängigkeiten zwischen Funktionen
            dependencies = await self.analyze_dependencies(fusion_id)
            
            # Erweiterte Analyse: Berücksichtige auch I/O-Operationen und regionale Faktoren
            
            # Identifiziere Funktionen, die sich für asynchrone Ausführung eignen
            async_candidates = []
            critical_path = []
            
            for i, func_id in enumerate(fusion.function_chain):
                function = self.lambda_runtime.get_function(func_id)
                
                # Erweiterte Analyse: I/O-Operationen berücksichtigen
                function_type = function.get("function_type", "cpu_intensive") if isinstance(function, dict) else "cpu_intensive"
                io_operations = function.get("io_operations", None) if isinstance(function, dict) else None
                
                # Funktionen mit I/O-Operationen sind oft gute Kandidaten für asynchrone Ausführung
                io_intensive = function_type == "io_intensive" or (io_operations and len(io_operations) > 0)
                
                # Bestimme, ob die Funktion vom Hauptdatenfluss abhängt
                is_critical = False
                
                # Einfache Heuristik: Wenn die Funktion Daten zurückgibt, die von
                # späteren Funktionen verwendet werden, ist sie kritisch
                for j in range(i+1, len(fusion.function_chain)):
                    next_func_id = fusion.function_chain[j]
                    if func_id in dependencies.get(next_func_id, set()):
                        is_critical = True
                        break
                
                if is_critical:
                    critical_path.append(func_id)
                else:
                    # Wenn die Funktion I/O-intensiv ist, hat sie höhere Priorität für 
                    # asynchrone Ausführung
                    async_candidates.append({
                        "func_id": func_id,
                        "io_intensive": io_intensive,
                        "priority": 2 if io_intensive else 1
                    })
            
            # Sortiere Kandidaten nach Priorität
            sorted_candidates = sorted(
                async_candidates, 
                key=lambda x: x["priority"], 
                reverse=True
            )
            
            result["async_candidates"] = [c["func_id"] for c in sorted_candidates]
            result["critical_path"] = critical_path
            
            # Erstelle asynchronen Ausführungsplan
            async_execution_plan = await self._create_async_execution_plan(
                fusion, 
                result["async_candidates"], 
                critical_path, 
                dependencies
            )
            
            result["async_execution_plan"] = async_execution_plan
            result["duration"] = time.time() - start_time
            
            return result
        except Exception as e:
            logger.error(f"Fehler bei der asynchronen Optimierung: {str(e)}")
            result["error"] = str(e)
            result["duration"] = time.time() - start_time
            return result

    async def _create_async_execution_plan(self, fusion, async_candidates, critical_path, dependencies):
        """
        Erstellt einen Ausführungsplan, der asynchrone und synchrone Funktionen kombiniert.
        
        Returns:
            Ein Ausführungsplan mit Informationen darüber, welche Funktionen
            asynchron ausgeführt werden sollen und wie ihre Ergebnisse verarbeitet werden.
        """
        execution_plan = {
            "sync_functions": critical_path,
            "async_functions": async_candidates,
            "execution_order": [],
            "result_collection": {}
        }
        
        # Bestimme die Ausführungsreihenfolge
        # 1. Kritische Funktionen müssen in der vorgegebenen Reihenfolge ausgeführt werden
        # 2. Nicht-kritische Funktionen können asynchron gestartet werden, sobald ihre
        # Abhängigkeiten erfüllt sind
        all_functions = fusion.function_chain.copy()
        execution_order = []
        
        pending_async = []
        for func_id in all_functions:
            if func_id in critical_path:
                # Synchrone Ausführung
                execution_order.append({
                    "id": func_id,
                    "type": "sync",
                    "wait_for": []
                })
                
                # Prüfe, ob asynchrone Funktionen jetzt gestartet werden können
                new_pending = []
                for async_func in pending_async:
                    if all(dep in [ex["id"] for ex in execution_order] for dep in async_func["wait_for"]):
                        execution_order.append(async_func)
                    else:
                        new_pending.append(async_func)
                pending_async = new_pending
            else:
                # Asynchrone Ausführung
                # Finde Abhängigkeiten
                deps = []
                for prev_func in execution_order:
                    if prev_func["id"] in self.dependency_graph.get(fusion.id, {}).get(func_id, set()):
                        deps.append(prev_func["id"])
                
                async_func = {
                    "id": func_id,
                    "type": "async",
                    "wait_for": deps
                }
                
                # Wenn keine Abhängigkeiten oder alle Abhängigkeiten bereits ausgeführt wurden,
                # kann die Funktion sofort gestartet werden
                if not deps or all(dep in [ex["id"] for ex in execution_order] for dep in deps):
                    execution_order.append(async_func)
                else:
                    pending_async.append(async_func)
        
        # Füge alle übrigen asynchronen Funktionen hinzu
        execution_order.extend(pending_async)
        
        # Erweiterte Ausführungsreihenfolge mit regionalen und Timing-Optimierungen
        if self.performance_model:
            # Simuliere verschiedene Ausführungsreihenfolgen und wähle die schnellste
            best_order = execution_order
            best_time = float('inf')
            
            # Einfache Strategie: Versuche einige Varianten und wähle die beste
            for _ in range(3):  # Begrenze auf 3 Versuche zur Effizienz
                # Mische die asynchronen Funktionen, behalte aber synchrone in gleicher Reihenfolge
                shuffled_order = [ex for ex in execution_order if ex["type"] == "sync"]
                async_execs = [ex for ex in execution_order if ex["type"] == "async"]
                random.shuffle(async_execs)
                
                # Füge asynchrone Funktionen an geeigneten Stellen ein
                for async_ex in async_execs:
                    # Finde den frühestmöglichen Zeitpunkt nach allen Abhängigkeiten
                    min_pos = 0
                    for dep in async_ex["wait_for"]:
                        for j, ex in enumerate(shuffled_order):
                            if ex["id"] == dep:
                                min_pos = max(min_pos, j + 1)
                    
                    # Füge an zufälliger Position nach Mindestposition ein
                    insert_pos = random.randint(min_pos, len(shuffled_order))
                    shuffled_order.insert(insert_pos, async_ex)
                
                # Simuliere diese Ausführungsreihenfolge
                total_time = self._simulate_execution_order(shuffled_order)
                
                if total_time < best_time:
                    best_time = total_time
                    best_order = shuffled_order
            
            execution_order = best_order
        
        execution_plan["execution_order"] = execution_order
        
        # Bestimme, wann die Ergebnisse der asynchronen Funktionen gesammelt werden müssen
        for i, func in enumerate(execution_order):
            if func["type"] == "async":
                # Finde den frühesten Zeitpunkt, an dem das Ergebnis benötigt wird
                needed_at = None
                for j in range(i + 1, len(execution_order)):
                    next_func = execution_order[j]
                    if func["id"] in self.dependency_graph.get(fusion.id, {}).get(next_func["id"], set()):
                        needed_at = j
                        break
                
                execution_plan["result_collection"][func["id"]] = {
                    "needed_at": needed_at,
                    "collect_before": needed_at if needed_at is not None else len(execution_order)
                }
        
        return execution_plan

    def _simulate_execution_order(self, execution_order):
        """
        Simuliert die Ausführungszeit einer bestimmten Ausführungsreihenfolge.
        """
        # Sehr vereinfachte Simulation - in der Praxis würde man hier das 
        # vollständige Performance-Modell verwenden
        total_time = 0
        async_start_times = {}
        async_durations = {}
        
        for i, step in enumerate(execution_order):
            func_id = step["id"]
            func_type = step["type"]
            
            if func_type == "sync":
                # Synchrone Funktionen addieren ihre Zeit immer zum Gesamt
                func_time = 0.1  # Vereinfachte Annahme
                total_time += func_time
            else:  # async
                # Asynchrone Funktionen starten, aber blockieren nicht direkt
                async_start_times[func_id] = total_time
                async_durations[func_id] = 0.08  # Vereinfachte Annahme
                
                # Prüfe, ob wir auf Ergebnisse warten müssen
                for wait_id, wait_time in list(async_start_times.items()):
                    if i == len(execution_order) - 1 or wait_id in [next_step["wait_for"] for next_step in execution_order[i+1:]]:
                        # Diese async Funktion muss abgeschlossen sein, bevor wir weitermachen
                        finish_time = wait_time + async_durations[wait_id]
                        if finish_time > total_time:
                            total_time = finish_time
                        
                        # Entferne aus der Tracking-Liste
                        del async_start_times[wait_id]
                        del async_durations[wait_id]
        
        return total_time

    async def invoke_fusion_optimized(self, fusion_id: str, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Führt eine optimierte Function Fusion aus, die sowohl synchrone als auch asynchrone
        Aufrufe unterstützt.
        
        Args:
            fusion_id: ID der auszuführenden Fusion
            event: Eingabedaten für die Fusion
            
        Returns:
            Ergebnis der Fusion-Ausführung
        """
        fusion = self.fusion_engine.get_fusion(fusion_id)
        
        # Optimierungsplan laden oder erstellen
        optimization_result = await self.optimize_fusion(fusion_id)
        if "error" in optimization_result:
            # Fallback auf normale Ausführung
            logger.warning(f"Optimierung fehlgeschlagen, verwende normale Ausführung: {optimization_result.get('error')}")
            return await self.fusion_engine.execute(fusion_id, event, self.lambda_runtime)
        
        # Asynchronen Ausführungsplan verwenden
        async_plan = optimization_result.get("async_optimization", {})
        execution_plan = async_plan.get("async_execution_plan", {})
        
        if not execution_plan:
            # Keine asynchrone Optimierung möglich, verwende normale Ausführung
            logger.info(f"Keine asynchrone Optimierung für Fusion {fusion_id} verfügbar")
            return await self.fusion_engine.execute(fusion_id, event, self.lambda_runtime)
        
        execution_order = execution_plan.get("execution_order", [])
        current_event = event
        results = {}
        async_tasks = {}
        
        start_time = time.time()
        logger.info(f"Starting optimized Function Fusion: {fusion.name} with event: {event}")
        
        # Ausführungsplan abarbeiten
        for step_index, step in enumerate(execution_order):
            func_id = step["id"]
            execution_type = step["type"]
            function = self.lambda_runtime.get_function(func_id)
            
            # Kontext für diese Fusion-Ausführung
            context = {
                "fusion_id": fusion_id,
                "fusion_name": fusion.name,
                "execution_type": execution_type,
                "step_index": step_index,
                "total_steps": len(execution_order),
                "optimized": True
            }
            
            try:
                if execution_type == "sync":
                    # Synchrone Ausführung
                    step_start = time.time()
                    
                    # Funktionstyp und IO-Eigenschaften berücksichtigen
                    function_type = function.get("function_type", "cpu_intensive") if isinstance(function, dict) else "cpu_intensive"
                    source_region = function.get("region", "us-east-1") if isinstance(function, dict) else "us-east-1"
                    
                    # Funktion mit erweiterten Parametern aufrufen
                    result = await self.lambda_runtime.invoke(
                        func_id,
                        current_event, 
                        execution_mode="local",
                        source_region=source_region,
                        function_type=function_type
                    )
                    
                    step_duration = time.time() - step_start
                    
                    # Tracking für zukünftige Optimierungen
                    self.track_execution(fusion_id, func_id, step_duration)
                    
                    results[func_id] = {
                        "function_id": func_id,
                        "function_name": function.get("name", func_id) if isinstance(function, dict) else func_id,
                        "execution_time": step_duration,
                        "result": result
                    }
                    
                    # Ergebnis als neues Event für die nächste Funktion verwenden
                    if isinstance(result, dict):
                        current_event = result
                    else:
                        current_event = {"result": result}
                        
                elif execution_type == "async":
                    # Asynchrone Ausführung - starten, aber nicht warten
                    logger.info(f"Starting async function {func_id} in fusion {fusion.name}")
                    
                    # Funktion mit erweiterten Parametern starten
                    function_type = function.get("function_type", "cpu_intensive") if isinstance(function, dict) else "cpu_intensive"
                    source_region = function.get("region", "us-east-1") if isinstance(function, dict) else "us-east-1"
                    
                    task = asyncio.create_task(self.lambda_runtime.invoke(
                        func_id,
                        current_event.copy(),
                        execution_mode="remote",  # Remote-Ausführung für Async
                        source_region=source_region,
                        function_type=function_type
                    ))
                    
                    async_tasks[func_id] = {
                        "task": task,
                        "start_time": time.time()
                    }
                
                # Prüfen, ob Ergebnisse gesammelt werden müssen
                result_collection = execution_plan.get("result_collection", {})
                for async_id, collection_info in result_collection.items():
                    if (async_id in async_tasks and
                        collection_info.get("collect_before") == step_index):
                        # Ergebnis sammeln
                        logger.info(f"Collecting result from async function {async_id}")
                        async_task_info = async_tasks[async_id]
                        async_task = async_task_info["task"]
                        
                        try:
                            async_result = await async_task
                            step_duration = time.time() - async_task_info["start_time"]
                            
                            # Tracking für zukünftige Optimierungen
                            self.track_execution(fusion_id, async_id, step_duration)
                            
                            results[async_id] = {
                                "function_id": async_id,
                                "function_name": self.lambda_runtime.functions[async_id]["handler"].__name__ if async_id in self.lambda_runtime.functions else async_id,
                                "execution_time": step_duration,
                                "result": async_result
                            }
                            
                            # Ergebnis in den Hauptdatenfluss integrieren, falls notwendig
                            if async_id in execution_plan.get("sync_functions", []):
                                if isinstance(async_result, dict):
                                    current_event.update(async_result)
                                else:
                                    current_event[f"result_{async_id}"] = async_result
                        except Exception as async_e:
                            logger.error(f"Async function {async_id} failed: {str(async_e)}")
                            results[async_id] = {
                                "function_id": async_id,
                                "function_name": self.lambda_runtime.functions[async_id]["handler"].__name__ if async_id in self.lambda_runtime.functions else async_id,
                                "error": str(async_e)
                            }
                
            except Exception as e:
                execution_time = time.time() - start_time
                error_message = f"Optimized Fusion {fusion.name} failed at function {func_id}: {str(e)}"
                logger.error(error_message)
                
                # Alle laufenden Tasks abbrechen
                for task_info in async_tasks.values():
                    task_info["task"].cancel()
                
                # Fehler zurückgeben
                return {
                    "fusion_id": fusion_id,
                    "fusion_name": fusion.name,
                    "status": "error",
                    "error": str(e),
                    "execution_time": execution_time,
                    "results": results,
                    "failed_function": func_id,
                    "optimized": True
                }
        
        # Auf verbleibende asynchrone Tasks warten
        for func_id, task_info in async_tasks.items():
            task = task_info["task"]
            if not task.done():
                try:
                    logger.info(f"Waiting for async function {func_id} to complete")
                    async_result = await task
                    step_duration = time.time() - task_info["start_time"]
                    
                    # Tracking für zukünftige Optimierungen
                    self.track_execution(fusion_id, func_id, step_duration)
                    
                    results[func_id] = {
                        "function_id": func_id,
                        "function_name": self.lambda_runtime.functions[func_id]["handler"].__name__ if func_id in self.lambda_runtime.functions else func_id,
                        "execution_time": step_duration,
                        "result": async_result
                    }
                except Exception as e:
                    logger.warning(f"Async task {func_id} failed: {str(e)}")
                    results[func_id] = {
                        "function_id": func_id,
                        "function_name": self.lambda_runtime.functions[func_id]["handler"].__name__ if func_id in self.lambda_runtime.functions else func_id,
                        "error": str(e)
                    }
        
        execution_time = time.time() - start_time
        logger.info(f"Optimized Function Fusion {fusion.name} completed in {execution_time:.2f}s")
        
        return {
            "fusion_id": fusion_id,
            "fusion_name": fusion.name,
            "status": "success",
            "execution_time": execution_time,
            "results": results,
            "final_result": current_event,
            "optimized": True,
            "optimization_info": {
                "async_functions": len(execution_plan.get("async_functions", [])),
                "sync_functions": len(execution_plan.get("sync_functions", [])),
                "total_steps": len(execution_order)
            }
        } 