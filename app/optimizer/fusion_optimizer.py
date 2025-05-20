# app/optimizer/fusion_optimizer.py
import asyncio
import json
import time
import random
import itertools
import os
import httpx
import logging
import traceback
from typing import Dict, List, Any, Optional, Set, Tuple
from tqdm import tqdm
from tqdm.asyncio import tqdm_asyncio

# Konfiguriere Logging mit detaillierterem Format
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("fusion_optimizer")

# Füge einen Stream-Handler für die Konsolenausgabe hinzu
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
logger.addHandler(console_handler)

class FunctionCallGraph:
    """
    Repräsentiert einen gerichteten Graphen aller möglichen Funktionsaufrufe
    und deren semantische Zusammenhänge.
    """
    
    def __init__(self):
        logger.info("Initialisiere FunctionCallGraph")
        # Adjazenzliste: function_name -> [possible_next_functions]
        self.call_edges = {}
        # Semantische Verträglichkeit: (from_func, to_func) -> bool
        self.compatibility = {}
        # Explizite Blacklist: Paare von Funktionen, die niemals aufgerufen werden sollten
        self.blacklist = set()
        
    def add_function(self, func_name: str):
        """Fügt eine neue Funktion zum Graphen hinzu."""
        if func_name not in self.call_edges:
            logger.debug(f"Füge Funktion zum Graph hinzu: {func_name}")
            self.call_edges[func_name] = []
    
    def add_edge(self, from_func: str, to_func: str, compatible: bool = True):
        """
        Fügt eine gerichtete Kante zwischen zwei Funktionen hinzu.
        
        Args:
            from_func: Name der aufrufenden Funktion
            to_func: Name der aufgerufenen Funktion
            compatible: Ob die Funktionen semantisch kompatibel sind
        """
        # Stelle sicher, dass beide Funktionen im Graphen sind
        self.add_function(from_func)
        self.add_function(to_func)
        
        # Füge Kante hinzu, falls sie noch nicht existiert
        if to_func not in self.call_edges[from_func]:
            logger.debug(f"Füge Kante hinzu: {from_func} -> {to_func} (kompatibel: {compatible})")
            self.call_edges[from_func].append(to_func)
        
        # Setze Kompatibilität
        self.compatibility[(from_func, to_func)] = compatible
    
    def add_blacklist_pair(self, func1: str, func2: str):
        """Fügt ein Funktionspaar zur Blacklist hinzu."""
        logger.debug(f"Füge Blacklist-Paar hinzu: {func1} <-> {func2}")
        self.blacklist.add((func1, func2))
        self.blacklist.add((func2, func1))  # Symmetrisch
        
        # Auch als inkompatibel markieren
        self.compatibility[(func1, func2)] = False
        self.compatibility[(func2, func1)] = False
    
    def get_possible_next_functions(self, func_name: str) -> List[str]:
        """Gibt alle möglichen Folgefunktionen für eine gegebene Funktion zurück."""
        if func_name not in self.call_edges:
            return []
        return self.call_edges[func_name]
    
    def is_valid_chain(self, chain: List[str]) -> bool:
        """Prüft, ob eine Funktionskette valide ist (keine blacklisted Paare enthält)."""
        if not chain or len(chain) < 2:
            return True
        
        # Prüfe alle benachbarten Paare in der Kette
        for i in range(len(chain) - 1):
            from_func, to_func = chain[i], chain[i+1]
            
            # Überprüfe Blacklist
            if (from_func, to_func) in self.blacklist:
                logger.debug(f"Kette enthält Blacklist-Paar: {from_func} -> {to_func}")
                return False
            
            # Überprüfe, ob die Kante existiert und kompatibel ist
            if (from_func, to_func) in self.compatibility:
                if not self.compatibility[(from_func, to_func)]:
                    logger.debug(f"Kette enthält inkompatibles Paar: {from_func} -> {to_func}")
                    return False
            else:
                # Wenn keine Kante definiert ist, nehmen wir an, dass sie nicht kompatibel sind
                logger.debug(f"Kette enthält undefinierte Kante: {from_func} -> {to_func}")
                return False
                
        return True
    
    def generate_all_valid_chains(self, min_length: int = 4, max_length: int = 5) -> List[List[str]]:
        """
        Generiert alle validen Funktionsketten ohne Berücksichtigung von Wahrscheinlichkeiten.
        Berücksichtigt nur die Kompatibilität zwischen Funktionen.
        
        Args:
            min_length: Minimale Kettenlänge
            max_length: Maximale Kettenlänge
            
        Returns:
            Liste aller validen Funktionsketten
        """
        logger.info(f"Generiere alle validen Ketten (Länge {min_length} bis {max_length})")
        
        all_chains = []
        all_functions = list(self.call_edges.keys())
        
        logger.info(f"Arbeitsfunktionen: {len(all_functions)} Funktionen gefunden")
        
        # Für jede Länge zwischen min_length und max_length
        for length in range(min_length, max_length + 1):
            logger.info(f"Generiere Ketten der Länge {length}...")
            chains_for_length = []
            
            # Fortschrittsanzeige für die Startfunktionen
            all_functions_progress = tqdm(all_functions, desc=f"Startfunktionen (Länge {length})")
            
            # Starte mit jeder Funktion
            for start_func in all_functions_progress:
                # Verwende DFS, um alle möglichen Pfade zu finden
                def dfs(current_chain):
                    # Base case: Wenn die Kette die gewünschte Länge erreicht hat
                    if len(current_chain) == length:
                        chains_for_length.append(current_chain.copy())
                        # Log alle 1000 gefundenen Ketten
                        if len(chains_for_length) % 1000 == 0:
                            logger.debug(f"  Gefunden: {len(chains_for_length)} Ketten der Länge {length}")
                        return
                    
                    # Expandiere zu allen möglichen nächsten Funktionen
                    current_func = current_chain[-1]
                    for next_func in all_functions:
                        # Überspringe Funktionen, die bereits in der Kette sind (Zyklen vermeiden)
                        if next_func in current_chain:
                            continue
                        
                        # Überprüfe, ob der Übergang von current_func zu next_func valide ist
                        if (current_func, next_func) in self.blacklist:
                            continue
                            
                        if (current_func, next_func) in self.compatibility:
                            if not self.compatibility[(current_func, next_func)]:
                                continue
                        else:
                            # Wenn keine explizite Kompatibilität definiert ist, prüfen ob eine Kante existiert
                            if next_func not in self.call_edges.get(current_func, []):
                                continue
                        
                        # Füge die nächste Funktion hinzu und fahre rekursiv fort
                        current_chain.append(next_func)
                        dfs(current_chain)
                        current_chain.pop()  # Backtracking
                
                # Starte DFS mit dieser Startfunktion
                chains_before = len(chains_for_length)
                dfs([start_func])
                chains_after = len(chains_for_length)
                logger.debug(f"  Von {start_func} aus: {chains_after - chains_before} neue Ketten gefunden")
            
            # Füge alle Ketten dieser Länge hinzu
            all_chains.extend(chains_for_length)
            logger.info(f"Generiert {len(chains_for_length)} valide Ketten der Länge {length}")
        
        logger.info(f"Insgesamt {len(all_chains)} valide Ketten generiert")
        return all_chains


