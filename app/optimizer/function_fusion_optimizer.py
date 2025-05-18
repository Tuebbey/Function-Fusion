import json
import sys
from typing import Dict, List, Any, Set, Optional, Tuple
import statistics
import logging

# Logger für den Optimizer
logger = logging.getLogger("lambda-sim.optimizer")

# Konstanten - Liste der Funktionsnamen
FUNCTION_LOG_GROUP_NAMES = ["Function- -A", "Function- -B", "Function- -C", "Function- -D", "Function- -E", "Function- -F", "Function- -G"]

# Hilfsfunktionen für Setup-Konvertierung
def setup_from_list(setup_list: List[List[str]]) -> str:
    """Konvertiert eine Liste von Fusion-Gruppen in einen Setup-String."""
    return ",".join(sorted([".".join(sorted(group)) for group in setup_list]))

def list_from_setup(setup: str) -> List[List[str]]:
    """Konvertiert einen Setup-String in eine Liste von Fusion-Gruppen."""
    return [group.split(".") for group in setup.split(",")]

def pairs(arr: List) -> List[List]:
    """Erzeugt alle möglichen Paare aus einer Liste."""
    result = []
    for i in range(len(arr)):
        for j in range(i + 1, len(arr)):
            result.append([arr[i], arr[j]])
    return result

def get_configuration_with_lowest_latency(setups_tested: Dict[str, List[Dict]]) -> str:
    """
    Findet die Konfiguration mit der niedrigsten mittleren Latenz.
    
    Args:
        setups_tested: Dictionary mit Setups und ihren Ausführungsdaten
        
    Returns:
        Key des Setups mit der niedrigsten mittleren Latenz
    """
    medians = {}
    for key in setups_tested.keys():
        durations = [inv["billedDuration"] for inv in setups_tested[key]]
        if durations:
            medians[key] = statistics.median(durations)
    
    min_key = ""
    min_value = float('inf')
    
    for key in medians:
        if medians[key] < min_value:
            min_key = key
            min_value = medians[key]
    
    return min_key

