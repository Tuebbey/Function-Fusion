# fusion_optimizer.py
import asyncio
import json
import time
import random
import itertools
import os
import multiprocessing
import numpy as np
import httpx
from typing import Dict, List, Any, Tuple, Set, Optional
from tqdm import tqdm
from tqdm.asyncio import tqdm_asyncio

class FunctionSignature:
    """Repräsentiert die Signatur einer Funktion mit Ein- und Ausgabetypen."""
    def __init__(self, name: str):
        self.name = name
        self.input_schema = {"type": "object"}
        self.output_schema = {"type": "object"}
        self.description = ""
        
    def __str__(self):
        return f"{self.name}: {self.input_schema['type']} -> {self.output_schema['type']}"


class FusionDiscovery:
    """Entdeckt kompatible Funktionen für Fusionen basierend auf Signatur-Analyse."""
    def __init__(self, runtime=None):
        self.runtime = runtime
        self.function_signatures = {}
        
    async def discover_all_function_signatures(self, functions=None):
        """Entdeckt die Signatur (Ein-/Ausgabe) aller angegebenen Funktionen."""
        if functions is None and self.runtime:
            functions = list(self.runtime.functions.keys())
        elif functions is None:
            functions = []
            
        for func_name in functions:
            await self.discover_function_signature(func_name)
            
    async def discover_function_signature(self, func_name):
        """
        Entdeckt die Signatur einer Funktion durch Testaufrufe oder Metadaten-Analyse.
        
        Dies würde in der Praxis durch Analyse von OpenAPI-Spezifikationen,
        JSON-Schema-Definitionen oder automatisierten Tests erfolgen.
        """
        # Beispiel-Implementierung basierend auf Testaufrufen oder Metadaten
        test_input = {"test": True}
        
        try:
            # Testaufruf, um die Ausgabe zu analysieren, falls Runtime verfügbar
            if self.runtime:
                test_output = await self.runtime.invoke(func_name, test_input)
                self.function_signatures[func_name] = {
                    "input_schema": self._infer_schema(test_input),
                    "output_schema": self._infer_schema(test_output)
                }
            else:
                # Statischer Fallback ohne Runtime
                self.function_signatures[func_name] = {
                    "input_schema": {"type": "object"},
                    "output_schema": {"type": "object"}
                }
            
        except Exception as e:
            print(f"Fehler bei der Analyse von {func_name}: {e}")
            # Fallback-Signatur
            self.function_signatures[func_name] = {
                "input_schema": {"type": "object"},
                "output_schema": {"type": "object"}
            }
            
    def _infer_schema(self, data):
        """Leitet ein JSON-Schema aus Beispieldaten ab."""
        schema = {"type": "object", "properties": {}}
        
        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, str):
                    schema["properties"][key] = {"type": "string"}
                elif isinstance(value, (int, float)):
                    schema["properties"][key] = {"type": "number"}
                elif isinstance(value, bool):
                    schema["properties"][key] = {"type": "boolean"}
                elif isinstance(value, list):
                    schema["properties"][key] = {"type": "array"}
                elif isinstance(value, dict):
                    schema["properties"][key] = self._infer_schema(value)
                    
        return schema
    
    def find_compatible_functions(self, source_function):
        """Findet alle Funktionen, die mit der Ausgabe der Quellfunktion kompatibel sind."""
        if source_function not in self.function_signatures:
            return []
            
        source_output = self.function_signatures[source_function]["output_schema"]
        compatible_functions = []
        
        for target_function, signature in self.function_signatures.items():
            if target_function == source_function:
                continue  # Selbstaufrufe ignorieren
                
            target_input = signature["input_schema"]
            
            # Prüfen, ob die Ausgabe der Quellfunktion mit der Eingabe der Zielfunktion kompatibel ist
            if self._is_schema_compatible(source_output, target_input):
                compatible_functions.append(target_function)
                
        return compatible_functions
    
    def _is_schema_compatible(self, output_schema, input_schema):
        """Prüft, ob zwei Schemas kompatibel sind (ob die Ausgabe als Eingabe verwendet werden kann)."""
        # In der Praxis würde hier eine tiefe JSON-Schema-Validierung stattfinden
        # Vereinfachte Implementierung:
        
        # Wenn die Ausgabe ein Objekt ist, prüfen wir, ob sie mindestens alle erforderlichen Eingabefelder enthält
        if output_schema["type"] == "object" and input_schema["type"] == "object":
            if "required" in input_schema:
                # Prüfen, ob alle erforderlichen Eingabefelder in der Ausgabe vorhanden sind
                required_fields = input_schema["required"]
                output_fields = output_schema.get("properties", {}).keys()
                
                return all(field in output_fields for field in required_fields)
            else:
                # Wenn keine Felder explizit erforderlich sind, gehen wir von Kompatibilität aus
                return True
                
        # Für andere Typen prüfen wir einfach, ob sie gleich sind
        return output_schema["type"] == input_schema["type"]
    
    def generate_all_fusion_chains(self, functions, max_length=5):
        """Generiert alle möglichen Fusionsketten basierend auf Kompatibilität."""
        all_chains = []
        
        # Alle Funktionen als mögliche Startpunkte betrachten
        for start_function in functions:
            chains = self._generate_chains_from(start_function, [], max_length)
            all_chains.extend(chains)
            
        return all_chains
    
    def _generate_chains_from(self, current_function, current_chain, max_length):
        """Rekursive Hilfsmethode zur Generierung von Ketten."""
        # Aktuelle Funktion zur Kette hinzufügen
        new_chain = current_chain + [current_function]
        
        # Wenn die maximale Länge erreicht ist, stoppen
        if len(new_chain) >= max_length:
            return [new_chain]
            
        # Alle kompatiblen Folgefunktionen finden
        next_functions = self.find_compatible_functions(current_function)
        
        # Zyklen vermeiden
        next_functions = [f for f in next_functions if f not in new_chain]
        
        # Keine weiteren kompatiblen Funktionen, Kette beenden
        if not next_functions:
            return [new_chain]
            
        # Für jede kompatible Funktion rekursiv fortsetzen
        chains = []
        for next_function in next_functions:
            chains.extend(self._generate_chains_from(next_function, new_chain, max_length))
            
        return chains