class FunctionFusionOptimizer:
    """
    Optimiert Function Fusion Konfigurationen basierend auf allen möglichen Parameterkombinationen.
    Schließt nur unrealistische Funktionsaufrufe aus.
    """
    
    def __init__(self, config_file="config/fusion_parameters.json", 
                 call_patterns_file="config/call_patterns.json",
                 test_data_file="config/test_data.json"):
        logger.info(f"Initialisiere FunctionFusionOptimizer")
        
        # Lade Hauptkonfiguration
        try:
            logger.info(f"Lade Konfigurationsdatei: {config_file}")
            with open(config_file, 'r') as f:
                self.params = json.load(f)
                logger.info(f"Konfiguration erfolgreich geladen: {len(self.params)} Parameter")
        except Exception as e:
            logger.exception(f"Fehler beim Laden der Konfiguration: {e}")
            # Fallback zu Standardkonfiguration
            self.params = self._get_default_params()
            logger.warning("Standard-Konfiguration wird verwendet")
        
        # Lade Aufrufmuster
        try:
            logger.info(f"Lade Aufrufmuster aus: {call_patterns_file}")
            with open(call_patterns_file, 'r') as f:
                self.call_patterns = json.load(f)
                logger.info(f"Aufrufmuster erfolgreich geladen: {len(self.call_patterns)} Funktionen")
        except Exception as e:
            logger.exception(f"Fehler beim Laden der Aufrufmuster: {e}")
            # Fallback zu leeren Aufrufmustern
            self.call_patterns = {}
            logger.warning("Keine Aufrufmuster verfügbar - es werden alle möglichen Kombinationen generiert")
        
        # Lade Testdaten
        try:
            logger.info(f"Lade Testdaten aus: {test_data_file}")
            with open(test_data_file, 'r') as f:
                self.test_data = json.load(f)
                logger.info(f"Testdaten erfolgreich geladen: {len(self.test_data)} Funktionen")
        except Exception as e:
            logger.exception(f"Fehler beim Laden der Testdaten: {e}")
            # Fallback zu leeren Testdaten
            self.test_data = {}
            logger.warning("Keine Testdaten verfügbar - es werden Standarddaten generiert")
        
        self.tester = None  # DockerFusionTester wird später initialisiert
        self.results = {}
        self.best_configs = []
        
        # Funktionsliste dynamisch ermitteln
        logger.info("Starte Funktionserkennung...")
        self.all_functions = self._discover_all_functions()
        logger.info(f"Gefundene Funktionen ({len(self.all_functions)}): {', '.join(self.all_functions)}")
        
        # Erstelle den Funktionsaufruf-Graphen
        logger.info("Erstelle Funktionsaufruf-Graph...")
        self.call_graph = self._build_function_call_graph()
        logger.info(f"Graph erstellt: {len(self.call_graph.call_edges)} Funktionen, " + 
                   f"{sum(len(e) for e in self.call_graph.call_edges.values())} Kanten, " +
                   f"{len(self.call_graph.blacklist)//2} Blacklist-Paare")
        
        # Memory-Konfigurationen für Funktionen
        self.function_memory_configs = self.params.get("function_memory_configs", {})
        
        # Standardwert für Funktionen ohne explizite Konfiguration
        self.default_memory_configs = [128, 256, 512, 1024]
        
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
        
        logger.info("FunctionFusionOptimizer initialisiert und bereit")
    
    def _get_default_params(self):
        """Liefert Standard-Parameter zurück, wenn keine Konfigurationsdatei verfügbar ist."""
        return {
            "function_memory_configs": {},
            "deployment": ["local"],
            "io_config": {
                "iterations": [1],
                "file_size_kb": [10],
                "enable_fsync": [False]
            },
            "network": {
                "latency_ms": [0],
                "loss_percent": [0],
                "bandwidth_kbit": [None]
            },
            "max_chain_length": 5,
            "min_chain_length": 2,
            "auto_discover_functions": True
        }
    
    def _discover_all_functions(self) -> List[str]:
        """Findet automatisch alle verfügbaren Funktionen im System."""
        # Zuerst prüfen, ob Funktionen in der Konfiguration angegeben sind
        if "functions" in self.params:
            logger.info("Verwende vorkonfigurierte Funktionsliste")
            return self.params["functions"]
        
        # Alternativ aus dem call_patterns extrahieren
        if self.call_patterns:
            functions = set(self.call_patterns.keys())
            for caller, details in self.call_patterns.items():
                functions.update(details.get("calls", []))
            if functions:
                logger.info(f"Extrahiere Funktionen aus call_patterns.json: {len(functions)} gefunden")
                return list(functions)
        
        # Alternativ aus test_data extrahieren
        if self.test_data:
            functions = list(self.test_data.keys())
            if functions:
                logger.info(f"Extrahiere Funktionen aus test_data.json: {len(functions)} gefunden")
                return functions
        
        # Andernfalls versuchen, sie automatisch zu erkennen
        functions = []
        
        # Erkennung basierend auf Docker-Funktionsordnern
        functions_dir = "functions/webshop"
        logger.info(f"Suche nach Funktionen in: {functions_dir}")
        
        if os.path.exists(functions_dir):
            logger.info(f"Verzeichnis {functions_dir} gefunden")
            functions = [d for d in os.listdir(functions_dir) 
                        if os.path.isdir(os.path.join(functions_dir, d))]
            logger.info(f"Gefunden: {len(functions)} Funktionen in {functions_dir}")
        else:
            logger.warning(f"Verzeichnis {functions_dir} nicht gefunden")
        
        if not functions:
            logger.info("Keine Funktionen gefunden, verwende Fallback-Liste")
            # Fallback: Hard-coded Liste
            functions = [
                "addcartitem", "cartkvstorage", "checkout", "currency", 
                "email", "emptycart", "frontend", "getads", "getcart", 
                "getproduct", "listproducts", "listrecommendations", 
                "payment", "searchproducts", "shipmentquote", "shiporder", 
                "supportedcurrencies"
            ]
            logger.info(f"Fallback-Liste enthält {len(functions)} Funktionen")
            
        return functions
    
    def _build_function_call_graph(self) -> FunctionCallGraph:
        """
        Erstellt einen gerichteten Graphen von Funktionsaufrufen
        basierend auf den Aufrufmustern in call_patterns.json.
        """
        logger.info("Erstelle Funktionsaufruf-Graph mit realistischen Aufrufbeziehungen")
        graph = FunctionCallGraph()
        
        # 1. Alle Funktionen hinzufügen
        for func in self.all_functions:
            graph.add_function(func)
        
        # 2. Kanten basierend auf call_patterns definieren
        if self.call_patterns:
            logger.info("Definiere Aufrufbeziehungen aus call_patterns.json")
            for caller, details in self.call_patterns.items():
                for callee in details.get("calls", []):
                    graph.add_edge(caller, callee, compatible=True)
                    logger.debug(f"Definiere Aufrufkante: {caller} -> {callee}")
        else:
            # Fallback: Hartcodierte Beziehungen definieren
            logger.info("Definiere hartcodierte Aufrufbeziehungen")
            
            # Frontend-Flows
            graph.add_edge("frontend", "listproducts")
            graph.add_edge("frontend", "getads")
            graph.add_edge("frontend", "getcart")
            graph.add_edge("frontend", "supportedcurrencies")
            graph.add_edge("frontend", "checkout")
            
            # Produkt-Flow
            graph.add_edge("listproducts", "getproduct")
            graph.add_edge("getproduct", "searchproducts")
            graph.add_edge("searchproducts", "getproduct")
            graph.add_edge("getproduct", "listrecommendations")
            
            # Warenkorb-Flow
            graph.add_edge("getcart", "cartkvstorage")
            graph.add_edge("addcartitem", "cartkvstorage")
            graph.add_edge("emptycart", "cartkvstorage")
            graph.add_edge("cartkvstorage", "getcart")
            
            # Checkout-Flow
            graph.add_edge("checkout", "getcart")
            graph.add_edge("checkout", "shipmentquote")
            graph.add_edge("checkout", "payment")
            graph.add_edge("checkout", "shiporder")
            graph.add_edge("checkout", "email")
            graph.add_edge("checkout", "emptycart")
            
            graph.add_edge("shipmentquote", "currency")
            graph.add_edge("payment", "currency")
        
        # 3. Definiere semantisch inkompatible Funktionspaare (Blacklist)
        logger.info("Definiere semantisch inkompatible Funktionspaare (Blacklist)")
        
        # Dies sind die unrealistischen Aufrufe, die ausgeschlossen werden sollen
        graph.add_blacklist_pair("addcartitem", "emptycart")
        graph.add_blacklist_pair("checkout", "addcartitem")
        graph.add_blacklist_pair("currency", "listproducts")
        graph.add_blacklist_pair("payment", "shipmentquote")
        graph.add_blacklist_pair("emptycart", "payment")
        graph.add_blacklist_pair("email", "getads")
        
        return graph
    
    def generate_fusion_groups(self, chains: List[List[str]], max_groups_per_chain: int = 10) -> Dict[str, List[List[List[str]]]]:
        """
        Generiert alle möglichen Fusionsgruppen für jede Funktionskette zur Evaluierung.
        
        Args:
            chains: Liste von Funktionsketten
            max_groups_per_chain: Maximale Anzahl von Fusionsgruppen pro Kette
            
        Returns:
            Dict mit Ketten als Schlüssel und Listen von Fusionsgruppen als Werten
        """
        logger.info(f"Generiere Fusionsgruppen für {len(chains)} Ketten")
        
        result = {}
        # Fortschrittsanzeige für die Verarbeitung aller Ketten
        chains_progress = tqdm(chains, desc="Generiere Fusionsgruppen")
        
        for i, chain in enumerate(chains_progress):
            chain_key = "->".join(chain)
            
            # Aktualisiere Fortschrittsanzeige mit aktueller Kette
            if i % 10 == 0:
                chains_progress.set_description(f"Generiere Fusionsgruppen [{i+1}/{len(chains)}]")
            
            # Verschiedene Fusionsstrategien generieren
            fusion_groups = []
            
            logger.debug(f"Verarbeite Kette {i+1}/{len(chains)}: {chain_key}")
            
            # 1. Alle benachbarten Paare testen
            for i in range(len(chain) - 1):
                fusion_groups.append([[chain[i], chain[i+1]]])
            
            # 2. Alle möglichen Triplets testen
            if len(chain) >= 3:
                for i in range(len(chain) - 2):
                    fusion_groups.append([[chain[i], chain[i+1], chain[i+2]]])
            
            # 3. Disjunkte Paare testen
            if len(chain) >= 4:
                for i in range(len(chain) - 3):
                    for j in range(i + 2, len(chain) - 1):
                        fusion_groups.append([[chain[i], chain[i+1]], [chain[j], chain[j+1]]])
            
            # 4. Baseline (keine Fusion) zum Vergleich
            fusion_groups.append([])
            
            # Begrenze die Anzahl der zu testenden Gruppen, wenn zu viele
            if len(fusion_groups) > max_groups_per_chain:
                logger.debug(f"  Zu viele Fusionsgruppen ({len(fusion_groups)}), reduziere auf {max_groups_per_chain}")
                # Immer Baseline behalten und den Rest zufällig auswählen
                baseline = []
                rest = [g for g in fusion_groups if g != []]
                selected = random.sample(rest, min(max_groups_per_chain - 1, len(rest)))
                fusion_groups = selected + [baseline]
                
            result[chain_key] = fusion_groups
            logger.debug(f"  Generiert: {len(fusion_groups)} Fusionsgruppen für diese Kette")
            
        total_groups = sum(len(groups) for groups in result.values())
        logger.info(f"Generierte insgesamt {total_groups} Fusionsgruppen für alle Ketten")
        
        return result
    
    def _generate_memory_configurations(self, chain: List[str], fusion_groups: List[List[str]]) -> List[Dict[str, int]]:
        """
        Generiert Memory-Konfigurationen für eine Funktionskette mit Fusionsgruppen.
        Verwendet alle Werte aus der Konfigurationsdatei.
        
        Args:
            chain: Die Funktionskette
            fusion_groups: Liste von Fusionsgruppen
            
        Returns:
            Liste von Memory-Konfigurationen für die Kette
        """
        logger.debug(f"Generiere Memory-Konfigurationen für Kette: {' -> '.join(chain)}")
        start_time = time.time()
        
        configs = []
        
        # Alle Konfigurationen aus der Parameterdatei verwenden
        for func in chain:
            memory_options = self.function_memory_configs.get(func, self.default_memory_configs)
            
            # Wenn noch keine Konfigurationen vorhanden, erstelle Basiskonfigurationen
            if not configs:
                configs = [{func: mem} for mem in memory_options]
                logger.debug(f"  Initialisiert mit {len(configs)} Basis-Konfigurationen für {func}")
            else:
                # Erweitere bestehende Konfigurationen
                new_configs = []
                for config in configs:
                    for mem in memory_options:
                        new_config = config.copy()
                        new_config[func] = mem
                        new_configs.append(new_config)
                
                configs = new_configs
                logger.debug(f"  Nach Hinzufügen von {func}: {len(configs)} Konfigurationen")
                
                # Wenn zu viele Konfigurationen, beschränke auf eine sinnvolle Anzahl
                if len(configs) > 50:
                    logger.debug(f"  Zu viele Konfigurationen ({len(configs)}), reduziere auf 50")
                    configs = random.sample(configs, 50)
        
        end_time = time.time()
        logger.debug(f"  Memory-Konfigurationen generiert: {len(configs)} in {end_time - start_time:.2f} Sekunden")
        return configs
    
    def generate_test_configurations(self, max_configs=None) -> List[Dict[str, Any]]:
        """
        Generiert Testkonfigurationen für alle Parameterkombinationen.
        Schließt nur unrealistische Funktionsaufrufe aus.
        
        Args:
            max_configs: Maximale Anzahl zu generierender Konfigurationen
            
        Returns:
            Liste von Testkonfigurationen
        """
        logger.info("Generiere Testkonfigurationen für alle Parameterkombinationen")
        start_time = time.time()
        
        # 1. Alle validen Ketten generieren
        logger.info("Starte Generierung valider Funktionsketten...")
        chains = self.call_graph.generate_all_valid_chains(
            min_length=self.params.get("min_chain_length", 2),
            max_length=self.params.get("max_chain_length", 5)
        )
        
        # Wenn zu viele Ketten, beschränke die Anzahl
        if len(chains) > 100:
            logger.info(f"Beschränke die Anzahl der Ketten von {len(chains)} auf 100 (zufällige Auswahl)")
            chains = random.sample(chains, 100)
        
        # 2. Fusionsgruppen für jede Kette generieren
        logger.info("Generiere Fusionsgruppen für die Ketten...")
        chain_fusion_groups = self.generate_fusion_groups(chains)
        
        # 3. Testkonfigurationen für jede Kette und Fusionsgruppe erstellen
        logger.info("Erstelle Testkonfigurationen für alle Parameterkombinationen...")
        configs = []
        
        # Fortschritt für Ketten
        chains_progress = tqdm(chains, desc="Verarbeite Ketten")
        
        for chain in chains_progress:
            chain_key = "->".join(chain)
            fusion_groups_list = chain_fusion_groups.get(chain_key, [[]])
            
            logger.debug(f"Verarbeite Kette: {chain_key}")
            logger.debug(f"  {len(fusion_groups_list)} Fusionsgruppen gefunden")
            
            # Fortschritt für Fusionsgruppen innerhalb einer Kette
            for fusion_groups in fusion_groups_list:
                # Memory-Konfigurationen generieren
                memory_configs = self._generate_memory_configurations(chain, fusion_groups)
                
                # Zähler für erstellte Konfigurationen
                created_configs_count = 0
                
                # Vollständiges kartesisches Produkt aller Parameter
                for memory_config in memory_configs:
                    for deploy in self.params["deployment"]:
                        for iterations in self.params["io_config"]["iterations"]:
                            for file_size in self.params["io_config"]["file_size_kb"]:
                                for fsync in self.params["io_config"]["enable_fsync"]:
                                    for latency in self.params["network"]["latency_ms"]:
                                        for loss in self.params["network"]["loss_percent"]:
                                            bandwidths = self.params["network"].get("bandwidth_kbit", [None])
                                            for bandwidth in bandwidths:
                                                config = {
                                                    "id": len(configs),
                                                    "type": "fusion_test",
                                                    "chain": chain,
                                                    "fusion_groups": fusion_groups,
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
                                                created_configs_count += 1
                
                logger.debug(f"  Für Fusionsgruppe {fusion_groups}: {created_configs_count} Konfigurationen erstellt")
        
        self.total_tests = len(configs)
        end_time = time.time()
        logger.info(f"Generiert: {self.total_tests} Testkonfigurationen in {end_time - start_time:.2f} Sekunden")
        
        # Bei Bedarf Anzahl der Tests begrenzen durch zufällige Auswahl
        if max_configs and len(configs) > max_configs:
            logger.info(f"Reduziere auf {max_configs} Testkonfigurationen durch zufällige Auswahl")
            configs = random.sample(configs, max_configs)
            self.total_tests = len(configs)
            
        return configs
    
    async def run_tests(self, test_configurations):
        """Führt Tests für alle Konfigurationen aus."""
        logger.info(f"Starte Tests für {len(test_configurations)} Konfigurationen")
        
        logger.info("Initialisiere DockerFusionTester...")
        try:
            from docker_fusion_tester import DockerFusionTester
            self.tester = DockerFusionTester()
            await self.tester.setup()
            logger.info("DockerFusionTester erfolgreich initialisiert")
        except Exception as e:
            logger.exception(f"Fehler bei Initialisierung des DockerFusionTester: {e}")
            raise
        
        try:
            # Fortschrittsanzeige
            logger.info("Starte Testausführung...")
            progress_bar = tqdm(total=len(test_configurations), desc="Tests")
            
            # Tests ausführen
            for i, config in enumerate(test_configurations):
                logger.info(f"==> Test {i+1}/{len(test_configurations)} (ID: {config['id']}) läuft...")
                try:
                    # Detaillierte Informationen zum aktuellen Test
                    logger.info(f"  Kette: {' -> '.join(config['chain'])}")
                    if config['fusion_groups']:
                        groups_str = ", ".join(["+".join(group) for group in config['fusion_groups']])
                        logger.info(f"  Fusionsgruppen: {groups_str}")
                    else:
                        logger.info("  Keine Fusion (Baseline)")
                    
                    # Führe Test aus
                    start_time = time.time()
                    result = await self._run_fusion_test(config)
                    end_time = time.time()
                    
                    # Protokolliere Ergebnis
                    test_duration = end_time - start_time
                    speedup = result.get("speedup_factor", 0)
                    logger.info(f"  ✓ Test abgeschlossen in {test_duration:.2f}s, Speedup: {speedup:.2f}x")
                    
                    # Speichere Ergebnis
                    config_key = str(config["id"])
                    self.results[config_key] = result
                    
                    # Fortschritt aktualisieren
                    self.progress += 1
                    progress_bar.update(1)
                    
                    # Speichere Zwischenergebnisse
                    if self.progress % 10 == 0:
                        logger.info(f"Speichere Zwischenergebnisse nach {self.progress} Tests...")
                        self._save_results()
                        
                except Exception as e:
                    logger.error(f"Fehler bei Test {config['id']}: {e}")
                    logger.error(f"Stack Trace: {traceback.format_exc()}")
                    # Fehlschlag protokollieren aber weitermachen
                    progress_bar.update(1)
                    self.progress += 1
            
            progress_bar.close()
            
            # Sortiere und speichere die besten Konfigurationen
            logger.info("Alle Tests abgeschlossen, aktualisiere beste Konfigurationen...")
            self._update_best_configs()
            self._save_results()
            logger.info("Ergebnisse gespeichert.")
            
        finally:
            logger.info("Bereinige DockerFusionTester...")
            await self.tester.cleanup()
    
    async def run_tests_parallel(self, test_configurations, max_workers=8):
        """Führt Tests parallel aus."""
        logger.info(f"Starte parallele Tests mit {max_workers} Workern")
        
        logger.info("Initialisiere DockerFusionTester...")
        try:
            from docker_fusion_tester import DockerFusionTester
            self.tester = DockerFusionTester()
            await self.tester.setup()
            logger.info("DockerFusionTester erfolgreich initialisiert")
        except Exception as e:
            logger.exception(f"Fehler bei Initialisierung des DockerFusionTester: {e}")
            raise
        
        try:
            # Teile die Tests in Chunks
            total = len(test_configurations)
            chunk_size = max(1, total // max_workers)
            chunks = [test_configurations[i:i + chunk_size] 
                     for i in range(0, total, chunk_size)]
            
            logger.info(f"Tests in {len(chunks)} Chunks aufgeteilt, je ~{chunk_size} Tests pro Worker")
            
            # Erstelle Worker-Pools
            semaphore = asyncio.Semaphore(max_workers)
            
            async def worker(worker_id, chunk):
                logger.info(f"Worker {worker_id} gestartet mit {len(chunk)} Tests")
                result_dict = {}
                
                async with semaphore:
                    # Fortschrittsanzeige für diesen Worker
                    worker_progress = tqdm(chunk, desc=f"Worker {worker_id}", position=worker_id)
                    
                    for config in worker_progress:
                        try:
                            logger.info(f"Worker {worker_id}: Test {config['id']} läuft...")
                            start_time = time.time()
                            result = await self._run_fusion_test(config)
                            end_time = time.time()
                            
                            # Log Ergebnis
                            test_duration = end_time - start_time
                            speedup = result.get("speedup_factor", 0)
                            logger.info(f"Worker {worker_id}: Test {config['id']} abgeschlossen " + 
                                      f"in {test_duration:.2f}s, Speedup: {speedup:.2f}x")
                            
                            result_dict[str(config["id"])] = result
                            worker_progress.set_description(f"Worker {worker_id} ({len(result_dict)}/{len(chunk)})")
                        except Exception as e:
                            logger.error(f"Worker {worker_id}: Fehler bei Test {config['id']}: {e}")
                            logger.error(f"Stack Trace: {traceback.format_exc()}")
                
                logger.info(f"Worker {worker_id} beendet: {len(result_dict)}/{len(chunk)} Tests erfolgreich")
                return result_dict
            
            # Starte Tasks
            logger.info(f"Starte {len(chunks)} Worker-Tasks...")
            tasks = [asyncio.create_task(worker(i, chunk)) for i, chunk in enumerate(chunks)]
            
            # Sammle Ergebnisse
            results_progress = tqdm(total=len(tasks), desc="Sammle Ergebnisse")
            
            for i, task in enumerate(asyncio.as_completed(tasks)):
                logger.info(f"Warte auf Ergebnisse von Worker {i+1}/{len(tasks)}...")
                try:
                    results = await task
                    # Füge Ergebnisse zum Hauptdict hinzu
                    result_count = len(results)
                    logger.info(f"Worker {i+1} abgeschlossen: {result_count} Ergebnisse erhalten")
                    self.results.update(results)
                    self.progress += result_count
                    
                    # Speichere Zwischenergebnisse
                    if self.progress % 10 == 0:
                        logger.info(f"Speichere Zwischenergebnisse nach {self.progress} Tests...")
                        self._save_results()
                        
                except Exception as e:
                    logger.error(f"Fehler beim Verarbeiten der Ergebnisse von Worker {i+1}: {e}")
                    logger.error(f"Stack Trace: {traceback.format_exc()}")
                
                results_progress.update(1)
            
            results_progress.close()
            
            # Aktualisiere beste Konfigurationen
            logger.info("Alle Worker abgeschlossen, aktualisiere beste Konfigurationen...")
            self._update_best_configs()
            self._save_results()
            logger.info(f"Alle Tests abgeschlossen: {self.progress} Tests durchgeführt, Ergebnisse gespeichert")
            
        finally:
            logger.info("Bereinige DockerFusionTester...")
            await self.tester.cleanup()
    
    async def _run_fusion_test(self, config):
        """
        Führt einen Fusionstest für eine Funktionskette mit Fusionsgruppen durch.
        Verwendet die Testdaten aus test_data.json.
        
        Args:
            config: Die Testkonfiguration
            
        Returns:
            Testergebnis mit Performance-Metriken
        """
        # Extrahiere Konfigurationen
        chain = config["chain"]
        fusion_groups = config["fusion_groups"]
        memory_config = config["memory_config"]
        
        logger.debug(f"Führe Test {config['id']} aus: {'-'.join(chain)}")
        
        if not chain:
            logger.warning(f"Test {config['id']}: Leere Funktionskette")
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
        logger.debug(f"Test {config['id']}: Konfiguriere Memory für {len(memory_config)} Funktionen")
        for func_name, memory in memory_config.items():
            try:
                logger.debug(f"  Setze Memory für {func_name}: {memory}MB")
                await self.tester.update_function_config(func_name, {"MEMORY_SIZE": str(memory)})
            except Exception as e:
                logger.warning(f"  ⚠️ Konnte Memory für {func_name} nicht setzen: {e}")
        
        # Netzwerk-Konfiguration für die beteiligten Funktionen setzen
        logger.debug(f"Test {config['id']}: Konfiguriere Netzwerk für {len(chain)} Funktionen")
        logger.debug(f"  Netzwerkkonfiguration: {network_config}")
        for func_name in chain:
            try:
                logger.debug(f"  Konfiguriere Netzwerk für {func_name}")
                await self.tester.update_network_config(func_name, network_config)
            except Exception as e:
                logger.warning(f"  ⚠️ Konnte Netzwerk für {func_name} nicht konfigurieren: {e}")
        
        # Start timing
        start_time = time.time()
        
        # Baseline-Test (ohne Fusion)
        logger.debug(f"Test {config['id']}: Starte Baseline-Test")
        baseline_results = await self._run_baseline_test(chain, io_params, config["id"])
        logger.debug(f"Test {config['id']}: Baseline-Test abgeschlossen, Zeit: {baseline_results.get('total_time_ms', 0):.2f}ms")
        
        # Fusion-Test
        logger.debug(f"Test {config['id']}: Starte Fusion-Test")
        fusion_results = await self._run_fusion_chain(chain, fusion_groups, io_params, config["id"])
        logger.debug(f"Test {config['id']}: Fusion-Test abgeschlossen, Zeit: {fusion_results.get('total_time_ms', 0):.2f}ms")
        
        # End timing
        end_time = time.time()
        
        # Berechne Performance-Metriken
        baseline_time = baseline_results.get("total_time_ms", 0)
        fusion_time = fusion_results.get("total_time_ms", 0)
        
        # Berechne Speedup
        speedup = baseline_time / fusion_time if fusion_time > 0 else 0
        
        # Ressourcennutzung berechnen (vereinfacht)
        resource_usage_percent = fusion_results.get("resource_usage_percent", 0)
        
        # Ergebnis zusammenstellen
        result = {
            "config": config,
            "baseline_time_ms": baseline_time,
            "fusion_time_ms": fusion_time,
            "speedup_factor": speedup,
            "test_duration_ms": (end_time - start_time) * 1000,
            "average_latency_ms": fusion_time,
            "requests_per_second": 1000 / fusion_time if fusion_time > 0 else 0,
            "resource_usage_percent": resource_usage_percent,
            "baseline_results": baseline_results,
            "fusion_results": fusion_results,
            "timestamp": time.time()
        }
        
        logger.debug(f"Test {config['id']} abgeschlossen: Speedup={speedup:.2f}x")
        return result
    
    async def _run_baseline_test(self, chain, io_params, config_id):
        """
        Führt einen Baseline-Test ohne Fusion durch.
        Verwendet Testdaten aus test_data.json.
        
        Args:
            chain: Die Funktionskette
            io_params: I/O-Parameter
            config_id: ID der Testkonfiguration
            
        Returns:
            Ergebnis des Baseline-Tests
        """
        logger.debug(f"Baseline-Test für ID {config_id}: {len(chain)} Funktionen einzeln aufrufen")
        results = {}
        total_time = 0
        
        # Rufe jede Funktion einzeln auf
        for i, func_name in enumerate(chain):
            logger.debug(f"  Baseline: Rufe Funktion {i+1}/{len(chain)} auf: {func_name}")
            
            # Hole Testdaten für diese Funktion
            input_data = self._get_test_data_for_function(func_name, config_id, i)
            
            # Füge I/O-Parameter für Tests hinzu
            input_data["io_params"] = io_params
            
            # Rufe die Funktion auf
            try:
                start_time = time.time()
                result = await self.tester.invoke_function(func_name, input_data)
                end_time = time.time()
                
                execution_time = result.get("execution_time_ms", 0)
                logger.debug(f"  Baseline: {func_name} abgeschlossen in {execution_time:.2f}ms")
                
                results[func_name] = result
                
                # Addiere Ausführungszeit
                total_time += execution_time
            except Exception as e:
                logger.error(f"  ❌ Baseline: Fehler beim Aufruf von {func_name}: {e}")
                # Fallback-Wert für Fehlerfall
                results[func_name] = {"error": str(e), "execution_time_ms": 0}
        
        logger.debug(f"Baseline-Test abgeschlossen: Gesamtzeit = {total_time:.2f}ms")
        return {
            "function_results": results,
            "total_time_ms": total_time
        }
    
    async def _run_fusion_chain(self, chain, fusion_groups, io_params, config_id):
        """
        Führt einen Test mit Fusion für die Funktionskette durch.
        Verwendet Testdaten aus test_data.json.
        
        Args:
            chain: Die Funktionskette
            fusion_groups: Liste von Fusionsgruppen
            io_params: I/O-Parameter
            config_id: ID der Testkonfiguration
            
        Returns:
            Ergebnis des Fusionstests
        """
        # Formatiere die Fusionsgruppen für bessere Lesbarkeit
        fusion_str = "keine" if not fusion_groups else ", ".join(["+".join(group) for group in fusion_groups])
        logger.debug(f"Fusion-Test für ID {config_id}: Kette mit {len(chain)} Funktionen, Fusion: {fusion_str}")
        
        results = {}
        total_time = 0
        resource_usage_percent = 0
        
        # Flache Liste aller Funktionen in Fusionsgruppen
        flat_fusion_funcs = set()
        for group in fusion_groups:
            for func in group:
                flat_fusion_funcs.add(func)
        
        # Verarbeite die Kette sequenziell, fasse aber Funktionen in Fusionsgruppen zusammen
        i = 0
        while i < len(chain):
            current_func = chain[i]
            
            # Suche nach der Fusionsgruppe, die diese Funktion enthält (falls vorhanden)
            fusion_group = None
            for group in fusion_groups:
                if current_func in group:
                    fusion_group = group
                    break
            
            if fusion_group:
                # Dies ist Teil einer Fusionsgruppe - rufe die erste Funktion der Gruppe auf
                group_start_func = fusion_group[0]
                group_str = "+".join(fusion_group)
                
                logger.debug(f"  Fusion: Rufe Fusionsgruppe auf: {group_str} (startet mit {group_start_func})")
                
                # Hole Testdaten für die erste Funktion in der Gruppe
                input_data = self._get_test_data_for_function(group_start_func, config_id, i)
                
                # Füge I/O-Parameter und Fusionsgruppe hinzu
                input_data["io_params"] = io_params
                input_data["fusion_group"] = fusion_group
                
                try:
                    # Rufe die erste Funktion der Gruppe auf, um die Fusion zu simulieren
                    start_time = time.time()
                    result = await self.tester.invoke_function(group_start_func, input_data)
                    end_time = time.time()
                    
                    execution_time = result.get("execution_time_ms", 0)
                    logger.debug(f"  Fusion: Gruppe {group_str} abgeschlossen in {execution_time:.2f}ms")
                    
                    group_key = "_".join(fusion_group)
                    results[group_key] = result
                    
                    # Addiere Ausführungszeit
                    total_time += execution_time
                    
                    # Verfolge Ressourcennutzung
                    if "body" in result and isinstance(result["body"], dict):
                        perf = result["body"].get("performance", {})
                        if isinstance(perf, dict):
                            usage = perf.get("cpu_usage_percent", 0)
                            resource_usage_percent += usage
                            logger.debug(f"  Fusion: CPU-Nutzung für Gruppe {group_str}: {usage:.1f}%")
                    
                    # Überspringe alle Funktionen in dieser Gruppe
                    skipped = len(fusion_group) - 1
                    logger.debug(f"  Fusion: Überspringe {skipped} weitere Funktionen in dieser Gruppe")
                    i += len(fusion_group)
                    
                except Exception as e:
                    logger.error(f"  ❌ Fusion: Fehler beim Aufruf der Fusionsgruppe {group_str}: {e}")
                    logger.error(f"  Stack Trace: {traceback.format_exc()}")
                    results[f"fusion_group_{i}"] = {"error": str(e), "execution_time_ms": 0}
                    i += len(fusion_group)
            else:
                # Keine Fusion für diese Funktion - rufe sie einzeln auf
                logger.debug(f"  Fusion: Rufe einzelne Funktion auf: {current_func} (keine Fusionsgruppe)")
                
                # Hole Testdaten für diese Funktion
                input_data = self._get_test_data_for_function(current_func, config_id, i)
                
                # Füge I/O-Parameter hinzu
                input_data["io_params"] = io_params
                
                try:
                    start_time = time.time()
                    result = await self.tester.invoke_function(current_func, input_data)
                    end_time = time.time()
                    
                    execution_time = result.get("execution_time_ms", 0)
                    logger.debug(f"  Fusion: Einzelfunktion {current_func} abgeschlossen in {execution_time:.2f}ms")
                    
                    results[current_func] = result
                    
                    # Addiere Ausführungszeit
                    total_time += execution_time
                
                except Exception as e:
                    logger.error(f"  ❌ Fusion: Fehler beim Aufruf von {current_func}: {e}")
                    logger.error(f"  Stack Trace: {traceback.format_exc()}")
                    results[current_func] = {"error": str(e), "execution_time_ms": 0}
                
                i += 1
        
        # Normalisiere Ressourcennutzung
        if fusion_groups:
            resource_usage_percent /= len(fusion_groups)
        
        logger.debug(f"Fusion-Test abgeschlossen: Gesamtzeit = {total_time:.2f}ms, Ressourcennutzung = {resource_usage_percent:.1f}%")
        return {
            "function_results": results,
            "total_time_ms": total_time,
            "resource_usage_percent": resource_usage_percent
        }
    
    def _get_test_data_for_function(self, func_name, config_id, position):
        """
        Holt Testdaten für eine bestimmte Funktion aus test_data.json.
        
        Args:
            func_name: Name der Funktion
            config_id: ID der Testkonfiguration (für eindeutige IDs)
            position: Position der Funktion in der Kette (für eindeutige IDs)
            
        Returns:
            Testdaten für die Funktion
        """
        # Standard-Testdaten falls nichts Spezifisches gefunden wird
        default_data = {
            "operation": "test",
            "userId": f"test_{config_id}_{position}"
        }
        
        # Spezifische Testdaten aus der JSON-Datei
        if func_name in self.test_data:
            # Direkte Daten verwenden
            func_data = self.test_data.get(func_name, {})
            
            # Spezialfälle für Funktionen mit verschiedenen Operationen
            if isinstance(func_data, dict) and any(op in func_data for op in ["add", "get", "empty"]):
                # Bei cartkvstorage oder ähnlichen mit mehreren Operationen
                operation = "get"  # Standard-Operation
                if "add" in func_data:
                    operation = "add"
                
                func_data = func_data.get(operation, {})
            
            # Tiefe Kopie erstellen und mit Default-Daten verbinden
            result = default_data.copy()
            if isinstance(func_data, dict):
                result.update(func_data)
            
            # Eindeutige ID einfügen
            result["userId"] = f"test_{config_id}_{position}"
            
            return result
        
        return default_data
    
    def _calculate_fitness(self, result):
        """Berechnet den Fitness-Wert eines Testergebnisses."""
        # Gewichtete Summe verschiedener Metriken
        speedup_fitness = self.fitness_functions["speedup"](result) * 2.0  # Doppelte Gewichtung
        latency_fitness = self.fitness_functions["latency"](result)
        throughput_fitness = self.fitness_functions["throughput"](result)
        resource_fitness = self.fitness_functions["resource_usage"](result)
        
        # Gewichtung der verschiedenen Aspekte
        fitness = (
            0.4 * speedup_fitness + 
            0.3 * latency_fitness + 
            0.2 * throughput_fitness + 
            0.1 * resource_fitness
        )
        
        logger.debug(f"Fitness berechnet: {fitness:.2f} (Speedup: {result.get('speedup_factor', 0):.2f}x)")
        return fitness
    
    def _update_best_configs(self):
        """Aktualisiert die Liste der besten Konfigurationen basierend auf den Testergebnissen."""
        logger.info("Aktualisiere Liste der besten Konfigurationen...")
        
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
        
        logger.info(f"Beste Konfiguration hat Fitness-Score: {sorted_configs[0][1]:.2f} " if sorted_configs else "Keine Ergebnisse")
        
        # Wähle die besten Konfigurationen
        self.best_configs = [
            self.results[config_key]["config"]
            for config_key, _ in sorted_configs[:10]  # Top 10
        ]
        
        logger.info(f"{len(self.best_configs)} beste Konfigurationen ausgewählt")
    
    def _save_results(self):
        """Speichert die Testergebnisse und besten Konfigurationen."""
        # Speichere alle Ergebnisse
        os.makedirs("results", exist_ok=True)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        
        results_file = f"results/fusion_results_{timestamp}.json"
        best_configs_file = f"results/best_configs_{timestamp}.json"
        
        logger.info(f"Speichere Ergebnisse in {results_file}")
        with open(results_file, "w") as f:
            json.dump({
                "timestamp": time.time(),
                "progress": self.progress,
                "total_tests": self.total_tests,
                "results": self.results,
                "best_configs": self.best_configs
            }, f, indent=2)
        
        # Speichere beste Konfigurationen separat
        logger.info(f"Speichere beste Konfigurationen in {best_configs_file}")
        with open(best_configs_file, "w") as f:
            json.dump({
                "timestamp": time.time(),
                "best_configs": self.best_configs
            }, f, indent=2)
        
        logger.info("Ergebnisse erfolgreich gespeichert")
    
    def analyze_results(self):
        """Analysiert die Testergebnisse und generiert einen Bericht."""
        if not self.results:
            logger.warning("Keine Testergebnisse vorhanden für Analyse")
            return "Keine Testergebnisse vorhanden."
        
        logger.info(f"Analysiere {len(self.results)} Testergebnisse...")
        
        report = {
            "summary": {
                "total_tests": len(self.results),
                "average_speedup": 0,
                "max_speedup": 0,
                "best_config": None
            },
            "chain_performance": {},
            "fusion_performance": {},
            "memory_performance": {},
            "io_performance": {},
            "network_performance": {}
        }

        # Berechne Summary-Statistiken
        logger.info("Berechne Summary-Statistiken...")
        speedups = []
        for result in self.results.values():
            speedup = result.get("speedup_factor", 0)
            speedups.append(speedup)

            if speedup > report["summary"]["max_speedup"]:
                report["summary"]["max_speedup"] = speedup
                report["summary"]["best_config"] = result["config"]

        report["summary"]["average_speedup"] = sum(speedups) / len(speedups) if speedups else 0
        logger.info(f"Durchschnittlicher Speedup: {report['summary']['average_speedup']:.2f}x")
        logger.info(f"Maximaler Speedup: {report['summary']['max_speedup']:.2f}x")

        # Analysiere Chain-Performance
        logger.info("Analysiere Performance nach Funktionsketten...")
        chain_data = {}
        for result in self.results.values():
            config = result["config"]
            chain_str = "->".join(config["chain"])
            chain_data.setdefault(chain_str, []).append(result.get("speedup_factor", 0))

        report["chain_performance"] = {
            chain: {
                "avg_speedup": sum(vals) / len(vals),
                "count": len(vals)
            }
            for chain, vals in chain_data.items()
        }
        logger.info(f"Performance für {len(chain_data)} verschiedene Funktionsketten analysiert")

        # Analysiere Fusionsgruppen-Performance
        logger.info("Analysiere Performance nach Fusionsgruppen...")
        fusion_data = {}
        for result in self.results.values():
            config = result["config"]
            
            # Erstelle eine String-Repräsentation der Fusionsgruppen
            if config["fusion_groups"]:
                fusion_str = "|".join(["_".join(group) for group in config["fusion_groups"]])
            else:
                fusion_str = "no_fusion"
                
            fusion_data.setdefault(fusion_str, []).append(result.get("speedup_factor", 0))

        report["fusion_performance"] = {
            fusion: {
                "avg_speedup": sum(vals) / len(vals),
                "count": len(vals)
            }
            for fusion, vals in fusion_data.items()
        }
        logger.info(f"Performance für {len(fusion_data)} verschiedene Fusionsgruppen analysiert")

        # Analysiere Memory-Performance
        logger.info("Analysiere Performance nach Memory-Konfigurationen...")
        memory_data = {}
        for result in self.results.values():
            config = result["config"]
            
            # Vereinfache Memory-Konfiguration zu einem String
            # Wir verwenden hier nur die durchschnittliche Memory-Zuordnung
            avg_memory = sum(config["memory_config"].values()) / len(config["memory_config"])
            memory_key = f"avg_{int(avg_memory)}MB"
            
            memory_data.setdefault(memory_key, []).append(result.get("speedup_factor", 0))

        report["memory_performance"] = {
            memory: {
                "avg_speedup": sum(vals) / len(vals),
                "count": len(vals)
            }
            for memory, vals in memory_data.items()
        }
        logger.info(f"Performance für {len(memory_data)} verschiedene Memory-Konfigurationen analysiert")

        # Analysiere I/O-Performance
        logger.info("Analysiere Performance nach I/O-Konfigurationen...")
        io_data = {}
        for result in self.results.values():
            config = result["config"]
            iterations = config["io_config"]["iterations"]
            file_size = config["io_config"]["file_size_kb"]
            key = f"iter_{iterations}_size_{file_size}"
            io_data.setdefault(key, []).append(result.get("speedup_factor", 0))

        report["io_performance"] = {
            key: {
                "avg_speedup": sum(vals) / len(vals),
                "count": len(vals)
            }
            for key, vals in io_data.items()
        }
        logger.info(f"Performance für {len(io_data)} verschiedene I/O-Konfigurationen analysiert")

        # Analysiere Network-Performance
        logger.info("Analysiere Performance nach Netzwerk-Konfigurationen...")
        network_data = {}
        for result in self.results.values():
            config = result["config"]
            net = config.get("network", {})
            latency = net.get("latency_ms", 0)
            loss = net.get("loss_percent", 0)
            bw = net.get("bandwidth_kbit", "unlimited")
            key = f"lat_{latency}_loss_{loss}_bw_{bw}"
            network_data.setdefault(key, []).append(result.get("speedup_factor", 0))

        report["network_performance"] = {
            key: {
                "avg_speedup": sum(vals) / len(vals),
                "count": len(vals)
            }
            for key, vals in network_data.items()
        }
        logger.info(f"Performance für {len(network_data)} verschiedene Netzwerk-Konfigurationen analysiert")

        # Extrahiere Top-Konfigurationen
        logger.info("Extrahiere Top-Konfigurationen...")
        top_configs = []
        for _, result in sorted(
            self.results.items(),
            key=lambda x: x[1].get("speedup_factor", 0),
            reverse=True
        )[:5]:
            config = result["config"]
            top_configs.append({
                "chain": "->".join(config["chain"]),
                "fusion_groups": [["->".join(group) for group in config["fusion_groups"]]],
                "memory": config["memory_config"],
                "speedup": result.get("speedup_factor", 0),
                "latency_ms": result.get("fusion_time_ms", 0)
            })

        report["top_configs"] = top_configs
        logger.info(f"Top 5 Konfigurationen mit Speedups von {top_configs[0]['speedup']:.2f}x bis {top_configs[-1]['speedup']:.2f}x")
        
        # Identifiziere die besten Fusionskandidaten
        logger.info("Identifiziere beste Fusionskandidaten...")
        report["best_fusion_candidates"] = self.identify_best_fusion_candidates()
        logger.info(f"{len(report['best_fusion_candidates'])} beste Fusionskandidaten identifiziert")

        logger.info(f"Analyse abgeschlossen: Durchschnittlicher Speedup = {report['summary']['average_speedup']:.2f}x")
        return report
    
    def identify_best_fusion_candidates(self):
        """
        Analysiert Testergebnisse, um die besten Fusionskandidaten zu identifizieren.
        """
        logger.info("Analysiere Testergebnisse für beste Fusionskandidaten...")
        fusion_performance = {}
        
        # Analysiere alle Testergebnisse
        for result_id, result in self.results.items():
            config = result.get("config", {})
            fusion_groups = config.get("fusion_groups", [])
            
            # Überspringe Baseline-Tests
            if not fusion_groups:
                continue
                
            # Analysiere jede Fusionsgruppe einzeln
            for group in fusion_groups:
                # Erstelle einen Identifikator für diese Fusionsgruppe
                group_id = "_".join(group)
                
                # Sammle Performance-Metriken
                speedup = result.get("speedup_factor", 0)
                
                if group_id not in fusion_performance:
                    fusion_performance[group_id] = {
                        "speedups": [],
                        "count": 0,
                        "functions": group
                    }
                    
                fusion_performance[group_id]["speedups"].append(speedup)
                fusion_performance[group_id]["count"] += 1
        
        # Berechne durchschnittlichen Speedup für jede Fusionsgruppe
        logger.info(f"Berechne durchschnittlichen Speedup für {len(fusion_performance)} Fusionsgruppen...")
        for group_id, metrics in fusion_performance.items():
            if metrics["speedups"]:
                metrics["avg_speedup"] = sum(metrics["speedups"]) / len(metrics["speedups"])
                logger.debug(f"Fusionsgruppe {group_id}: Avg Speedup = {metrics['avg_speedup']:.2f}x, {metrics['count']} Tests")
            else:
                metrics["avg_speedup"] = 0
        
        # Sortiere nach durchschnittlichem Speedup
        sorted_fusions = sorted(
            fusion_performance.items(),
            key=lambda x: x[1]["avg_speedup"],
            reverse=True
        )
        
        # Liste der besten Fusionskandidaten
        best_candidates = []
        for group_id, metrics in sorted_fusions[:10]:  # Top 10
            best_candidates.append({
                "functions": metrics["functions"],
                "avg_speedup": metrics["avg_speedup"],
                "test_count": metrics["count"]
            })
            logger.info(f"Top Fusion: {'+'.join(metrics['functions'])}: {metrics['avg_speedup']:.2f}x Speedup ({metrics['count']} Tests)")
        
        logger.info(f"Identifiziert: {len(best_candidates)} beste Fusionskandidaten")
        return best_candidates


class DockerFusionTester:
    """Führt Tests mit Docker-basierten Funktionen durch."""
    
    def __init__(self, services_url_base="http://localhost"):
        self.services_url_base = services_url_base
        self.http_client = None
        logger.info(f"DockerFusionTester initialisiert mit URL-Basis: {services_url_base}")
    
    async def setup(self):
        """Initialisiert den Tester."""
        logger.info("Initialisiere HTTP-Client für DockerFusionTester...")
        self.http_client = httpx.AsyncClient(timeout=30.0)
        logger.info("DockerFusionTester bereit")
    
    async def cleanup(self):
        """Räumt Ressourcen auf."""
        if self.http_client:
            logger.info("Schließe HTTP-Client...")
            await self.http_client.aclose()
            logger.info("HTTP-Client geschlossen")
    
    async def invoke_function(self, function_name, event_data):
        """Ruft eine Funktion auf und gibt das Ergebnis zurück."""
        # Service-Port bestimmen
        service_name = function_name.lower().replace("_", "-")
        url = f"{self.services_url_base}:{self._get_service_port(service_name)}/invoke"
        
        logger.debug(f"Rufe Funktion auf: {function_name}, URL: {url}")
        
        # Aufruf durchführen
        try:
            start_time = asyncio.get_event_loop().time()
            logger.debug(f"HTTP-Anfrage an {url} gesendet")
            response = await self.http_client.post(url, json=event_data)
            end_time = asyncio.get_event_loop().time()
            
            if response.status_code == 200:
                result = response.json()
                # Ausführungszeit hinzufügen
                execution_time = (end_time - start_time) * 1000  # ms
                result["execution_time_ms"] = execution_time
                logger.debug(f"Funktion {function_name} erfolgreich aufgerufen: {execution_time:.2f}ms")
                return result
            else:
                logger.warning(f"Funktion {function_name} lieferte Status {response.status_code}")
                return {
                    "error": f"Status {response.status_code}",
                    "execution_time_ms": (end_time - start_time) * 1000
                }
                
        except httpx.ReadTimeout:
            logger.error(f"Timeout beim Aufruf von {function_name}")
            return {"error": f"Timeout beim Aufruf von {function_name}", "execution_time_ms": 0}
        except httpx.ConnectTimeout:
            logger.error(f"Verbindungs-Timeout für {function_name}")
            return {"error": f"Verbindungs-Timeout für {function_name}", "execution_time_ms": 0}
        except httpx.ConnectError:
            logger.error(f"Verbindungsfehler für {function_name}")
            return {"error": f"Verbindungsfehler für {function_name}", "execution_time_ms": 0}
        except Exception as e:
            logger.error(f"Unerwarteter Fehler beim Aufruf von {function_name}: {e}")
            logger.error(f"Stack Trace: {traceback.format_exc()}")
            return {"error": str(e), "execution_time_ms": 0}
    
    async def update_function_config(self, function_name, config_updates):
        """Aktualisiert die Konfiguration einer Funktion (z.B. Memory)."""
        service_name = function_name.lower().replace("_", "-")
        url = f"{self.services_url_base}:{self._get_service_port(service_name)}/config"
        
        logger.debug(f"Aktualisiere Konfiguration für {function_name}: {config_updates}")
        
        try:
            response = await self.http_client.post(url, json=config_updates)
            success = response.status_code == 200
            if success:
                logger.debug(f"Konfiguration für {function_name} erfolgreich aktualisiert")
            else:
                logger.warning(f"Konfigurationsaktualisierung für {function_name} fehlgeschlagen: Status {response.status_code}")
            return success
        except Exception as e:
            logger.warning(f"Fehler beim Aktualisieren der Konfiguration für {function_name}: {e}")
            logger.debug(f"Stack Trace: {traceback.format_exc()}")
            return False
    
    async def update_network_config(self, function_name, network_config):
        """Aktualisiert die Netzwerkkonfiguration einer Funktion."""
        service_name = function_name.lower().replace("_", "-")
        url = f"{self.services_url_base}:{self._get_service_port(service_name)}/network"
        
        logger.debug(f"Aktualisiere Netzwerkkonfiguration für {function_name}: {network_config}")
        
        try:
            response = await self.http_client.post(url, json=network_config)
            success = response.status_code == 200
            if success:
                logger.debug(f"Netzwerkkonfiguration für {function_name} erfolgreich aktualisiert")
            else:
                logger.warning(f"Netzwerkkonfiguration für {function_name} fehlgeschlagen: Status {response.status_code}")
            return success
        except Exception as e:
            logger.warning(f"Fehler beim Aktualisieren der Netzwerkkonfiguration für {function_name}: {e}")
            logger.debug(f"Stack Trace: {traceback.format_exc()}")
            return False
    
    def _get_service_port(self, service_name):
        """Gibt den Port für einen Service zurück."""
        # Service-Port-Mapping
        service_ports = {
            "addcartitem": 8002,
            "cartkvstorage": 8003,
            "checkout": 8012,
            "currency": 8014,
            "email": 8017,
            "emptycart": 8005,
            "frontend": 8001,
            "getads": 8016,
            "getcart": 8004,
            "getproduct": 8007,
            "listproducts": 8006,
            "listrecommendations": 8009,
            "payment": 8013,
            "searchproducts": 8008,
            "shipmentquote": 8010,
            "shiporder": 8011,
            "supportedcurrencies": 8015
        }
        port = service_ports.get(service_name, 8000)
        logger.debug(f"Service-Port für {service_name}: {port}")
        return port


async def run_function_fusion_optimization(test_count=None, parallel=True, max_workers=8):
    """Führt einen umfassenden Optimierungsprozess für Function Fusion durch."""
    logger.info("Starte Function Fusion Optimierung...")
    start_time = time.time()
    
    # 1. Optimizer für automatische Fusionsidentifikation erstellen
    logger.info("Initialisiere FunctionFusionOptimizer...")
    optimizer = FunctionFusionOptimizer()
    
    # 2. Testvarianten für realistische Funktionsaufrufe generieren
    logger.info("Generiere Testkonfigurationen...")
    test_configs = optimizer.generate_test_configurations(test_count)
    logger.info(f"Generiert: {len(test_configs)} Testkonfigurationen")
    
    # 3. Tests ausführen
    logger.info("Führe Tests aus...")
    test_start_time = time.time()
    if parallel and max_workers > 1:
        logger.info(f"Führe Tests parallel mit {max_workers} Workern aus...")
        await optimizer.run_tests_parallel(test_configs, max_workers)
    else:
        logger.info("Führe Tests sequentiell aus...")
        await optimizer.run_tests(test_configs)
    
    test_end_time = time.time()
    test_duration = test_end_time - test_start_time
    logger.info(f"Tests abgeschlossen in {test_duration:.2f} Sekunden")
    
    # 4. Ergebnisse analysieren
    logger.info("Analysiere Ergebnisse...")
    analysis_start_time = time.time()
    results = optimizer.analyze_results()
    analysis_end_time = time.time()
    analysis_duration = analysis_end_time - analysis_start_time
    logger.info(f"Analyse abgeschlossen in {analysis_duration:.2f} Sekunden")
    
    # 5. Bericht erstellen
    logger.info("Erstelle Bericht...")
    report_start_time = time.time()
    generate_detailed_report(results)
    report_end_time = time.time()
    report_duration = report_end_time - report_start_time
    logger.info(f"Bericht erstellt in {report_duration:.2f} Sekunden")
    
    end_time = time.time()
    total_duration = end_time - start_time
    logger.info(f"Function Fusion Optimierung abgeschlossen in {total_duration:.2f} Sekunden")
    return results


def generate_detailed_report(results):
    """Erstellt einen detaillierten Bericht über die Optimierungsergebnisse."""
    logger.info("Erstelle detaillierten Bericht...")
    
    # 1. Überblick
    print("=== FUNCTION FUSION OPTIMIERUNG - BERICHT ===")
    print(f"Getestete Konfigurationen: {results['summary']['total_tests']}")
    print(f"Durchschnittliche Beschleunigung: {results['summary']['average_speedup']:.2f}x")
    print(f"Maximale Beschleunigung: {results['summary']['max_speedup']:.2f}x")
    
    # 2. Beste Fusionskandidaten
    print("\n=== BESTE FUSION-KANDIDATEN ===")
    for i, candidate in enumerate(results.get("best_fusion_candidates", []), 1):
        print(f"{i}. {' -> '.join(candidate['functions'])}")
        print(f"   Durchschnittliche Beschleunigung: {candidate['avg_speedup']:.2f}x")
        print(f"   Anzahl Tests: {candidate['test_count']}")
        print("   ---")
    
    # 3. Top-5 Konfigurationen
    print("\n=== TOP 5 KONFIGURATIONEN ===")
    for i, config in enumerate(results.get("top_configs", []), 1):
        print(f"{i}. Kette: {config['chain']}")
        if "fusion_groups" in config:
            print(f"   Fusionsgruppen: {config['fusion_groups']}")
        print(f"   Beschleunigung: {config.get('speedup', 0):.2f}x")
        print(f"   Latenz: {config.get('latency_ms', 0):.2f} ms")
        print("   ---")
    
    # 4. Performance nach Fusionsgruppe
    print("\n=== PERFORMANCE NACH FUSIONSGRUPPE ===")
    fusion_data = sorted(
        results.get("fusion_performance", {}).items(),
        key=lambda x: x[1]["avg_speedup"],
        reverse=True
    )
    for fusion, data in fusion_data[:5]:  # Top-5
        print(f"Fusionsgruppe: {fusion}")
        print(f"  Durchschnittliche Beschleunigung: {data['avg_speedup']:.2f}x")
        print(f"  Anzahl Tests: {data['count']}")
    
    # 5. Ausgabe in Datei
    report_file = f"fusion_optimization_results_{time.strftime('%Y%m%d_%H%M%S')}.json"
    logger.info(f"Speichere vollständigen Bericht in {report_file}")
    
    with open(report_file, "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"\nDetaillierten Bericht in '{report_file}' gespeichert.")
    logger.info("Bericht erfolgreich erstellt und gespeichert")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Function Fusion Optimizer')
    parser.add_argument('--test-count', type=int, help='Anzahl der durchzuführenden Tests')
    parser.add_argument('--parallel', action='store_true', help='Tests parallel ausführen')
    parser.add_argument('--workers', type=int, default=8, help='Anzahl der Worker für parallele Ausführung')
    parser.add_argument('--debug', action='store_true', help='Debug-Logging aktivieren')
    args = parser.parse_args()
    
    # Debug-Logging aktivieren, falls gewünscht
    if args.debug:
        logger.setLevel(logging.DEBUG)
        for handler in logger.handlers:
            handler.setLevel(logging.DEBUG)
        logger.info("Debug-Logging aktiviert")
    
    # Informationen über die Ausführungsumgebung
    logger.info(f"Python-Version: {os.sys.version}")
    logger.info(f"Arbeitsverzeichnis: {os.getcwd()}")
    logger.info(f"Verfügbare CPUs: {os.cpu_count()}")
    
    # Optimierung durchführen
    logger.info(f"Starte Optimierung mit Parametern: test_count={args.test_count}, parallel={args.parallel}, workers={args.workers}")
    try:
        asyncio.run(run_function_fusion_optimization(
            test_count=args.test_count,
            parallel=args.parallel,
            max_workers=args.workers
        ))
    except Exception as e:
        logger.critical(f"Fataler Fehler bei der Optimierung: {e}")
        logger.critical(f"Stack Trace: {traceback.format_exc()}")
        raise