def iterate_on_lowest_latency(
    setups_tested: Dict[str, List[Dict]], 
    null_if_already_tested: bool = False,
    function_to_find_base=get_configuration_with_lowest_latency
) -> Optional[str]:
    """
    Iteriert ausgehend von der aktuell besten Konfiguration, um eine bessere zu finden.
    
    Args:
        setups_tested: Dictionary mit Setups und ihren Ausführungsdaten
        null_if_already_tested: Wenn True, gibt None zurück wenn das Setup bereits getestet wurde
        function_to_find_base: Funktion zum Finden der Basiskonfiguration
        
    Returns:
        Neues optimiertes Setup oder None, wenn keine Verbesserung möglich
    """
    current_min = function_to_find_base(setups_tested)
    current_optimal_setup = list_from_setup(current_min)
    logger.info(f"Current Optimal Setup is: {current_optimal_setup}")
    
    # Erstelle Sets für synchrone Aufrufe
    sync_calls = set()
    # Initialisiere die Sets, so dass jede Funktion zunächst in ihrem eigenen Set ist
    function_names = [fn.split("-")[2] for fn in FUNCTION_LOG_GROUP_NAMES]
    for fname in function_names:
        sync_calls.add(frozenset([fname]))
    
    # Analysiere alle Aufrufe und fasse synchrone Aufrufe zusammen
    for key in setups_tested:
        invocations_list = setups_tested[key]
        for invocation in invocations_list:
            # Liste der Funktionen, die synchron aufgerufen werden
            sync_calls_list = [
                call["called"] 
                for call in invocation.get("calls", []) 
                if call.get("sync", False) == True
            ]
            
            # Überprüfe jedes Paar von synchronen Aufrufen
            for pair in pairs(sync_calls_list):
                # Finde die Sets, die die Funktionen enthalten
                first_set = None
                second_set = None
                
                for s in sync_calls:
                    if pair[0] in s:
                        first_set = s
                    if pair[1] in s:
                        second_set = s
                
                # Wenn sie noch nicht im selben Set sind, führe die Sets zusammen
                if first_set and second_set and first_set != second_set:
                    if pair[1] not in first_set:
                        sync_calls.remove(first_set)
                        sync_calls.remove(second_set)
                        combined = set(first_set).union(set(second_set))
                        sync_calls.add(frozenset(combined))
    
    logger.info("----- Done Setting up, now finding new optimums.")
    logger.info(f"syncCalls: {sync_calls}")
    
    # Vergleiche Setup und syncCalls, um mögliche Verbesserungen zu finden
    for i, fusion_group in enumerate(current_optimal_setup):
        for fktn in fusion_group:
            logger.info(f"Currently Trying function {fktn}")
            
            # Überprüfe, ob es Funktionen gibt, die nicht aufgerufen werden, aber in derselben Fusionsgruppe sind
            logger.info(f"Trying to find a function that is not called at all but in the same fusion group as {fktn}")
            fktn_group = next((g for g in current_optimal_setup if fktn in g), [])
            logger.info(f"Function Group is {fktn_group}")
            
            # Finde das synchrone Set, das die Funktion enthält
            fktn_sync_set = None
            for s in sync_calls:
                if fktn in s:
                    fktn_sync_set = s
                    break
            
            logger.info(f"Function Sync Set is {fktn_sync_set}")
            
            # Falls die Funktion nicht aufgerufen wird
            if not fktn_sync_set:
                logger.info(f"Skipping uncalled function {fktn}")
                continue
            
            for fktn_in_group in fktn_group:
                if fktn_sync_set and fktn_in_group not in fktn_sync_set:
                    logger.info(f"{fktn_in_group} should not be in the same fusionGroup as {fktn}")
                    idx = next((i for i, g in enumerate(current_optimal_setup) if fktn in g), -1)
                    if idx >= 0:
                        current_optimal_setup[idx] = [item for item in fktn_group if item != fktn_in_group]
                        current_optimal_setup.append([fktn_in_group])
                        logger.info(f"new Optimal Setup {setup_from_list(current_optimal_setup)}")
                        
                        already_tested = setup_from_list(current_optimal_setup) in setups_tested
                        if null_if_already_tested and already_tested:
                            logger.info("Returning None because it has already been tested")
                            return None
                        
                        if not already_tested:
                            return setup_from_list(current_optimal_setup)
                        else:
                            logger.info("...was already tested")
                else:
                    logger.info(f"Function Sync Set contains function {fktn_in_group}")
            
            # Überprüfe auf Funktionen, die synchron zusammengehören, aber in verschiedenen Gruppen sind
            if fktn_sync_set:
                for should_be_sync in fktn_sync_set:
                    logger.info(f"Trying whether {should_be_sync} is already in fusion group {fusion_group}")
                    logger.info(f"Shouldbesync type: {type(should_be_sync)}")
                    
                    if should_be_sync not in fusion_group:
                        logger.info(f"!!! Found one! FusionGroup {fusion_group} does not include {should_be_sync} !")
                        logger.info(f"Old Optimal Setup: {current_optimal_setup}")
                        
                        # Entferne should_be_sync aus seiner aktuellen Fusionsgruppe
                        for k in range(len(current_optimal_setup)):
                            new_group = [item for item in current_optimal_setup[k] if item != should_be_sync]
                            logger.info(f"Current Group {current_optimal_setup[k]} filtered down to {new_group}")
                            
                            if not new_group:
                                logger.info("...Removing it")
                                current_optimal_setup.pop(k)
                                break  # Wichtig: Breche die Schleife ab, da sich der Index verschoben hat
                            else:
                                current_optimal_setup[k] = new_group
                        
                        # Füge zur aktuellen Fusionsgruppe hinzu
                        current_optimal_setup[i].append(should_be_sync)
                        logger.info(f"New Optimal Setup: {current_optimal_setup}")
                        
                        # Überprüfe, ob dieses Setup bereits getestet wurde
                        already_tested = setup_from_list(current_optimal_setup) in setups_tested
                        
                        if already_tested:
                            logger.info("New Optimum has already been tested...")
                            
                            if null_if_already_tested:
                                return None
                            
                            continue
                        
                        return setup_from_list(current_optimal_setup)
                    else:
                        logger.info("...It is already...")
            
            # Versuche asynchrone Funktionen in separate Gruppen zu verschieben
            other_sync_sets = [s for s in sync_calls if fktn not in s]
            for not_sync_set in other_sync_sets:
                logger.info(f"Not Sync Set is {not_sync_set}")
                
                for should_not_be_sync in not_sync_set:
                    logger.info(f"Trying whether {should_not_be_sync} is wrongly in fusion group {fusion_group}")
                    
                    if should_not_be_sync in fusion_group:
                        logger.info(f"!!! Found one! FusionGroup {fusion_group} includes {should_not_be_sync}, but shouldn't!")
                        logger.info(f"Old Optimal Setup: {current_optimal_setup}")
                        
                        # Entferne should_not_be_sync aus der Fusionsgruppe
                        for k in range(len(current_optimal_setup)):
                            new_group = [item for item in current_optimal_setup[k] if item != should_not_be_sync]
                            
                            if not new_group:
                                current_optimal_setup.pop(k)
                                k -= 1  # Korrigiere den Index für die nächste Iteration
                            else:
                                current_optimal_setup[k] = new_group
                        
                        # Füge eine neue Fusionsgruppe hinzu
                        current_optimal_setup.append([should_not_be_sync])
                        logger.info(f"New Optimal Setup: {current_optimal_setup}")
                        
                        # Überprüfe, ob dieses Setup bereits getestet wurde
                        already_tested = setup_from_list(current_optimal_setup) in setups_tested
                        
                        if already_tested:
                            logger.info("New Optimum has already been tested...")
                            
                            if null_if_already_tested:
                                logger.info("Returning None because it has already been tested")
                                return None
                            
                            continue
                        
                        return setup_from_list(current_optimal_setup)
                    else:
                        logger.info("...It is already...")
    
    logger.info("Cannot find anything to improve")
    return None

