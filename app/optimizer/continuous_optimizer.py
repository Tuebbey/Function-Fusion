import asyncio
import time
import json
import logging
import os
import random
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime, timedelta
from threading import Thread, Event
import statistics

logger = logging.getLogger("lambda-sim.continuous-optimizer")

class ContinuousOptimizer:
    """
    Kontinuierliche Optimierung von Function Fusion Setups durch 
    fortlaufende Überwachung der Anwendungsleistung und automatische Anpassung.
    
    Verwendet ein modifiziertes CSP-1 (Continuous Sampling Plan) für die Entscheidung,
    wann Optimierungsläufe ausgeführt werden sollen.
    """
    
    def __init__(self, 
                 lambda_runtime=None, 
                 fusion_engine=None, 
                 enhanced_optimizer=None,
                 cost_model=None):
        """
        Initialisiert den kontinuierlichen Optimizer.
        
        Args:
            lambda_runtime: Die Lambda-Runtime-Instanz
            fusion_engine: Die Fusion-Engine-Instanz
            enhanced_optimizer: Der erweiterte Optimizer für die eigentliche Optimierung
            cost_model: Das Kostenmodell für die Kostenbewertung
        """
        self.lambda_runtime = lambda_runtime
        self.fusion_engine = fusion_engine
        self.enhanced_optimizer = enhanced_optimizer
        self.cost_model = cost_model
        
        # Optimierungsverlauf
        self.optimization_history = []
        
        # Metriken-Historie (für die Überwachung)
        self.metrics_history = {}
        
        # Status des Optimierungsprozesses
        self.is_running = False
        self.stop_event = Event()
        self.optimization_thread = None
        
        # CSP-1 Parameter
        self.csp_config = {
            "initial_interval": 100,  # Anfängliche Anzahl an Ausführungen vor der ersten Optimierung
            "normal_interval": 1000,  # Standardintervall zwischen Optimierungen
            "min_interval": 50,       # Minimales Intervall bei Bedarf für schnellere Anpassung
            "max_consecutive_success": 3,  # Anzahl erfolgreicher Optimierungen, bevor das Intervall erhöht wird
            "metric_drift_threshold": 0.15  # Schwellenwert für Leistungsabweichungen, die eine Optimierung auslösen
        }
        
        # Counter für Ausführungen seit der letzten Optimierung
        self.executions_since_last_optimization = 0
        
        # Aktuelle Intervallgröße
        self.current_interval = self.csp_config["initial_interval"]
        
        # Zähler für aufeinanderfolgende erfolgreiche Optimierungen
        self.consecutive_successful_optimizations = 0
        
        # Konfiguration für die Speicherung von Optimierungsergebnissen
        self.results_dir = "optimization_results"
        os.makedirs(self.results_dir, exist_ok=True)
    
    def start_monitoring(self, interval_seconds: float = 5.0):
        """
        Startet die kontinuierliche Überwachung und Optimierung.
        
        Args:
            interval_seconds: Intervall in Sekunden zwischen Überprüfungen
        """
        if self.is_running:
            logger.warning("Kontinuierliche Optimierung läuft bereits")
            return
        
        self.is_running = True
        self.stop_event.clear()
        
        # Starte den Überwachungs-Thread
        self.optimization_thread = Thread(
            target=self._monitoring_loop,
            args=(interval_seconds,),
            daemon=True
        )
        self.optimization_thread.start()
        
        logger.info(f"Kontinuierliche Optimierung gestartet (Intervall: {interval_seconds}s)")
    
    def stop_monitoring(self):
        """Stoppt die kontinuierliche Überwachung und Optimierung."""
        if not self.is_running:
            logger.warning("Kontinuierliche Optimierung läuft nicht")
            return
        
        self.stop_event.set()
        if self.optimization_thread:
            self.optimization_thread.join(timeout=10.0)
        
        self.is_running = False
        logger.info("Kontinuierliche Optimierung gestoppt")
    
    def _monitoring_loop(self, interval_seconds: float):
        """
        Hauptschleife für die Überwachung und Optimierung.
        
        Args:
            interval_seconds: Intervall in Sekunden zwischen Überprüfungen
        """
        while not self.stop_event.is_set():
            try:
                # Überprüfe, ob eine Optimierung erforderlich ist
                if self._should_run_optimization():
                    logger.info("Starte automatische Optimierung...")
                    
                    # Sammle aktuelle Ausführungsdaten
                    execution_data = self._collect_execution_data()
                    
                    # Führe die Optimierung durch
                    optimize_result = self._run_optimization(execution_data)
                    
                    # Aktualisiere den Optimierungsverlauf
                    self._update_optimization_history(optimize_result)
                    
                    # Verarbeite das Optimierungsergebnis
                    self._process_optimization_result(optimize_result)
                    
                    # Setze den Zähler zurück
                    self.executions_since_last_optimization = 0
                
                # Überwache Metriken für zukünftige Entscheidungen
                self._update_metrics()
            
            except Exception as e:
                logger.error(f"Fehler in der Überwachungsschleife: {str(e)}")
            
            # Warte bis zum nächsten Intervall oder bis das Stopp-Signal gesetzt wird
            self.stop_event.wait(interval_seconds)
    
    def _should_run_optimization(self) -> bool:
        """
        Entscheidet basierend auf dem CSP-1 Algorithmus, ob eine Optimierung durchgeführt werden soll.
        
        Returns:
            True, wenn eine Optimierung durchgeführt werden sollte, sonst False
        """
        # Einfache Implementierung des CSP-1 Algorithmus
        
        # Fall 1: Haben wir das Intervall erreicht?
        if self.executions_since_last_optimization >= self.current_interval:
            logger.info(f"Intervall von {self.current_interval} Ausführungen erreicht")
            return True
        
        # Fall 2: Haben wir signifikante Abweichungen in den Metriken?
        if self._detect_metric_drift():
            logger.info("Signifikante Leistungsabweichung erkannt")
            return True
        
        return False
    
    def _detect_metric_drift(self) -> bool:
        """
        Erkennt signifikante Änderungen in den Leistungsmetriken,
        die eine vorzeitige Optimierung erfordern könnten.
        
        Returns:
            True, wenn eine signifikante Abweichung erkannt wurde, sonst False
        """
        # Benötigt ausreichende Metrikhistorie
        if not self.metrics_history:
            return False
        
        # Prüfe Latenz-Drift
        if "latency" in self.metrics_history:
            latency_history = self.metrics_history["latency"]
            if len(latency_history) >= 10:  # Mindestens 10 Datenpunkte für statistische Signifikanz
                # Berechne die aktuelle Latenz (Durchschnitt der letzten 5 Werte)
                current_latency = statistics.mean(latency_history[-5:])
                
                # Berechne die Baseline-Latenz (Durchschnitt der vorherigen 5 Werte)
                baseline_latency = statistics.mean(latency_history[-10:-5])
                
                # Berechne die prozentuale Änderung
                if baseline_latency > 0:
                    latency_change = abs(current_latency - baseline_latency) / baseline_latency
                    
                    # Wenn die Änderung über dem Schwellenwert liegt, Optimierung auslösen
                    if latency_change > self.csp_config["metric_drift_threshold"]:
                        logger.info(f"Latenz-Drift erkannt: {latency_change:.2%} Änderung")
                        return True
        
        # Ähnlich könnten wir Kostenänderungen überwachen, falls verfügbar
        
        return False
    
    def _collect_execution_data(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Sammelt Ausführungsdaten aus der Fusion Engine und der Lambda Runtime.
        
        Returns:
            Dictionary mit Ausführungsdaten, gruppiert nach Fusion-Setups
        """
        # In einer realen Implementierung würden wir hier Daten aus Logs oder einer Datenbank abrufen
        # Für die Simulation nutzen wir die gespeicherten Traces
        
        execution_data = {}
        
        # Beispiel: Verarbeitung der Trace-Daten aus der Fusion Engine
        for trace_id, trace in self.fusion_engine.traces.items():
            setup_key = trace.fusion_id
            if setup_key not in execution_data:
                execution_data[setup_key] = []
            
            # Extraktion relevanter Daten aus dem Trace
            trace_data = {
                "trace_id": trace_id,
                "fusion_id": trace.fusion_id,
                "start_time": trace.start_time,
                "end_time": trace.end_time,
                "duration": trace.duration,
                "status": trace.status,
                "nodes": {}
            }
            
            # Knotendaten hinzufügen
            for node_id, node in trace.nodes.items():
                trace_data["nodes"][node_id] = {
                    "function_id": node.function_id,
                    "start_time": node.start_time,
                    "end_time": node.end_time,
                    "duration": node.duration,
                    "status": node.status,
                    "strategy": node.strategy,
                    "mode": node.mode
                }
            
            execution_data[setup_key].append(trace_data)
        
        return execution_data
    
    def _run_optimization(self, execution_data: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
        """
        Führt die eigentliche Optimierung durch.
        
        Args:
            execution_data: Gesammelte Ausführungsdaten
            
        Returns:
            Optimierungsergebnis
        """
        if not self.enhanced_optimizer:
            logger.error("Kein Enhanced Optimizer verfügbar")
            return {"status": "error", "message": "Kein Enhanced Optimizer verfügbar"}
        
        try:
            # Setze die aktuellen Testergebnisse im Optimizer
            self.enhanced_optimizer.set_test_results(execution_data)
            
            # Führe beide Optimierungsphasen durch
            path_groups, memory_configs = self.enhanced_optimizer.optimize()
            
            # Bewerte die Verbesserung
            current_setup = self.enhanced_optimizer.get_lowest_latency_configuration()
            optimal_setup = self.enhanced_optimizer.get_optimal_configuration()
            
            # Erstelle das Optimierungsergebnis
            result = {
                "status": "success",
                "timestamp": time.time(),
                "current_setup": current_setup,
                "optimal_setup": optimal_setup,
                "path_groups": path_groups,
                "memory_configurations": memory_configs,
                "metrics": self._get_current_metrics()
            }
            
            # Kostenabschätzung hinzufügen, falls ein Kostenmodell verfügbar ist
            if self.cost_model and current_setup in execution_data and optimal_setup in execution_data:
                current_cost = self.cost_model.calculate_fusion_cost(
                    {"groups": self.enhanced_optimizer.get_configuration_as_list(current_setup)},
                    execution_data[current_setup]
                )["total_cost"]
                
                optimal_cost = self.cost_model.calculate_fusion_cost(
                    {"groups": self.enhanced_optimizer.get_configuration_as_list(optimal_setup)},
                    execution_data[optimal_setup]
                )["total_cost"]
                
                result["cost_comparison"] = {
                    "current_cost": current_cost,
                    "optimal_cost": optimal_cost,
                    "savings_percentage": (1 - optimal_cost / current_cost) * 100 if current_cost > 0 else 0
                }
            
            return result
        
        except Exception as e:
            logger.error(f"Fehler bei der Optimierung: {str(e)}")
            return {
                "status": "error",
                "timestamp": time.time(),
                "message": str(e)
            }
    
    def _update_optimization_history(self, optimize_result: Dict[str, Any]):
        """
        Aktualisiert den Optimierungsverlauf mit dem neuesten Ergebnis.
        
        Args:
            optimize_result: Ergebnis der Optimierung
        """
        self.optimization_history.append(optimize_result)
        
        # Speichere die Optimierungsergebnisse
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        result_file = os.path.join(self.results_dir, f"optimization_{timestamp}.json")
        
        with open(result_file, 'w') as f:
            json.dump(optimize_result, f, indent=2)
        
        logger.info(f"Optimierungsergebnis gespeichert in: {result_file}")
        
        # Halte den Verlauf auf eine vernünftige Größe
        if len(self.optimization_history) > 100:
            self.optimization_history = self.optimization_history[-100:]
    
    def _process_optimization_result(self, optimize_result: Dict[str, Any]):
        """
        Verarbeitet das Optimierungsergebnis und passt die Anwendung entsprechend an.
        
        Args:
            optimize_result: Ergebnis der Optimierung
        """
        if optimize_result["status"] != "success":
            logger.warning(f"Optimierung fehlgeschlagen: {optimize_result.get('message', 'Unbekannter Fehler')}")
            return
        
        # Vergleiche aktuelles und optimales Setup
        current_setup = optimize_result.get("current_setup", "")
        optimal_setup = optimize_result.get("optimal_setup", "")
        
        if current_setup == optimal_setup:
            logger.info("Aktuelles Setup ist bereits optimal")
            
            # Erhöhe Zähler für aufeinanderfolgende erfolgreiche Optimierungen
            self.consecutive_successful_optimizations += 1
            
            # Passe das Intervall an, wenn wir mehrere erfolgreiche Optimierungen hatten
            if (self.consecutive_successful_optimizations >= 
                self.csp_config["max_consecutive_success"]):
                self._increase_optimization_interval()
            
            return
        
        # Setze den Zähler zurück, da wir eine Änderung vornehmen müssen
        self.consecutive_successful_optimizations = 0
        
        # Hier würden wir in einer realen Implementierung die Anwendung anpassen
        # Beispiel: Neue Funktionsgruppen deployen, Memory-Konfigurationen ändern, etc.
        
        logger.info(f"Optimiertes Setup gefunden: {optimal_setup} (vorher: {current_setup})")
        
        # Wenn Kostenvergleich verfügbar ist, zeige die Einsparungen an
        if "cost_comparison" in optimize_result:
            cost_comp = optimize_result["cost_comparison"]
            savings = cost_comp.get("savings_percentage", 0)
            logger.info(f"Prognostizierte Kosteneinsparung: {savings:.2f}%")
    
    def _update_metrics(self):
        """Aktualisiert die Metrik-Historie mit den neuesten Werten."""
        # Hier würden wir in einer realen Implementierung aktuelle Metriken sammeln
        # Beispiel: Durchschnittliche Latenz, Kosten, Fehlerraten, etc.
        
        # Latenz-Metriken
        latency_values = []
        for trace_id, trace in self.fusion_engine.traces.items():
            if trace.duration:
                latency_values.append(trace.duration * 1000)  # in ms
        
        if latency_values:
            avg_latency = statistics.mean(latency_values)
            
            if "latency" not in self.metrics_history:
                self.metrics_history["latency"] = []
            
            self.metrics_history["latency"].append(avg_latency)
            
            # Begrenze die Größe der Historie
            if len(self.metrics_history["latency"]) > 100:
                self.metrics_history["latency"] = self.metrics_history["latency"][-100:]
        
        # Inkrementiere den Ausführungszähler
        self.executions_since_last_optimization += 1
    
    def _get_current_metrics(self) -> Dict[str, Any]:
        """
        Gibt die aktuellen Leistungsmetriken zurück.
        
        Returns:
            Dictionary mit aktuellen Metriken
        """
        metrics = {}
        
        # Latenz-Metriken
        if "latency" in self.metrics_history and self.metrics_history["latency"]:
            recent_latencies = self.metrics_history["latency"][-10:]
            metrics["latency"] = {
                "average": statistics.mean(recent_latencies),
                "median": statistics.median(recent_latencies),
                "min": min(recent_latencies),
                "max": max(recent_latencies)
            }
            
            if len(recent_latencies) > 1:
                metrics["latency"]["std_dev"] = statistics.stdev(recent_latencies)
        
        return metrics
    
    def _increase_optimization_interval(self):
        """Erhöht das Intervall zwischen Optimierungsläufen."""
        old_interval = self.current_interval
        self.current_interval = min(self.current_interval * 2, self.csp_config["normal_interval"])
        
        if self.current_interval != old_interval:
            logger.info(f"Optimierungsintervall erhöht von {old_interval} auf {self.current_interval} Ausführungen")
    
    def _decrease_optimization_interval(self):
        """Verringert das Intervall zwischen Optimierungsläufen."""
        old_interval = self.current_interval
        self.current_interval = max(self.current_interval // 2, self.csp_config["min_interval"])
        
        if self.current_interval != old_interval:
            logger.info(f"Optimierungsintervall verringert von {old_interval} auf {self.current_interval} Ausführungen")
    
    def force_optimization(self) -> Dict[str, Any]:
        """
        Erzwingt einen sofortigen Optimierungslauf unabhängig vom geplanten Intervall.
        
        Returns:
            Das Optimierungsergebnis
        """
        logger.info("Manuell ausgelöste Optimierung wird durchgeführt...")
        
        # Sammle aktuelle Ausführungsdaten
        execution_data = self._collect_execution_data()
        
        # Führe die Optimierung durch
        optimize_result = self._run_optimization(execution_data)
        
        # Aktualisiere den Optimierungsverlauf
        self._update_optimization_history(optimize_result)
        
        # Verarbeite das Optimierungsergebnis
        self._process_optimization_result(optimize_result)
        
        # Setze den Zähler zurück
        self.executions_since_last_optimization = 0
        
        return optimize_result
    
    def get_optimization_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Gibt die letzten N Optimierungsergebnisse zurück.
        
        Args:
            limit: Maximale Anzahl der zurückzugebenden Ergebnisse
            
        Returns:
            Liste der letzten Optimierungsergebnisse
        """
        return self.optimization_history[-limit:]
    
    def update_csp_config(self, config_updates: Dict[str, Any]):
        """
        Aktualisiert die CSP-Konfiguration.
        
        Args:
            config_updates: Dictionary mit zu aktualisierenden Werten
        """
        self.csp_config.update(config_updates)
        logger.info(f"CSP-Konfiguration aktualisiert: {config_updates}")
        
        # Aktualisiere das aktuelle Intervall, falls nötig
        if "normal_interval" in config_updates:
            self.current_interval = min(self.current_interval, config_updates["normal_interval"])
        if "min_interval" in config_updates:
            self.current_interval = max(self.current_interval, config_updates["min_interval"])
    
    def apply_fusion_setup(self, setup: Dict[str, Any]) -> bool:
        """
        Wendet ein spezifisches Fusion-Setup direkt an, ohne Optimierung.
        Nützlich für manuelle Eingriffe oder Tests.
        
        Args:
            setup: Das anzuwendende Setup (mit Gruppen und Speicherkonfigurationen)
            
        Returns:
            True bei Erfolg, False bei Fehler
        """
        if not setup or not isinstance(setup, dict):
            logger.error("Ungültiges Setup-Format")
            return False
        
        try:
            # Hier würden wir das Setup in einer realen Implementierung anwenden
            # Beispiel: Neue Funktionsgruppen deployen, Memory-Konfigurationen ändern, etc.
            
            logger.info(f"Fusion-Setup manuell angewendet: {setup}")
            
            # Füge einen Eintrag zur Optimierungshistorie hinzu
            self.optimization_history.append({
                "status": "success",
                "timestamp": time.time(),
                "message": "Manuell angewendetes Setup",
                "setup": setup,
                "manual": True
            })
            
            return True
        
        except Exception as e:
            logger.error(f"Fehler beim Anwenden des Fusion-Setups: {str(e)}")
            return False
    
    def simulate_workload_change(self, workload_type: str, intensity: float = 1.0):
        """
        Simuliert eine Änderung im Workload, um die Anpassungsfähigkeit zu testen.
        Nützlich für Tests und Experimente.
        
        Args:
            workload_type: Art des Workloads ("cpu", "memory", "io", "mixed")
            intensity: Intensität der Änderung (0.0 - 1.0)
        """
        logger.info(f"Workload-Änderung simuliert: Typ={workload_type}, Intensität={intensity:.2f}")
        
        # Reduziere das Optimierungsintervall, um schneller auf die Änderung zu reagieren
        self._decrease_optimization_interval()
        
        # In einer realen Implementierung würden wir hier Lastgeneratoren steuern
        # oder Workload-Parameter anpassen
        
        # Für die Simulation fügen wir einen künstlichen Drift zu den Metriken hinzu
        if "latency" in self.metrics_history and self.metrics_history["latency"]:
            current_avg = statistics.mean(self.metrics_history["latency"][-5:])
            latency_change = 0
            
            if workload_type == "cpu":
                # CPU-intensive Workloads erhöhen die Latenz stark
                latency_change = current_avg * 0.3 * intensity
            elif workload_type == "memory":
                # Speicher-intensive Workloads erhöhen die Latenz moderat
                latency_change = current_avg * 0.2 * intensity
            elif workload_type == "io":
                # I/O-intensive Workloads erhöhen die Latenz stark für kleine Funktionen
                latency_change = current_avg * (0.4 * intensity)
            elif workload_type == "mixed":
                # Gemischte Workloads haben variable Effekte
                latency_change = current_avg * (0.25 * intensity)
            
            # Füge den Drift zu den letzten 5 Messwerten hinzu
            for i in range(5):
                if "latency" in self.metrics_history and self.metrics_history["latency"]:
                    drift_factor = 1.0 + (latency_change / current_avg)
                    new_latency = self.metrics_history["latency"][-1] * drift_factor
                    self.metrics_history["latency"].append(new_latency)
    
    def generate_report(self, include_recommendations: bool = True) -> Dict[str, Any]:
        """
        Generiert einen Bericht über den aktuellen Zustand und die Optimierungshistorie.
        
        Args:
            include_recommendations: Ob automatische Empfehlungen enthalten sein sollen
            
        Returns:
            Dictionary mit dem Bericht
        """
        current_time = datetime.now()
        
        report = {
            "timestamp": current_time.isoformat(),
            "optimizer_status": "running" if self.is_running else "stopped",
            "current_interval": self.current_interval,
            "executions_since_last_optimization": self.executions_since_last_optimization,
            "optimization_history_length": len(self.optimization_history),
            "current_metrics": self._get_current_metrics()
        }
        
        # Füge die letzten Optimierungsergebnisse hinzu
        recent_optimizations = self.get_optimization_history(5)
        if recent_optimizations:
            report["recent_optimizations"] = []
            for opt in recent_optimizations:
                # Vereinfachte Version für den Bericht
                simplified_opt = {
                    "timestamp": opt.get("timestamp", 0),
                    "status": opt.get("status", "unknown"),
                    "current_setup": opt.get("current_setup", ""),
                    "optimal_setup": opt.get("optimal_setup", "")
                }
                
                # Kostenvergleich hinzufügen, falls verfügbar
                if "cost_comparison" in opt:
                    simplified_opt["cost_comparison"] = opt["cost_comparison"]
                
                report["recent_optimizations"].append(simplified_opt)
        
        # Empfehlungen hinzufügen
        if include_recommendations and report["current_metrics"]:
            report["recommendations"] = self._generate_recommendations()
        
        return report
    
    def _generate_recommendations(self) -> List[Dict[str, Any]]:
        """
        Generiert automatische Empfehlungen basierend auf den aktuellen Metriken und der Optimierungshistorie.
        
        Returns:
            Liste von Empfehlungen
        """
        recommendations = []
        
        # Prüfe auf Optimierungspotenzial
        if (len(self.optimization_history) >= 2 and
            self.optimization_history[-1]["status"] == "success" and
            "cost_comparison" in self.optimization_history[-1]):
            
            savings = self.optimization_history[-1]["cost_comparison"].get("savings_percentage", 0)
            
            if savings > 10:
                recommendations.append({
                    "type": "cost_optimization",
                    "priority": "high" if savings > 25 else "medium",
                    "message": f"Potenzial für Kosteneinsparungen von {savings:.2f}% durch Anwendung des optimierten Setups",
                    "action": "apply_optimal_setup"
                })
        
        # Prüfe auf Leistungsprobleme
        if "latency" in self.metrics_history and len(self.metrics_history["latency"]) >= 10:
            recent_avg = statistics.mean(self.metrics_history["latency"][-5:])
            previous_avg = statistics.mean(self.metrics_history["latency"][-10:-5])
            
            if recent_avg > previous_avg * 1.2:  # 20% Anstieg
                recommendations.append({
                    "type": "performance_degradation",
                    "priority": "high" if recent_avg > previous_avg * 1.5 else "medium",
                    "message": f"Leistungsverschlechterung erkannt: Latenz ist um {((recent_avg / previous_avg) - 1) * 100:.2f}% gestiegen",
                    "action": "force_optimization"
                })
        
        # Prüfe auf Optimierungsfrequenz
        if self.executions_since_last_optimization > self.current_interval * 2:
            recommendations.append({
                "type": "optimization_frequency",
                "priority": "low",
                "message": "Lange Zeit seit der letzten Optimierung. Erwäge einen manuellen Optimierungslauf.",
                "action": "force_optimization"
            })
        
        return recommendations