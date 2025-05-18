# app/optimizer/communication_aware_optimizer.py

import logging
import statistics
import copy
import json
import os
from typing import Dict, List, Any, Tuple, Optional, Set

from app.optimizer.enhanced_fusion_optimizer import EnhancedFusionOptimizer
from evaluation.improved_cost_model import ImprovedCostModel

logger = logging.getLogger("lambda-sim.communication-optimizer")

class CommunicationAwareOptimizer(EnhancedFusionOptimizer):
    """
    Erweiterte Optimizer-Implementierung, die Service-zu-Service-Kommunikationsaspekte berücksichtigt.
    
    Diese Klasse erweitert den EnhancedFusionOptimizer um die Fähigkeit, bei der Optimierung
    von Function Fusion Setups auch Kommunikationsmuster, -kosten und -latenzen zu berücksichtigen.
    """
    
    def __init__(self, lambda_runtime=None, fusion_engine=None, cost_model=None, communication_model=None):
        """
        Initialisiert den kommunikationsbewussten Optimizer.
        
        Args:
            lambda_runtime: Die Lambda-Runtime-Instanz
            fusion_engine: Die Fusion-Engine-Instanz (sollte idealerweise EnhancedFusionEngine sein)
            cost_model: Das Kostenmodell für die Optimierung
            communication_model: Das Kommunikationsmodell
        """
        super().__init__(lambda_runtime, fusion_engine, cost_model)
        
        # Kommunikationsmodell speichern, wenn übergeben
        self.communication_model = communication_model
        
        # Kommunikationsspezifische Optimierungsgewichte
        self.comm_optimization_weights = {
            "latency": 0.4,    # Gewichtung für Gesamtlatenz
            "cost": 0.3,       # Gewichtung für Gesamtkosten
            "comm_latency": 0.2,  # Gewichtung für Kommunikationslatenz
            "comm_cost": 0.1    # Gewichtung für Kommunikationskosten
        }
        
        # Kommunikationstypen für verschiedene Szenarien
        self.communication_strategies = {
            "sync_local": "direct",       # Direkte Aufrufe für lokale synchrone Aufrufe
            "sync_remote": "http",        # HTTP für entfernte synchrone Aufrufe
            "async_local": "event",       # Event-basiert für lokale asynchrone Aufrufe
            "async_remote": "api_gateway" # API Gateway für entfernte asynchrone Aufrufe
        }
        
        # Erweiterter Speicherplatz für Optimierungsergebnisse
        self.optimization_phases["communication"] = {"completed": False, "result": None}
    
    def set_communication_weights(self, latency: float, cost: float, comm_latency: float, comm_cost: float):
        """
        Setzt die Gewichtungsfaktoren für die kommunikationsbewusste Optimierung.
        
        Args:
            latency: Gewichtungsfaktor für Gesamtlatenz (0-1)
            cost: Gewichtungsfaktor für Gesamtkosten (0-1)
            comm_latency: Gewichtungsfaktor für Kommunikationslatenz (0-1)
            comm_cost: Gewichtungsfaktor für Kommunikationskosten (0-1)
        """
        total = latency + cost + comm_latency + comm_cost
        
        if total > 0:
            self.comm_optimization_weights = {
                "latency": latency / total,
                "cost": cost / total,
                "comm_latency": comm_latency / total,
                "comm_cost": comm_cost / total
            }
            
        logger.info(f"Kommunikationsgewichte gesetzt: {self.comm_optimization_weights}")
    
    def set_communication_strategies(self, strategies: Dict[str, str]):
        """
        Setzt die Kommunikationsstrategien für verschiedene Aufruftypen.
        
        Args:
            strategies: Dictionary mit Strategien
        """
        self.communication_strategies.update(strategies)
        logger.info(f"Kommunikationsstrategien aktualisiert: {self.communication_strategies}")
    
    def get_optimal_configuration_with_communication(self) -> str:
        """
        Findet die optimale Konfiguration unter Berücksichtigung der Kommunikationsaspekte.
        
        Returns:
            Key des optimalen Setups
        """
        # Wenn keine Ergebnisse vorhanden sind, leeren String zurückgeben
        if not self.test_results:
            return ""
           
        # Wenn kein Kostenmodell oder Kommunikationsmodell vorhanden ist, auf Standard-Methode zurückfallen
        if not self.cost_model or not self.communication_model:
            logger.warning("Kein Kosten- oder Kommunikationsmodell verfügbar, verwende Standard-Methode")
            return self.get_optimal_configuration()
        
        # Berechne normalisierte Scores für verschiedene Aspekte
        latency_scores = {}
        cost_scores = {}
        comm_latency_scores = {}
        comm_cost_scores = {}
       
        # Latenz-Scores berechnen
        durations = {}
        for key in self.test_results.keys():
            durations[key] = statistics.median([inv.get("billedDuration", 0) for inv in self.test_results[key]])
           
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
        
        # Kommunikationslatenz-Scores berechnen
        comm_latencies = {}
        for key in self.test_results.keys():
            comm_latency_values = []
            for inv in self.test_results[key]:
                # Extrahiere Kommunikationsstatistiken, falls vorhanden
                comm_stats = inv.get("communication_stats", {})
                if comm_stats and "total_latency" in comm_stats:
                    comm_latency_values.append(comm_stats["total_latency"])
                else:
                    # Wenn keine Kommunikationsstatistik vorhanden ist, verwende einen Schätzwert
                    # basierend auf der Anzahl der Funktionsaufrufe und dem Kommunikationstyp
                    calls = inv.get("calls", [])
                    estimated_latency = 0
                    for call in calls:
                        call_type = call.get("strategy", "local")
                        is_sync = call.get("sync", False)
                        
                        if call_type == "remote":
                            if is_sync:
                                # Für synchrone Remote-Aufrufe HTTP-Latenz schätzen
                                estimated_latency += 50  # 50ms als Schätzwert
                            else:
                                # Für asynchrone Remote-Aufrufe API Gateway-Latenz schätzen
                                estimated_latency += 80  # 80ms als Schätzwert
                    
                    comm_latency_values.append(estimated_latency)
            
            if comm_latency_values:
                comm_latencies[key] = statistics.mean(comm_latency_values)
            else:
                comm_latencies[key] = 0
        
        max_comm_latency = max(comm_latencies.values()) if comm_latencies and max(comm_latencies.values()) > 0 else 1
        for key, latency in comm_latencies.items():
            # Normalisierte Kommunikationslatenz: Niedrigere Werte sind besser
            comm_latency_scores[key] = 1 - (latency / max_comm_latency)
        
        # Kommunikationskosten-Scores berechnen
        comm_costs = {}
        for key in self.test_results.keys():
            comm_cost_values = []
            for inv in self.test_results[key]:
                # Extrahiere Kommunikationsstatistiken, falls vorhanden
                comm_stats = inv.get("communication_stats", {})
                if comm_stats and "total_cost" in comm_stats:
                    comm_cost_values.append(comm_stats["total_cost"])
                else:
                    # Wenn keine Kommunikationsstatistik vorhanden ist, verwende einen Schätzwert
                    calls = inv.get("calls", [])
                    estimated_cost = 0
                    for call in calls:
                        call_type = call.get("strategy", "local")
                        if call_type == "remote":
                            # Schätzwert für Remote-Aufrufkosten
                            estimated_cost += 0.0000004  # $0.40 pro Million Aufrufe
                    
                    comm_cost_values.append(estimated_cost)
            
            if comm_cost_values:
                comm_costs[key] = statistics.mean(comm_cost_values)
            else:
                comm_costs[key] = 0
        
        max_comm_cost = max(comm_costs.values()) if comm_costs and max(comm_costs.values()) > 0 else 1
        for key, cost in comm_costs.items():
            # Normalisierte Kommunikationskosten: Niedrigere Werte sind besser
            comm_cost_scores[key] = 1 - (cost / max_comm_cost)
        
        # Kombinierte gewichtete Scores berechnen
        combined_scores = {}
        for key in self.test_results.keys():
            latency_score = latency_scores.get(key, 0)
            cost_score = cost_scores.get(key, 0)
            comm_latency_score = comm_latency_scores.get(key, 0)
            comm_cost_score = comm_cost_scores.get(key, 0)
            
            combined_scores[key] = (
                self.comm_optimization_weights["latency"] * latency_score +
                self.comm_optimization_weights["cost"] * cost_score +
                self.comm_optimization_weights["comm_latency"] * comm_latency_score +
                self.comm_optimization_weights["comm_cost"] * comm_cost_score
            )
        
        # Setup mit dem höchsten Score finden
        optimal_key = max(combined_scores.items(), key=lambda x: x[1])[0] if combined_scores else ""
        
        # Logging der Score-Komponenten für das optimale Setup
        if optimal_key:
            logger.info(f"Optimales Setup mit Kommunikation: {optimal_key}")
            logger.info(f"  Latenz-Score: {latency_scores.get(optimal_key, 0):.4f}")
            logger.info(f"  Kosten-Score: {cost_scores.get(optimal_key, 0):.4f}")
            logger.info(f"  Kommunikationslatenz-Score: {comm_latency_scores.get(optimal_key, 0):.4f}")
            logger.info(f"  Kommunikationskosten-Score: {comm_cost_scores.get(optimal_key, 0):.4f}")
            logger.info(f"  Gesamt-Score: {combined_scores.get(optimal_key, 0):.4f}")
        
        return optimal_key
    
    def optimize_communication_settings(self, 
                                       path_groups: List[List[str]], 
                                       memory_configs: Dict[str, int]) -> Dict[str, Any]:
        """
        Optimiert die Kommunikationseinstellungen für die gegebenen Funktionsgruppen.
        
        Diese dritte Optimierungsphase findet nach der Pfad- und Infrastrukturoptimierung statt
        und bestimmt die optimalen Kommunikationstypen und -parameter.
        
        Args:
            path_groups: Funktionsgruppen aus der Pfadoptimierung
            memory_configs: Speicherkonfigurationen aus der Infrastrukturoptimierung
            
        Returns:
            Optimierte Kommunikationseinstellungen
        """
        logger.info("Starte Kommunikationsoptimierung für optimierte Pfadgruppen...")
        
        # Prüfe, ob die benötigten Komponenten verfügbar sind
        if not self.communication_model:
            logger.warning("Kein Kommunikationsmodell verfügbar, überspringe Kommunikationsoptimierung")
            return {}
        
        communication_settings = {}
        
        # Ermittle für jede Gruppe ihre Beziehungen zu anderen Gruppen
        group_relations = self._analyze_group_relations(path_groups)
        
        # Für jede Gruppe optimale Kommunikationseinstellungen bestimmen
        for i, group in enumerate(path_groups):
            group_key = self._get_group_key(group)
            
            # Standardkommunikationstypen setzen
            group_settings = {
                "communication_type": "direct",  # Default innerhalb der Gruppe
                "serialization": "json",
                "compression": "none",
                "auth_type": "none",
                "relations": {}
            }
            
            # Für jede andere Gruppe die Beziehung bestimmen
            for j, other_group in enumerate(path_groups):
                if i == j:
                    continue
                    
                other_group_key = self._get_group_key(other_group)
                relation = group_relations.get((group_key, other_group_key), {})
                
                # Kommunikationstyp basierend auf Aufrufart bestimmen
                comm_type = self._determine_optimal_communication_type(
                    relation.get("call_type", "none"),
                    relation.get("is_sync", False)
                )
                
                # Kommunikationseinstellungen für diese Beziehung
                relation_settings = {
                    "communication_type": comm_type,
                    "serialization": self._determine_optimal_serialization(comm_type, relation),
                    "compression": self._determine_optimal_compression(comm_type, relation),
                    "auth_type": self._determine_optimal_auth_type(comm_type, relation)
                }
                
                group_settings["relations"][other_group_key] = relation_settings
            
            communication_settings[group_key] = group_settings
            
        # Kommunikationsphase als abgeschlossen markieren
        self.optimization_phases["communication"]["completed"] = True
        self.optimization_phases["communication"]["result"] = communication_settings
        
        logger.info(f"Kommunikationsoptimierung abgeschlossen: {communication_settings}")
        
        return communication_settings
    
    def _analyze_group_relations(self, path_groups: List[List[str]]) -> Dict[Tuple[str, str], Dict[str, Any]]:
        """
        Analysiert die Beziehungen zwischen Funktionsgruppen basierend auf Aufrufmustern.
        
        Args:
            path_groups: Funktionsgruppen aus der Pfadoptimierung
            
        Returns:
            Dictionary mit Beziehungen zwischen Gruppen
        """
        relations = {}
        
        # Mappings erstellen: Funktion -> Gruppe
        function_to_group = {}
        for group in path_groups:
            group_key = self._get_group_key(group)
            for func in group:
                function_to_group[func] = group_key
        
        # Aufrufmuster analysieren
        call_patterns = self.analyze_call_patterns()
        
        # Für jede Aufrufbeziehung die Gruppenbeziehung bestimmen
        for caller, callees in call_patterns.items():
            if caller not in function_to_group:
                continue
                
            caller_group = function_to_group[caller]
            
            for callee, is_sync in callees.items():
                if callee not in function_to_group:
                    continue
                    
                callee_group = function_to_group[callee]
                
                # Wenn Caller und Callee in verschiedenen Gruppen sind
                if caller_group != callee_group:
                    relation_key = (caller_group, callee_group)
                    
                    # Bestehende Beziehung aktualisieren oder neue erstellen
                    if relation_key not in relations:
                        relations[relation_key] = {
                            "call_count": 0,
                            "sync_calls": 0,
                            "async_calls": 0,
                            "call_type": "remote"  # Standardmäßig remote, da zwischen Gruppen
                        }
                    
                    relations[relation_key]["call_count"] += 1
                    if is_sync:
                        relations[relation_key]["sync_calls"] += 1
                    else:
                        relations[relation_key]["async_calls"] += 1
                        
                    # Bestimme den dominanten Aufruftyp
                    relations[relation_key]["is_sync"] = relations[relation_key]["sync_calls"] > relations[relation_key]["async_calls"]
        
        return relations
    
    def _get_group_key(self, group: List[str]) -> str:
        """Erzeugt einen konsistenten Schlüssel für eine Funktionsgruppe."""
        return ".".join(sorted(group))
    
    def _determine_optimal_communication_type(self, call_type: str, is_sync: bool) -> str:
        """
        Bestimmt den optimalen Kommunikationstyp basierend auf Aufruftyp und Synchronität.
        
        Args:
            call_type: "local" oder "remote"
            is_sync: Ob synchrone Aufrufe dominieren
            
        Returns:
            Optimaler Kommunikationstyp
        """
        if call_type == "local":
            return self.communication_strategies["sync_local"] if is_sync else self.communication_strategies["async_local"]
        else:  # remote
            return self.communication_strategies["sync_remote"] if is_sync else self.communication_strategies["async_remote"]
    
    def _determine_optimal_serialization(self, comm_type: str, relation: Dict[str, Any]) -> str:
        """
        Bestimmt das optimale Serialisierungsformat basierend auf Kommunikationstyp und Beziehung.
        
        Args:
            comm_type: Kommunikationstyp
            relation: Beziehungsinformationen
            
        Returns:
            Optimales Serialisierungsformat
        """
        # Entscheide basierend auf Kommunikationstyp
        if comm_type == "direct":
            return "json"  # Direkte Aufrufe verwenden typischerweise JSON
        elif comm_type == "http":
            # Für HTTP-Kommunikation können wir kompaktere Formate verwenden
            return "protobuf" if self._is_high_volume(relation) else "json"
        elif comm_type == "api_gateway":
            return "json"  # API Gateway verwendet typischerweise JSON
        elif comm_type == "event":
            return "json"  # Eventbasierte Dienste verwenden typischerweise JSON
        else:
            return "json"  # Standard ist JSON
    
    def _determine_optimal_compression(self, comm_type: str, relation: Dict[str, Any]) -> str:
        """
        Bestimmt die optimale Komprimierung basierend auf Kommunikationstyp und Beziehung.
        
        Args:
            comm_type: Kommunikationstyp
            relation: Beziehungsinformationen
            
        Returns:
            Optimale Komprimierung
        """
        # Für lokale oder direkte Aufrufe keine Komprimierung
        if comm_type == "direct":
            return "none"
            
        # Für Hochvolumen-Aufrufe Brotli verwenden
        if self._is_high_volume(relation):
            return "brotli"
            
        # Für HTTP und API Gateway normales gzip
        if comm_type in ["http", "api_gateway"]:
            return "gzip"
            
        # Standard ist keine Komprimierung
        return "none"
    
    def _determine_optimal_auth_type(self, comm_type: str, relation: Dict[str, Any]) -> str:
        """
        Bestimmt den optimalen Authentifizierungstyp basierend auf Kommunikationstyp und Beziehung.
        
        Args:
            comm_type: Kommunikationstyp
            relation: Beziehungsinformationen
            
        Returns:
            Optimaler Authentifizierungstyp
        """
        # Für direkte Aufrufe keine Authentifizierung
        if comm_type == "direct":
            return "none"
            
        # Für HTTP einfache API-Schlüssel
        if comm_type == "http":
            return "api_key"
            
        # Für API Gateway IAM-Authentifizierung
        if comm_type == "api_gateway":
            return "iam"
            
        # Für Event-Services typischerweise IAM-Authentifizierung
        if comm_type == "event":
            return "iam"
            
        # Standard ist keine Authentifizierung
        return "none"
    
    def _is_high_volume(self, relation: Dict[str, Any]) -> bool:
        """Bestimmt, ob die Beziehung ein hohes Aufrufsvolumen hat."""
        return relation.get("call_count", 0) > 10
    
    def optimize(self, null_if_already_tested: bool = False) -> Tuple[List[List[str]], Dict[str, int], Dict[str, Any]]:
        """
        Führt alle drei Optimierungsphasen durch:
        1. Pfadoptimierung
        2. Infrastrukturoptimierung
        3. Kommunikationsoptimierung
        
        Args:
            null_if_already_tested: Wenn True, gibt None zurück, wenn das Setup bereits getestet wurde
            
        Returns:
            Tuple mit (optimierten Funktionsgruppen, optimierten Speicherkonfigurationen, optimierten Kommunikationseinstellungen)
        """
        # Phase 1 & 2: Pfad- und Infrastrukturoptimierung (aus Basisklasse)
        path_groups, memory_configs = super().optimize(null_if_already_tested)
        
        # Phase 3: Kommunikationsoptimierung
        logger.info("Starte Kommunikationsoptimierung...")
        comm_settings = self.optimize_communication_settings(path_groups, memory_configs)
        
        return path_groups, memory_configs, comm_settings
    
    def get_optimal_configuration(self) -> str:
        """
        Überschreibt die Methode aus der Basisklasse, um Kommunikationsaspekte zu berücksichtigen.
        
        Returns:
            Key des optimalen Setups
        """
        return self.get_optimal_configuration_with_communication()
    
    def save_optimization_results(self, filename: str) -> None:
        """
        Speichert die Optimierungsergebnisse in einer JSON-Datei.
        Erweitert die Methode aus der Basisklasse um Kommunikationsoptimierungsergebnisse.
        
        Args:
            filename: Dateiname
        """
        if not (self.optimization_phases["path"]["completed"] and 
                self.optimization_phases["infrastructure"]["completed"]):
            logger.warning("Keine vollständigen Optimierungsergebnisse zum Speichern vorhanden")
            return
            
        results = {
            "path_groups": self.optimization_phases["path"]["result"],
            "memory_configurations": self.optimization_phases["infrastructure"]["result"],
            "optimization_weights": self.optimization_weights,
            "setup_string": self.get_setup_string(self.optimization_phases["path"]["result"])
        }
        
        # Kommunikationsoptimierungsergebnisse hinzufügen, falls vorhanden
        if self.optimization_phases["communication"]["completed"]:
            results["communication_settings"] = self.optimization_phases["communication"]["result"]
            results["communication_weights"] = self.comm_optimization_weights
        
        try:
            with open(filename, 'w') as f:
                json.dump(results, f, indent=2)
            logger.info(f"Optimierungsergebnisse gespeichert in: {filename}")
        except Exception as e:
            logger.error(f"Fehler beim Speichern der Optimierungsergebnisse: {str(e)}")
    
    def load_optimization_results(self, filename: str) -> Dict[str, Any]:
        """
        Lädt Optimierungsergebnisse aus einer JSON-Datei.
        Erweitert die Methode aus der Basisklasse um Kommunikationsoptimierungsergebnisse.
        
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
            
            # Kommunikationsoptimierungsergebnisse laden, falls vorhanden
            if "communication_settings" in results:
                self.optimization_phases["communication"]["completed"] = True
                self.optimization_phases["communication"]["result"] = results.get("communication_settings", {})
                
            if "communication_weights" in results:
                self.comm_optimization_weights = results.get("communication_weights", self.comm_optimization_weights)
            
            logger.info(f"Optimierungsergebnisse geladen aus: {filename}")
            return results
        except Exception as e:
            logger.error(f"Fehler beim Laden der Optimierungsergebnisse: {str(e)}")
            return {}