class ComprehensiveFusionOptimizer:
    """Tool zur umfassenden Optimierung von Function Fusion Konfigurationen."""
    
    def __init__(self, config_file="config/fusion_parameters.json"):
        print(f"[DEBUG] Aktuelles Arbeitsverzeichnis: {os.getcwd()}")
        print(f"[DEBUG] Erwarteter Config-Pfad: {config_file}")
        print(f"[DEBUG] Existiert Datei? {os.path.exists(config_file)}")
        # Lade Konfiguration
        with open(config_file, 'r') as f:
            self.params = json.load(f)
        
        self.tester = None  # DockerFusionTester wird später initialisiert
        self.results = {}
        self.best_configs = []
        
        # Funktionsliste dynamisch ermitteln
        self.all_functions = self._discover_all_functions()
        
        # Erweiterte Parameter für DAG-Unterstützung
        self.params["enable_dag"] = self.params.get("enable_dag", True)
        self.params["max_chain_length"] = self.params.get("max_chain_length", 5)
        self.params["min_chain_length"] = self.params.get("min_chain_length", 2)
        
        # Memory-Konfigurationen für Funktionen
        self.function_memory_configs = self.params.get("function_memory_configs", {})
        
        # Standardwert für Funktionen ohne explizite Konfiguration
        self.default_memory_configs = [128, 256, 512, 1024]
        
        # DAG-Konfigurationen
        self.dag_configs = []
        
        # Definiere Fitness-Funktionen
        self.fitness_functions = {
            "latency": lambda x: -x.get("average_latency_ms", 0),  # Niedriger ist besser
            "throughput": lambda x: x.get("requests_per_second", 0),  # Höher ist besser
            "resource_usage": lambda x: -x.get("resource_usage_percent", 0),  # Niedriger ist besser
            "speedup": lambda x: x.get("speedup_factor", 0)  # Höher ist besser
        }
        
        # Fortschritts-Tracking
        self.progress = 0
        self.total_tests = 0
        
        # FusionDiscovery für Kompatibilitätsanalyse
        self.discovery = FusionDiscovery()
    
    def _discover_all_functions(self):
        """Findet automatisch alle verfügbaren Funktionen im System."""
        # Zuerst prüfen, ob Funktionen in der Konfiguration angegeben sind
        if "functions" in self.params:
            return self.params["functions"]
        
        # Andernfalls versuchen, sie automatisch zu erkennen
        functions = []
        
        # Beispiel für die automatische Erkennung basierend auf den Docker-Funktionsordnern
        import os
        functions_dir = "functions/webshop"
        if os.path.exists(functions_dir):
            functions = [d for d in os.listdir(functions_dir) 
                        if os.path.isdir(os.path.join(functions_dir, d))]
        
        if not functions:
            # Fallback: Hard-coded Liste basierend auf den Docker-Containern
            functions = [
                "addcartitem", "cartkvstorage", "checkout", "currency", 
                "email", "emptycart", "frontend", "getads", "getcart", 
                "getproduct", "listproducts", "listrecommendations", 
                "payment", "searchproducts", "shipmentquote", "shiporder", 
                "supportedcurrencies"
            ]
            
        print(f"Entdeckte {len(functions)} Funktionen: {functions}")
        return functions
    
    def generate_all_possible_chains(self, max_chain_length=None, min_chain_length=None, limit=10):
        """Erzeugt alle möglichen Funktionsketten bis zu einer bestimmten Länge."""
        if max_chain_length is None:
            max_chain_length = self.params["max_chain_length"]
            
        if min_chain_length is None:
            min_chain_length = self.params["min_chain_length"]
        
        all_chains = []
        total_generated = 0
        
        # Berechne, wie viele Ketten pro Länge generiert werden sollen
        lengths = list(range(min_chain_length, max_chain_length + 1))
        chains_per_length = limit // len(lengths)
        
        for length in lengths:
            # Berechne, wie viele Permutationen es geben würde
            import math
            total_possible = math.perm(len(self.all_functions), length)
            
            if total_possible <= chains_per_length:
                # Wenn weniger als das Limit, generiere alle
                chains = [list(p) for p in itertools.permutations(self.all_functions, length)]
            else:
                # Ansonsten generiere eine zufällige Teilmenge
                print(f"  Begrenze Ketten mit Länge {length} auf {chains_per_length} (von {total_possible})")
                
                # Methode 1: Zufällige Auswahl von Funktionen für jede Position
                chains = []
                for _ in range(chains_per_length):
                    chain = random.sample(self.all_functions, length)
                    if chain not in chains:  # Vermeidet Duplikate
                        chains.append(chain)
                
                # Stelle sicher, dass wir genug haben (falls es Duplikate gab)
                while len(chains) < chains_per_length and len(chains) < total_possible:
                    chain = random.sample(self.all_functions, length)
                    if chain not in chains:
                        chains.append(chain)
            
            all_chains.extend(chains)
            total_generated += len(chains)
            
            if total_generated >= limit:
                break
        
        # Falls wir über dem Limit sind, kürzen
        if len(all_chains) > limit:
            all_chains = all_chains[:limit]
        
        print(f"Generierte {len(all_chains)} mögliche Funktionsketten mit Länge {min_chain_length}-{max_chain_length}.")
        return all_chains
        
    
    def filter_compatible_chains(self, all_chains):
        """Filtert Ketten basierend auf Input/Output-Kompatibilität."""
        compatible_chains = []
        
        for chain in all_chains:
            if self._is_chain_compatible(chain):
                compatible_chains.append(chain)
                
        print(f"Gefiltert auf {len(compatible_chains)} kompatible Ketten.")
        return compatible_chains
    
    def _is_chain_compatible(self, chain):
        """Prüft, ob die Ein-/Ausgaben der Funktionen in der Kette kompatibel sind."""
        # Diese Methode würde die API-Spezifikationen jeder Funktion analysieren
        # und prüfen, ob die Ausgabe von Funktion i als Eingabe für Funktion i+1 dienen kann
        
        # Hier eine vereinfachte Implementierung, die bekannte Inkompatibilitäten prüft
        for i in range(len(chain) - 1):
            # Bekannte inkompatible Funktionspaare
            incompatible_pairs = [
                ("addcartitem", "emptycart"),           # Logischer Konflikt
                ("checkout", "addcartitem"),            # Checkout sollte nach dem Hinzufügen von Items sein
                ("currency", "listproducts"),           # Currency nimmt keinen Product-Response entgegen
                ("payment", "shipmentquote")            # Payment und Shipment haben inkompatible Parameter
            ]
            
            if (chain[i], chain[i+1]) in incompatible_pairs:
                return False
                
        return True
    
    def generate_dag_structures(self, compatible_chains, max_dags=50, max_chains_per_start=5000):
        """Generiert komplexe DAG-Strukturen aus kompatiblen Ketten ohne Zyklen."""
        if not self.params.get("enable_dag", True):
            print("DAG-Generierung deaktiviert.")
            return []
        
        print(f"Beginne DAG-Generierung (max {max_dags} DAGs)...")
        dags = []
        processed_starts = 0
        
        # Gruppiere Ketten nach erstem Element (Startknoten) 
        by_first_node = {}
        for chain in compatible_chains:
            if not chain:
                continue
                
            first = chain[0]
            if first not in by_first_node:
                by_first_node[first] = []
                
            by_first_node[first].append(chain)
        
        print(f"Gefunden: {len(by_first_node)} mögliche Startknoten für DAGs")
        
        # Verarbeite Startknoten mit den meisten Ketten zuerst
        sorted_starts = sorted(by_first_node.items(), key=lambda x: len(x[1]), reverse=True)
        
        for start_node, chains in sorted_starts:
            if len(chains) < 2:
                continue
                
            processed_starts += 1
            if processed_starts % 5 == 0:
                print(f"Verarbeite Startknoten {processed_starts}/{len(sorted_starts)}: {start_node} mit {len(chains)} Ketten")
            
            # Begrenze die Anzahl der Ketten pro Startknoten für bessere Performance
            if len(chains) > max_chains_per_start:
                print(f"  Begrenze Ketten für {start_node} von {len(chains)} auf {max_chains_per_start}")
                chains = chains[:max_chains_per_start]
            
            # Erstelle einen Graphen mit gewichteten Kanten
            G = {}
            edge_weights = {}
            
            # Füge Knoten hinzu
            for chain in chains:
                for node in chain:
                    if node not in G:
                        G[node] = set()
            
            # Gewichte Kanten basierend auf Häufigkeit und Position
            for chain in chains:
                for i in range(len(chain) - 1):
                    u, v = chain[i], chain[i+1]
                    if v not in G[u]:
                        G[u].add(v)
                        edge_weights[(u, v)] = 1
                    else:
                        edge_weights[(u, v)] += 1
            
            # Wähle Kanten mit höherem Gewicht, um Zyklen zu vermeiden
            dag = {
                "nodes": set(G.keys()),
                "edges": [],
                "start_node": start_node
            }
            
            # Sortiere Kanten nach Gewicht (absteigend)
            sorted_edges = sorted(edge_weights.items(), key=lambda x: x[1], reverse=True)
            
            # Füge Kanten hinzu, solange keine Zyklen entstehen
            for (u, v), weight in sorted_edges:
                edge = {"from": u, "to": v}
                dag["edges"].append(edge)
                
                # Prüfe auf Zyklen und entferne die Kante, wenn ein Zyklus entsteht
                if self._has_cycles(dag):
                    dag["edges"].remove(edge)
            
            # Nur DAGs mit mindestens 2 Kanten hinzufügen
            if len(dag["edges"]) >= 2:
                # Konvertiere nodes von Set zu Liste
                dag["nodes"] = list(dag["nodes"])
                dags.append(dag)
                
                if len(dags) % 10 == 0:
                    print(f"  Bisher {len(dags)} DAGs generiert")
                
                # Begrenze die Anzahl der DAGs
                if len(dags) >= max_dags:
                    print(f"Maximale Anzahl von {max_dags} DAGs erreicht, beende Generierung")
                    break
        
        print(f"Generierte {len(dags)} komplexe DAG-Strukturen aus {processed_starts} Startknoten.")
        return dags
    
    def _has_cycles(self, dag):
        """Prüft, ob ein DAG Zyklen enthält."""
        # Implementierung eines Algorithmus zum Erkennen von Zyklen in einem gerichteten Graphen
        visited = set()
        temp_visited = set()
        
        def visit(node):
            """Rekursive DFS-Funktion zum Erkennen von Zyklen."""
            if node in temp_visited:
                return True  # Zyklus gefunden
                
            if node in visited:
                return False
                
            temp_visited.add(node)
            
            # Besuche alle Nachbarn
            for edge in dag["edges"]:
                if edge["from"] == node and visit(edge["to"]):
                    return True
                    
            temp_visited.remove(node)
            visited.add(node)
            return False
            
        # Starte DFS von jedem Knoten aus
        for node in dag["nodes"]:
            if node not in visited and visit(node):
                return True
                
        return False
    
    def _generate_memory_combinations(self, chain):
        """Generiert alle möglichen Memory-Kombinationen für eine Kette."""
        # Sammle Memory-Optionen für jede Funktion in der Kette
        memory_options = []
        for func in chain:
            # Verwende konfigurierte Memory-Werte oder Standard
            options = self.function_memory_configs.get(func, self.default_memory_configs)
            memory_options.append(options)
        
        # Für kurze Ketten: Alle Kombinationen durchgehen
        if len(chain) <= 3:
            all_combinations = list(itertools.product(*memory_options))
            return [dict(zip(chain, combo)) for combo in all_combinations]
        
        # Für längere Ketten: Sampling zur Reduzierung der Kombinationen
        result = []
        
        # 1. Alle Funktionen mit dem gleichen Memory-Wert
        for mem in self.default_memory_configs:
            result.append({func: mem for func in chain})
        
        # 2. Erste Funktion mit höherem Memory, Rest niedrig
        for high_mem in [512, 1024, 2048]:
            config = {func: 128 for func in chain}
            config[chain[0]] = high_mem
            result.append(config)
        
        # 3. Einige zufällige Kombinationen
        for _ in range(10):
            config = {}
            for func in chain:
                options = self.function_memory_configs.get(func, self.default_memory_configs)
                config[func] = random.choice(options)
            result.append(config)
        
        return result
    
    def generate_test_configurations(self, test_count=None):
        """Überschreibt die bisherige Methode, um alle möglichen Kombinationen zu testen."""
        # Schritt 1: Alle möglichen Funktionsketten generieren
        print("Generiere alle möglichen Funktionsketten...")
        all_chains = self.generate_all_possible_chains()
        
        # Schritt 2: Auf kompatible Ketten filtern
        print("Filtere auf kompatible Ketten...")
        compatible_chains = self.filter_compatible_chains(all_chains)
        
        # Schritt 3: DAG-Strukturen generieren
        print("Generiere DAG-Strukturen...")
        dags = self.generate_dag_structures(compatible_chains)
        self.dag_configs = dags
        
        # Schritt 4: Für jede kompatible Kette alle Parameter-Kombinationen generieren
        configs = []
        
        # Zuerst lineare Ketten
        print("Generiere Konfigurationen für lineare Ketten...")
        for chain in tqdm(compatible_chains):
            # Für jede Kette verschiedene Memory-Konfigurationen
            memory_configs = self._generate_memory_combinations(chain)
            
            for memory_config in memory_configs:
                # Kartesisches Produkt aller Parameter
                for deploy in self.params["deployment"]:
                    for iterations in self.params["io_config"]["iterations"]:
                        for file_size in self.params["io_config"]["file_size_kb"]:
                            for fsync in self.params["io_config"]["enable_fsync"]:
                                for latency in self.params["network"]["latency_ms"]:
                                    for loss in self.params["network"]["loss_percent"]:
                                        # Bandbreiten-Parameter
                                        bandwidth_options = self.params["network"].get("bandwidth_kbit", [None])
                                        
                                        for bandwidth in bandwidth_options:
                                            config = {
                                                "id": len(configs),
                                                "type": "chain",
                                                "chain": chain,
                                                "memory_config": memory_config,
                                                "deployment": deploy,
                                                "io_config": {
                                                    "iterations": iterations,
                                                    "file_size_kb": file_size,
                                                    "enable_fsync": fsync
                                                },
                                                "network": {
                                                    "latency_ms": latency,
                                                    "loss_percent": loss,
                                                    "bandwidth_kbit": bandwidth
                                                }
                                            }
                                            configs.append(config)
        
        # Dann DAG-Strukturen
        if self.params.get("enable_dag", True):
            print("Generiere Konfigurationen für DAG-Strukturen...")
            for dag in tqdm(dags):
                # Für DAGs nehmen wir nur eine Teilmenge der Parameter-Kombinationen
                # um die Gesamtzahl der Tests zu begrenzen
                deployments = self.params["deployment"]
                iterations = [self.params["io_config"]["iterations"][0], self.params["io_config"]["iterations"][-1]]
                file_sizes = [self.params["io_config"]["file_size_kb"][0], self.params["io_config"]["file_size_kb"][-1]]
                
                # Memory-Konfigurationen für DAGs (einfacheres Sampling)
                memory_config = {}
                for node in dag["nodes"]:
                    options = self.function_memory_configs.get(node, self.default_memory_configs)
                    memory_config[node] = options[0]  # Verwende die niedrigste Memory-Option als Standard
                
                for deploy in deployments:
                    for iter_val in iterations:
                        for file_size in file_sizes:
                            for fsync in [False]:  # Vereinfachung: nur ohne fsync
                                for latency in [self.params["network"]["latency_ms"][0]]:  # Niedrigste Latenz
                                    for loss in [self.params["network"]["loss_percent"][0]]:  # Niedrigster Verlust
                                        bandwidth = None  # Unbegrenzte Bandbreite
                                        
                                        config = {
                                            "id": len(configs),
                                            "type": "dag",
                                            "dag": dag,
                                            "memory_config": memory_config,
                                            "deployment": deploy,
                                            "io_config": {
                                                "iterations": iter_val,
                                                "file_size_kb": file_size,
                                                "enable_fsync": fsync
                                            },
                                            "network": {
                                                "latency_ms": latency,
                                                "loss_percent": loss,
                                                "bandwidth_kbit": bandwidth
                                            }
                                        }
                                        configs.append(config)
        
        self.total_tests = len(configs)
        print(f"Generierte insgesamt {self.total_tests} Test-Konfigurationen.")
        
        # Optional: Wenn ein test_count angegeben wurde und weniger ist als die Gesamtzahl
        if test_count and test_count < len(configs):
            print(f"Reduziere auf {test_count} Test-Konfigurationen...")
            
            # Strategie für die Reduzierung:
            # 1. Alle DAG-Strukturen beibehalten (diese sind besonders interessant)
            dag_configs = [c for c in configs if c["type"] == "dag"]
            chain_configs = [c for c in configs if c["type"] == "chain"]
            
            remaining = test_count - len(dag_configs)
            if remaining <= 0:
                # Falls zu viele DAGs, auch diese reduzieren
                configs = random.sample(dag_configs, test_count)
            else:
                # Sonst zufällige Auswahl von Ketten hinzufügen
                chain_selection = random.sample(chain_configs, min(remaining, len(chain_configs)))
                configs = dag_configs + chain_selection
                
            self.total_tests = len(configs)
            print(f"Reduziert auf {self.total_tests} Test-Konfigurationen.")
            
        return configs
    
    def _calculate_fitness(self, result):
        """Berechnet den Fitness-Wert eines Testergebnisses."""
        # Gewichtete Summe verschiedener Metriken
        speedup_fitness = self.fitness_functions["speedup"](result) * 2.0  # Doppelte Gewichtung
        latency_fitness = self.fitness_functions["latency"](result)
        throughput_fitness = self.fitness_functions["throughput"](result)
        resource_fitness = self.fitness_functions["resource_usage"](result)
        
        # Gewichtung der verschiedenen Aspekte
        return (
            0.4 * speedup_fitness + 
            0.3 * latency_fitness + 
            0.2 * throughput_fitness + 
            0.1 * resource_fitness
        )
    
    async def run_tests(self, test_configurations):
        """Führt die Tests für alle Konfigurationen aus."""
        from docker_fusion_tester import DockerFusionTester
        
        self.tester = DockerFusionTester()
        await self.tester.setup()
        
        try:
            # Fortschrittsanzeige
            progress_bar = tqdm(total=len(test_configurations))
            
            # Tests ausführen
            for config in test_configurations:
                result = await self._run_single_test(config)
                
                config_key = str(config["id"])
                self.results[config_key] = result
                
                # Fortschritt aktualisieren
                self.progress += 1
                progress_bar.update(1)
                
                # Speichere Zwischenergebnisse
                if self.progress % 100 == 0:
                    self._save_results()
            
            progress_bar.close()
            
            # Sortiere und speichere die besten Konfigurationen
            self._update_best_configs()
            self._save_results()
            
        finally:
            await self.tester.cleanup()
    
    async def run_tests_parallel(self, test_configurations, max_workers=8):
        """Führt Tests parallel mit einer begrenzten Anzahl von Workern aus."""
        from .docker_fusion_tester import DockerFusionTester
        
        self.tester = DockerFusionTester()
        await self.tester.setup()
        
        try:
            total = len(test_configurations)
            chunks = [test_configurations[i:i + total // max_workers + 1] 
                      for i in range(0, total, total // max_workers + 1)]
            
            # Parallele Tasks starten
            tasks = []
            for chunk in chunks:
                task = asyncio.create_task(self._run_test_chunk(chunk))
                tasks.append(task)
            
            # Auf alle Tasks warten mit Fortschrittsanzeige
            for result in await tqdm_asyncio.gather(*tasks, total=len(tasks)):
                # Ergebnisse zusammenführen
                for config_key, test_result in result.items():
                    self.results[config_key] = test_result
            
            # Beste Konfigurationen aktualisieren
            self._update_best_configs()
            self._save_results()
            
        finally:
            await self.tester.cleanup()
    
    async def _run_test_chunk(self, chunk):
        """Führt einen Chunk von Tests aus und gibt die Ergebnisse zurück."""
        results = {}
        
        for config in chunk:
            result = await self._run_single_test(config)
            config_key = str(config["id"])
            results[config_key] = result
        
        return results
    
    async def _run_single_test(self, config):
        """Überschreibt die Basismethode, um sowohl Ketten als auch DAGs zu testen."""
        # Je nach Konfigurationstyp unterschiedliche Tests durchführen
        if config["type"] == "chain":
            return await self._run_chain_test(config)
        elif config["type"] == "dag":
            return await self._run_dag_test(config)
        else:
            raise ValueError(f"Unbekannter Konfigurationstyp: {config['type']}")
    
    async def _run_chain_test(self, config):
        """Führt einen Test für eine lineare Funktionskette durch."""
        # Konfigurationen auslesen
        chain = config["chain"]
        memory_config = config["memory_config"]  # Memory-Konfiguration pro Funktion
        
        if not chain:
            return {"error": "Leere Funktionskette"}
            
        # I/O-Konfiguration erstellen
        io_params = {
            "iterations": config["io_config"]["iterations"],
            "file_size_kb": config["io_config"]["file_size_kb"],
            "enable_fsync": config["io_config"]["enable_fsync"],
            "enable_fio": random.random() < 0.2  # 20% Sampling für FIO
        }
        
        # Netzwerk-Konfiguration
        network_config = {
            "latency_ms": config["network"]["latency_ms"],
            "loss_percent": config["network"]["loss_percent"],
            "bandwidth_kbit": config["network"].get("bandwidth_kbit")
        }
        
        # Memory-Konfiguration für die beteiligten Funktionen setzen
        for func_name, memory in memory_config.items():
            try:
                await self.tester.update_function_config(func_name, {"MEMORY_SIZE": str(memory)})
            except Exception as e:
                print(f"Warnung: Konnte Memory für {func_name} nicht setzen: {e}")
        
        # Netzwerk-Konfiguration für die beteiligten Funktionen setzen
        for func_name in chain:
            try:
                await self.tester.update_network_config(func_name, network_config)
            except Exception as e:
                print(f"Warnung: Konnte Netzwerk für {func_name} nicht konfigurieren: {e}")
        
        start_time = time.time()
        
        # Direkter Test (ohne Fusion)
        # Bei einer Kette rufen wir die letzte Funktion direkt auf
        direct_service = chain[-1]
        direct_result = await self.tester.invoke_function(direct_service, {
            "operation": "test",
            "userId": f"test_{config['id']}_direct",
            "io_params": io_params
        })
        
        # Fusion-Test
        # Bei einer Kette rufen wir die erste Funktion auf, die dann die anderen aufruft
        fusion_service = chain[0]
        fusion_result = await self.tester.invoke_function(fusion_service, {
            "userId": f"test_{config['id']}_fusion",
            "io_params": io_params
        })
        
        end_time = time.time()
        
        # Ergebnisse erfassen
        direct_time = direct_result.get("execution_time_ms", 0)
        fusion_time = fusion_result.get("execution_time_ms", 0)
        
        speedup = direct_time / fusion_time if fusion_time > 0 else 0
        
        # CPU-Nutzung schätzen (vereinfacht)
        resource_usage_percent = 0
        if "body" in fusion_result and isinstance(fusion_result["body"], dict):
            performance = fusion_result["body"].get("performance", {})
            if isinstance(performance, dict):
                resource_usage_percent = performance.get("cpu_usage_percent", 0)
        
        return {
            "config": config,
            "direct_time_ms": direct_time,
            "fusion_time_ms": fusion_time,
            "speedup_factor": speedup,
            "test_duration_ms": (end_time - start_time) * 1000,
            "average_latency_ms": fusion_time,
            "requests_per_second": 1000 / fusion_time if fusion_time > 0 else 0,
            "resource_usage_percent": resource_usage_percent,
            "direct_result": direct_result,
            "fusion_result": fusion_result,
            "timestamp": time.time()
        }
    
    async def _run_dag_test(self, config):
        """Führt einen Test für einen DAG durch."""
        # Hier müssen wir die DAG-spezifische Testlogik implementieren
        dag = config["dag"]
        memory_config = config["memory_config"]
        
        if not dag or not dag["nodes"]:
            return {"error": "Leerer DAG"}
            
        # I/O-Konfiguration erstellen
        io_params = {
            "iterations": config["io_config"]["iterations"],
            "file_size_kb": config["io_config"]["file_size_kb"],
            "enable_fsync": config["io_config"]["enable_fsync"],
            "enable_fio": random.random() < 0.2  # 20% Sampling für FIO
        }
        
        # Netzwerk-Konfiguration
        network_config = {
            "latency_ms": config["network"]["latency_ms"],
            "loss_percent": config["network"]["loss_percent"],
            "bandwidth_kbit": config["network"].get("bandwidth_kbit")
        }
        
        # Memory und Netzwerk für alle Knoten konfigurieren
        for node in dag["nodes"]:
            memory = memory_config.get(node, 128)
            try:
                await self.tester.update_function_config(node, {"MEMORY_SIZE": str(memory)})
                await self.tester.update_network_config(node, network_config)
            except Exception as e:
                print(f"Warnung: Konnte {node} nicht konfigurieren: {e}")
        
        start_time = time.time()
        
        # Direkter Test: Rufe alle Endfunktionen direkt auf
        # Endfunktionen sind Knoten ohne ausgehende Kanten
        end_nodes = [node for node in dag["nodes"] 
                    if not any(edge["from"] == node for edge in dag["edges"])]
                    
        direct_results = {}
        for node in end_nodes:
            result = await self.tester.invoke_function(node, {
                "operation": "test",
                "userId": f"test_{config['id']}_direct_{node}",
                "io_params": io_params
            })
            direct_results[node] = result
        
        # Berechne Gesamtzeit für direkten Aufruf (Summe aller Endknoten)
        direct_time = sum(result.get("execution_time_ms", 0) for result in direct_results.values())
        
        # Fusion-Test: Rufe den Startknoten auf
        start_node = dag["start_node"]
        fusion_result = await self.tester.invoke_function(start_node, {
            "userId": f"test_{config['id']}_fusion_dag",
            "io_params": io_params
        })
        
        end_time = time.time()
        fusion_time = fusion_result.get("execution_time_ms", 0)
        
        speedup = direct_time / fusion_time if fusion_time > 0 else 0
        
        # CPU-Nutzung schätzen (vereinfacht)
        resource_usage_percent = 0
        if "body" in fusion_result and isinstance(fusion_result["body"], dict):
            performance = fusion_result["body"].get("performance", {})
            if isinstance(performance, dict):
                resource_usage_percent = performance.get("cpu_usage_percent", 0)
        
        return {
            "config": config,
            "direct_time_ms": direct_time,
            "fusion_time_ms": fusion_time,
            "speedup_factor": speedup,
            "test_duration_ms": (end_time - start_time) * 1000,
            "average_latency_ms": fusion_time,
            "requests_per_second": 1000 / fusion_time if fusion_time > 0 else 0,
            "resource_usage_percent": resource_usage_percent,
            "direct_results": direct_results,
            "fusion_result": fusion_result,
            "timestamp": time.time()
        }
    
    def _update_best_configs(self):
        """Aktualisiert die Liste der besten Konfigurationen basierend auf den Testergebnissen."""
        # Berechne Fitness für alle Ergebnisse
        fitness_scores = {}
        for config_key, result in self.results.items():
            fitness_scores[config_key] = self._calculate_fitness(result)
        
        # Sortiere nach Fitness
        sorted_configs = sorted(
            [(k, v) for k, v in fitness_scores.items()],
            key=lambda x: x[1],
            reverse=True
        )
        
        # Wähle die besten Konfigurationen
        self.best_configs = [
            self.results[config_key]["config"]
            for config_key, _ in sorted_configs[:10]  # Top 10
        ]
    
    def _save_results(self):
        """Speichert die Testergebnisse und besten Konfigurationen."""
        # Speichere alle Ergebnisse
        os.makedirs("results", exist_ok=True)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        
        with open(f"results/fusion_results_{timestamp}.json", "w") as f:
            json.dump({
                "timestamp": time.time(),
                "progress": self.progress,
                "total_tests": self.total_tests,
                "results": self.results,
                "best_configs": self.best_configs
            }, f, indent=2)
        
        # Speichere beste Konfigurationen separat
        with open(f"results/best_configs_{timestamp}.json", "w") as f:
            json.dump({
                "timestamp": time.time(),
                "best_configs": self.best_configs
            }, f, indent=2)
    
    def analyze_results(self):
        """Analysiert die Testergebnisse und generiert einen Bericht."""
        if not self.results:
            return "Keine Testergebnisse vorhanden."
        
        report = {
            "summary": {
                "total_tests": len(self.results),
                "average_speedup": 0,
                "max_speedup": 0,
                "best_config": None
            },
            "performance_by_parameter": {},
            "io_performance": {},
            "network_performance": {},
            "memory_performance": {},
            "chain_performance": {},
            "dag_performance": {}
        }

        # === 1. Summary berechnen ===
        speedups = []
        for result in self.results.values():
            speedup = result.get("speedup_factor", 0)
            speedups.append(speedup)

            if speedup > report["summary"]["max_speedup"]:
                report["summary"]["max_speedup"] = speedup
                report["summary"]["best_config"] = result["config"]

        report["summary"]["average_speedup"] = sum(speedups) / len(speedups) if speedups else 0

        # === 2. Chain Performance ===
        chain_data = {}
        for result in self.results.values():
            config = result["config"]
            if config["type"] == "chain":
                chain_str = "->".join(config["chain"])
                chain_data.setdefault(chain_str, []).append(result.get("speedup_factor", 0))

        report["chain_performance"] = {
            chain: {
                "avg_speedup": sum(vals) / len(vals),
                "count": len(vals)
            }
            for chain, vals in chain_data.items()
        }

        # === 3. DAG Performance ===
        dag_data = {}
        for result in self.results.values():
            config = result["config"]
            if config["type"] == "dag":
                dag_id = f"{config['dag']['start_node']}_nodes_{len(config['dag']['nodes'])}"
                dag_data.setdefault(dag_id, []).append(result.get("speedup_factor", 0))

        report["dag_performance"] = {
            dag: {
                "avg_speedup": sum(vals) / len(vals),
                "count": len(vals)
            }
            for dag, vals in dag_data.items()
        }

        # === 4. Memory Performance (für Chains und DAGs) ===
        memory_groups = {}
        for result in self.results.values():
            config = result["config"]
            memory_config = config.get("memory_config", {})
            if not memory_config:
                continue

            if config["type"] == "chain" and config["chain"]:
                func1 = config["chain"][0]
            elif config["type"] == "dag":
                func1 = config["dag"]["start_node"]
            else:
                continue

            memory = memory_config.get(func1, 128)
            key = f"{func1}_{memory}MB"
            memory_groups.setdefault(key, []).append(result.get("speedup_factor", 0))

        report["memory_performance"] = {
            key: {
                "avg_speedup": sum(vals) / len(vals),
                "count": len(vals)
            }
            for key, vals in memory_groups.items()
        }

        # === 5. IO Performance ===
        io_groups = {}
        for result in self.results.values():
            config = result["config"]
            iterations = config["io_config"]["iterations"]
            file_size = config["io_config"]["file_size_kb"]
            key = f"iter_{iterations}_size_{file_size}"
            io_groups.setdefault(key, []).append(result.get("speedup_factor", 0))

        report["io_performance"] = {
            key: {
                "avg_speedup": sum(vals) / len(vals),
                "count": len(vals)
            }
            for key, vals in io_groups.items()
        }

        # === 6. Network Performance ===
        network_groups = {}
        for result in self.results.values():
            config = result["config"]
            net = config.get("network", {})
            latency = net.get("latency_ms", 0)
            loss = net.get("loss_percent", 0)
            bw = net.get("bandwidth_kbit", "unlimited")
            key = f"lat_{latency}_loss_{loss}_bw_{bw}"
            network_groups.setdefault(key, []).append(result.get("speedup_factor", 0))

        report["network_performance"] = {
            key: {
                "avg_speedup": sum(vals) / len(vals),
                "count": len(vals)
            }
            for key, vals in network_groups.items()
        }

        # === 7. Top-5 Konfigurationen ===
        top_configs = []
        for _, result in sorted(
            self.results.items(),
            key=lambda x: x[1].get("speedup_factor", 0),
            reverse=True
        )[:5]:
            config = result["config"]
            if config["type"] == "chain":
                top_configs.append({
                    "chain": "->".join(config["chain"]),
                    "memory": config["memory_config"],
                    "speedup": result.get("speedup_factor", 0),
                    "latency_ms": result.get("fusion_time_ms", 0)
                })
            else:  # dag
                top_configs.append({
                    "type": "dag",
                    "start_node": config["dag"]["start_node"],
                    "node_count": len(config["dag"]["nodes"]),
                    "speedup": result.get("speedup_factor", 0),
                    "latency_ms": result.get("fusion_time_ms", 0)
                })

        report["top_configs"] = top_configs

        return report



async def run_comprehensive_fusion_optimization(test_count=None, parallel=True, max_workers=8):
    """Führt einen umfassenden Fusionsoptimierungsprozess durch."""
    print("Starte umfassende Function Fusion Optimierung...")
    
    # 1. Optimizer für umfassende Tests erstellen
    optimizer = ComprehensiveFusionOptimizer()
    
    # 2. Testvarianten für alle Ketten und DAGs generieren
    print("Generiere Testkonfigurationen...")
    test_configs = optimizer.generate_test_configurations(test_count)
    
    # 3. Tests ausführen
    print("Führe Tests aus...")
    if parallel and max_workers > 1:
        await optimizer.run_tests_parallel(test_configs, max_workers)
    else:
        await optimizer.run_tests(test_configs)
    
    # 4. Ergebnisse analysieren
    print("Analysiere Ergebnisse...")
    results = optimizer.analyze_results()
    
    # 5. Bericht erstellen
    print("Erstelle Bericht...")
    generate_detailed_report(results)
    
    print("Umfassende Function Fusion Optimierung abgeschlossen.")
    return results


def generate_detailed_report(results):
    """Erstellt einen detaillierten Bericht über die Optimierungsergebnisse."""
    # Hier würde ein umfassender Bericht erstellt werden
    
    # 1. Überblick
    print("=== FUNCTION FUSION OPTIMIERUNG - BERICHT ===")
    print(f"Getestete Konfigurationen: {results['summary']['total_tests']}")
    print(f"Durchschnittliche Beschleunigung: {results['summary']['average_speedup']:.2f}x")
    print(f"Maximale Beschleunigung: {results['summary']['max_speedup']:.2f}x")
    
    # 2. Top-5 Konfigurationen
    print("\n=== TOP 5 KONFIGURATIONEN ===")
    for i, config in enumerate(results.get("top_configs", []), 1):
        if "chain" in config:
            print(f"{i}. Kette: {config['chain']}")
        else:
            print(f"{i}. DAG mit Startknoten: {config.get('start_node', 'N/A')}, " +
                 f"{config.get('node_count', 0)} Knoten")
        
        print(f"   Beschleunigung: {config.get('speedup', 0):.2f}x")
        print(f"   Latenz: {config.get('latency_ms', 0):.2f} ms")
        if "memory" in config:
            print(f"   Memory-Konfiguration: {config['memory']}")
        print("   ---")
    
    # 3. Performance nach Chain-Typ
    print("\n=== PERFORMANCE NACH KETTENTYP ===")
    chain_data = sorted(
        results.get("chain_performance", {}).items(),
        key=lambda x: x[1]["avg_speedup"],
        reverse=True
    )
    for chain, data in chain_data[:5]:  # Top-5
        print(f"Kette: {chain}")
        print(f"  Durchschnittliche Beschleunigung: {data['avg_speedup']:.2f}x")
        print(f"  Anzahl Tests: {data['count']}")
    
    # 4. Memory-Performance
    print("\n=== PERFORMANCE NACH MEMORY-KONFIGURATION ===")
    memory_data = sorted(
        results.get("memory_performance", {}).items(),
        key=lambda x: x[1]["avg_speedup"],
        reverse=True
    )
    for mem, data in memory_data[:5]:  # Top-5
        print(f"Konfiguration: {mem}")
        print(f"  Durchschnittliche Beschleunigung: {data['avg_speedup']:.2f}x")
        print(f"  Anzahl Tests: {data['count']}")
    
    # 5. Ausgabe in Datei
    import json
    
    report_file = f"fusion_optimization_results_{time.strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"\nDetaillierten Bericht in '{report_file}' gespeichert.")


class DockerFusionTester:
    """Führt Tests mit Docker-basierten Funktionen durch."""
    
    def __init__(self, services_url_base="http://localhost"):
        self.services_url_base = services_url_base
        self.http_client = None
    
    async def setup(self):
        """Initialisiert den Tester."""
        self.http_client = httpx.AsyncClient(timeout=30.0)
        print("DockerFusionTester bereit")
    
    async def cleanup(self):
        """Räumt Ressourcen auf."""
        if self.http_client:
            await self.http_client.aclose()
    
    async def invoke_function(self, function_name, event_data):
        """Ruft eine Funktion auf und gibt das Ergebnis zurück."""
        # Service-Port bestimmen (z.B. 8000 + Service-Index)
        service_name = function_name.lower().replace("_", "-")
        url = f"{self.services_url_base}:{self._get_service_port(service_name)}/invoke"
        
        # Aufruf durchführen
        try:
            start_time = asyncio.get_event_loop().time()
            response = await self.http_client.post(url, json=event_data)
            end_time = asyncio.get_event_loop().time()
            
            if response.status_code == 200:
                result = response.json()
                # Ausführungszeit hinzufügen
                execution_time = (end_time - start_time) * 1000  # ms
                result["execution_time_ms"] = execution_time
                return result
            else:
                return {
                    "error": f"Status {response.status_code}",
                    "execution_time_ms": (end_time - start_time) * 1000
                }
                
        except Exception as e:
            return {"error": str(e), "execution_time_ms": 0}
    
    async def update_function_config(self, function_name, config_updates):
        """Aktualisiert die Konfiguration einer Funktion (z.B. Memory)."""
        service_name = function_name.lower().replace("_", "-")
        url = f"{self.services_url_base}:{self._get_service_port(service_name)}/config"
        
        try:
            response = await self.http_client.post(url, json=config_updates)
            return response.status_code == 200
        except Exception as e:
            print(f"Fehler beim Aktualisieren der Konfiguration: {e}")
            return False
    
    async def update_network_config(self, function_name, network_config):
        """Aktualisiert die Netzwerkkonfiguration einer Funktion."""
        service_name = function_name.lower().replace("_", "-")
        url = f"{self.services_url_base}:{self._get_service_port(service_name)}/network"
        
        try:
            response = await self.http_client.post(url, json=network_config)
            return response.status_code == 200
        except Exception as e:
            print(f"Fehler beim Aktualisieren der Netzwerkkonfiguration: {e}")
            return False
    
    def _get_service_port(self, service_name):
        """Gibt den Port für einen Service zurück."""
        # Idealerweise aus einer Konfigurationsdatei oder Environment lesen
        service_ports = {
            "addcartitem": 8001,
            "cartkvstorage": 8002,
            "checkout": 8003,
            "currency": 8004,
            "email": 8005,
            "emptycart": 8006,
            "frontend": 8007,
            "getads": 8008,
            "getcart": 8009,
            "getproduct": 8010,
            "listproducts": 8011,
            "listrecommendations": 8012,
            "payment": 8013,
            "searchproducts": 8014,
            "shipmentquote": 8015,
            "shiporder": 8016,
            "supportedcurrencies": 8017
        }
        return service_ports.get(service_name, 8000)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Comprehensive Function Fusion Optimizer')
    parser.add_argument('--test-count', type=int, help='Anzahl der durchzuführenden Tests')
    parser.add_argument('--parallel', action='store_true', help='Tests parallel ausführen')
    parser.add_argument('--workers', type=int, default=8, help='Anzahl der Worker für parallele Ausführung')
    args = parser.parse_args()
    
    # Comprehensive Optimierung durchführen
    asyncio.run(run_comprehensive_fusion_optimization(
        test_count=args.test_count,
        parallel=args.parallel,
        max_workers=args.workers
    ))