# Beispielklasse zur Integration mit bestehender Optimizer-Struktur
class FunctionFusionOptimizerAdapter:
    """
    Adapter-Klasse zur Integration des Function Fusion Optimizers mit der bestehenden FusionOptimizer-Struktur.
    Diese Klasse dient als Brücke zwischen der vorhandenen Infrastruktur und den neuen Optimierungsfunktionen.
    """
    
    def __init__(self, lambda_runtime=None, fusion_engine=None):
        """
        Initialisiert den Adapter.
        
        Args:
            lambda_runtime: Die Lambda-Runtime-Instanz (optional)
            fusion_engine: Die Fusion-Engine-Instanz (optional)
        """
        self.lambda_runtime = lambda_runtime
        self.fusion_engine = fusion_engine
        self.test_results = {}
        
    def set_test_results(self, results: Dict[str, List[Dict]]):
        """
        Setzt die Testergebnisse für die Optimierung.
        
        Args:
            results: Dictionary mit Setups und ihren Ausführungsdaten
        """
        self.test_results = results
        
    def get_lowest_latency_configuration(self) -> str:
        """
        Findet die Konfiguration mit der niedrigsten Latenz.
        
        Returns:
            Key des Setups mit der niedrigsten mittleren Latenz
        """
        return get_configuration_with_lowest_latency(self.test_results)
        
    def optimize(self, null_if_already_tested: bool = False) -> Optional[str]:
        """
        Optimiert die Fusion-Setups basierend auf den Testergebnissen.
        
        Args:
            null_if_already_tested: Wenn True, gibt None zurück wenn das Setup bereits getestet wurde
            
        Returns:
            Neues optimiertes Setup oder None, wenn keine Verbesserung möglich
        """
        return iterate_on_lowest_latency(self.test_results, null_if_already_tested)
        
    def get_configuration_as_list(self, setup: str) -> List[List[str]]:
        """
        Konvertiert einen Setup-String in eine Liste von Fusion-Gruppen.
        
        Args:
            setup: Setup-String (z.B. "A.B,C,D")
            
        Returns:
            Liste von Fusion-Gruppen (z.B. [["A", "B"], ["C"], ["D"]])
        """
        return list_from_setup(setup)

# Wenn das Modul direkt ausgeführt wird (für Tests)
if __name__ == "__main__":
    # Beispiel für die Verwendung des Optimizers
    test_data = {
        "A.B.C.D.E.F.G": [
            {
                "traceId": "f1940f9795747e2a",
                "fusionGroup": "A,B,C,D", 
                "source": "A",
                "currentFunction": "A",
                "billedDuration": 2056,
                "maxMemoryUsed": 80,
                "isRootInvocation": True,
                "startTimestamp": 1645016691288,
                "endTimestamp": 1645016693329,
                "internalDuration": 2030,
                "calls": [
                    {"called": "A", "caller": "A", "local": True, "sync": True, "time": 641},
                    {"called": "B", "caller": "A", "local": True, "sync": True, "time": 641},
                    {"called": "D", "caller": "A", "local": True, "sync": True, "time": 641},
                    {"called": "E", "caller": "A", "local": True, "sync": True, "time": 641},
                    {"called": "C", "caller": "A", "local": True, "sync": False, "time": 641},
                    {"called": "F", "caller": "A", "local": True, "sync": False, "time": 641},
                    {"called": "G", "caller": "A", "local": True, "sync": False, "time": 641}
                ]
            },
        ],
        "A.B.D.E.F.G,C": [
            {
                "billedDuration": 3000,
                "calls": [
                    {"called": "A", "caller": "A", "local": True, "sync": True, "time": 641}
                ]
            }
        ],
        "A.B.D.E.G,C,F": [
            {
                "billedDuration": 10,
                "calls": [
                    {"called": "A", "caller": "A", "local": True, "sync": True, "time": 641}
                ]
            }
        ]
    }
    
    # Direkter Aufruf der Optimierungsfunktion
    optimal_setup = iterate_on_lowest_latency(test_data, False)
    print(f"Optimales Setup: {optimal_setup}")
    
    # Oder Verwendung über den Adapter
    adapter = FunctionFusionOptimizerAdapter()
    adapter.set_test_results(test_data)
    best_config = adapter.get_lowest_latency_configuration()
    print(f"Beste Konfiguration: {best_config}")
    optimized = adapter.optimize()
    print(f"Optimierte Konfiguration: {optimized}")