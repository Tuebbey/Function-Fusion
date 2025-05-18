# evaluation/experiment_workflow.py
import asyncio
import json
import os
import logging
from typing import Dict, List, Any, Optional
import matplotlib.pyplot as plt
import pandas as pd
from datetime import datetime

from app.runtime import runtime
from app.fusion import fusion_engine
from .performance_model import PerformanceModel
from .cost_model import FaaSCostModel
from .experiment_runner import FusionTestRunner

logger = logging.getLogger("experiment-workflow")
logger.setLevel(logging.INFO)

class FusionExperimentWorkflow:
    """
    Führt systematische Experimente zur Evaluierung verschiedener Function Fusion Strategien durch.
    """
    
    def __init__(self, 
                 experiment_name: str, 
                 output_dir: str = "results"):
        self.experiment_name = experiment_name
        self.output_dir = output_dir
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Modelle initialisieren
        self.performance_model = PerformanceModel()
        self.cost_model = FaaSCostModel(provider="aws_lambda")
        
        # TestRunner erstellen
        self.test_runner = FusionTestRunner(
            runtime, fusion_engine, self.cost_model, self.performance_model
        )
        
        # Output-Verzeichnis erstellen
        self.result_dir = os.path.join(output_dir, f"{experiment_name}_{self.timestamp}")
        os.makedirs(self.result_dir, exist_ok=True)
        
        # Experiment-Daten
        self.scenarios = []
        self.results = {}
        
    def add_scenario(self, 
                    name: str, 
                    functions: List[str],
                    test_event: Dict[str, Any],
                    repetitions: int = 3,
                    modes: List[str] = ["sync"]):
        """Fügt ein Testszenario hinzu."""
        scenario = {
            "name": name,
            "functions": functions,
            "test_event": test_event,
            "repetitions": repetitions,
            "modes": modes
        }
        self.scenarios.append(scenario)
        return self
    
    async def run_all_scenarios(self):
        """Führt alle registrierten Testszenarien aus."""
        results_summary = {}
        
        for i, scenario in enumerate(self.scenarios):
            logger.info(f"\n===== Szenario {i+1}/{len(self.scenarios)}: {scenario['name']} =====")
            
            # Einzelnes Szenario ausführen
            scenario_results = await self.test_runner.run_batch_tests(
                functions=scenario["functions"],
                test_event=scenario["test_event"],
                repetitions=scenario.get("repetitions", 3),
                modes=scenario.get("modes", ["sync"])
            )
            
            # Ergebnisse speichern
            scenario_filename = f"{scenario['name'].replace(' ', '_').lower()}.json"
            scenario_path = os.path.join(self.result_dir, scenario_filename)
            
            with open(scenario_path, 'w') as f:
                json.dump(scenario_results, f, indent=2)
            
            results_summary[scenario['name']] = {
                "file": scenario_path,
                "analysis": scenario_results.get("analysis", {})
            }
            
            # Visualisierung generieren
            self._generate_visualizations(scenario['name'], scenario_results)
        
        # Gesamtzusammenfassung speichern
        summary_path = os.path.join(self.result_dir, "summary.json")
        with open(summary_path, 'w') as f:
            json.dump(results_summary, f, indent=2)
        
        self.results = results_summary
        return results_summary
    
    def _generate_visualizations(self, scenario_name: str, results: Dict[str, Any]):
        """Generiert Visualisierungen der Ergebnisse."""
        try:
            # Daten für die Visualisierung vorbereiten
            configs = []
            exec_times = []
            
            for config_name, result in results.get("results", {}).items():
                configs.append(config_name)
                exec_times.append(result.get("avg_execution_time", 0))
            
            if not configs:
                return
            
            # DataFrame erstellen
            df = pd.DataFrame({
                "Configuration": configs,
                "Execution Time (s)": exec_times
            })
            
            # Nach Ausführungszeit sortieren
            df = df.sort_values("Execution Time (s)")
            
            # Visualisierung erstellen
            plt.figure(figsize=(12, 6))
            plt.barh(df["Configuration"], df["Execution Time (s)"])
            plt.xlabel("Execution Time (seconds)")
            plt.title(f"Performance Comparison - {scenario_name}")
            plt.tight_layout()
            
            # Speichern
            viz_path = os.path.join(self.result_dir, f"{scenario_name.replace(' ', '_').lower()}_perf.png")
            plt.savefig(viz_path)
            plt.close()
            
            logger.info(f"Visualisierung gespeichert: {viz_path}")
            
        except Exception as e:
            logger.error(f"Fehler bei der Generierung der Visualisierung: {str(e)}")
    
    def generate_report(self):
        """Generiert einen Bericht der Ergebnisse."""
        if not self.results:
            logger.warning("Keine Ergebnisse für den Bericht verfügbar")
            return
        
        report = [
            f"# Function Fusion Experiment Report: {self.experiment_name}",
            f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## Summary of Results",
            ""
        ]
        
        for scenario_name, scenario_results in self.results.items():
            report.append(f"### Scenario: {scenario_name}")
            
            analysis = scenario_results.get("analysis", {})
            
            if "fastest_configuration" in analysis:
                fastest = analysis["fastest_configuration"]
                report.append(f"* **Fastest Configuration:** {fastest.get('name', 'N/A')} ({fastest.get('avg_execution_time', 0):.2f}s)")
            
            if "most_reliable_configuration" in analysis:
                reliable = analysis["most_reliable_configuration"]
                report.append(f"* **Most Reliable Configuration:** {reliable.get('name', 'N/A')} (Success Rate: {reliable.get('success_rate', 0)*100:.1f}%)")
            
            report.append("")
        
        # Fazit zur Heuristik
        report.append("## Comparison with Original Heuristic")
        report.append("The original Function Fusion heuristic suggests:")
        report.append("* Tasks called synchronously should be fused locally")
        report.append("* Tasks called asynchronously should be placed in remote functions")
        report.append("")
        report.append("Based on our experiments, this heuristic was:")
        
        # Hier müsste eine Analyse erfolgen, ob die Heuristik in den Tests optimal war
        
        # Report speichern
        report_path = os.path.join(self.result_dir, "report.md")
        with open(report_path, 'w') as f:
            f.write('\n'.join(report))
        
        logger.info(f"Bericht gespeichert: {report_path}")
        return report_path