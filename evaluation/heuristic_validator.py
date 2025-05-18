# evaluation/heuristic_validator.py
import json
import os
from typing import Dict, List, Any, Tuple
import pandas as pd
import matplotlib.pyplot as plt

class HeuristicValidator:
    """
    Validiert die Heuristik aus dem Function Fusion Paper:
    - Synchrone Tasks lokal ausführen
    - Asynchrone Tasks remote ausführen
    
    Analysiert Testergebnisse, um festzustellen, ob diese Heuristik optimal ist.
    """
    
    def __init__(self, results_dir: str):
        self.results_dir = results_dir
        self.results = {}
        self.summary = {}
    
    def load_results(self):
        """Lädt alle Ergebnisse aus dem Ergebnisverzeichnis."""
        for filename in os.listdir(self.results_dir):
            if filename.endswith('.json') and filename != 'summary.json':
                filepath = os.path.join(self.results_dir, filename)
                try:
                    with open(filepath, 'r') as f:
                        self.results[filename] = json.load(f)
                except Exception as e:
                    print(f"Fehler beim Laden von {filename}: {str(e)}")
    
    def validate_heuristic(self) -> Dict[str, Any]:
        """
        Analysiert die Ergebnisse und überprüft, ob die Heuristik optimal ist.
        
        Returns:
            Dict mit Validierungsergebnissen
        """
        validation_results = {
            "scenarios": {},
            "overall": {
                "heuristic_optimal_count": 0,
                "total_scenarios": 0,
                "optimal_percentage": 0,
                "cases_where_heuristic_fails": []
            }
        }
        
        for filename, result_data in self.results.items():
            scenario_name = filename.split('.')[0]
            
            # Für jedes Szenario die Heuristik überprüfen
            scenario_result = self._validate_scenario(result_data)
            validation_results["scenarios"][scenario_name] = scenario_result
            
            # Gesamtstatistik aktualisieren
            validation_results["overall"]["total_scenarios"] += 1
            if scenario_result["heuristic_is_optimal"]:
                validation_results["overall"]["heuristic_optimal_count"] += 1
            else:
                validation_results["overall"]["cases_where_heuristic_fails"].append({
                    "scenario": scenario_name,
                    "optimal_config": scenario_result["optimal_config"],
                    "heuristic_config": scenario_result["heuristic_config"],
                    "performance_difference_percent": scenario_result["performance_difference_percent"]
                })
        
        # Prozentsatz berechnen, in dem die Heuristik optimal ist
        if validation_results["overall"]["total_scenarios"] > 0:
            validation_results["overall"]["optimal_percentage"] = (
                validation_results["overall"]["heuristic_optimal_count"] / 
                validation_results["overall"]["total_scenarios"] * 100
            )
        
        self.summary = validation_results
        return validation_results
    
    def _validate_scenario(self, result_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validiert die Heuristik für ein einzelnes Szenario."""
        # Finde die schnellste Konfiguration
        results = result_data.get("results", {})
        fastest_config = None
        fastest_time = float('inf')
        
        for config_name, config_result in results.items():
            avg_time = config_result.get("avg_execution_time", float('inf'))
            if avg_time < fastest_time:
                fastest_time = avg_time
                fastest_config = config_name
        
        # Finde die Konfiguration, die der Heuristik entspricht
        # Die Heuristik ist: sync=local, async=remote
        heuristic_config = None
        heuristic_time = None
        
        for config_name, config_result in results.items():
            # Überprüfen, ob die Konfiguration der Heuristik entspricht
            # Hier nehmen wir an, dass die Konfiguration "config_local_local_..." heißt,
            # wenn alle synchronen Aufrufe lokal sind
            if config_name.startswith("config_local_"):
                heuristic_config = config_name
                heuristic_time = config_result.get("avg_execution_time", float('inf'))
                break
        
        # Ergebnisse zusammenfassen
        heuristic_is_optimal = heuristic_config == fastest_config
        
        # Performance-Unterschied berechnen
        performance_difference = 0
        performance_difference_percent = 0
        
        if heuristic_time is not None and fastest_time != float('inf'):
            performance_difference = heuristic_time - fastest_time
            if fastest_time > 0:
                performance_difference_percent = (performance_difference / fastest_time) * 100
        
        return {
            "optimal_config": fastest_config,
            "optimal_time": fastest_time,
            "heuristic_config": heuristic_config,
            "heuristic_time": heuristic_time,
            "heuristic_is_optimal": heuristic_is_optimal,
            "performance_difference": performance_difference,
            "performance_difference_percent": performance_difference_percent
        }
    
    def generate_report(self, output_file: str = "heuristic_validation_report.md"):
        """Generiert einen Bericht zur Heuristik-Validierung."""
        if not self.summary:
            self.validate_heuristic()
        
        report = [
            "# Function Fusion Heuristic Validation Report",
            "",
            "## Summary",
            "",
            f"The heuristic (sync tasks = local, async tasks = remote) was optimal in "
            f"{self.summary['overall']['heuristic_optimal_count']} out of "
            f"{self.summary['overall']['total_scenarios']} scenarios "
            f"({self.summary['overall']['optimal_percentage']:.1f}%).",
            "",
            "## Detailed Results"
        ]
        
        for scenario, results in self.summary["scenarios"].items():
            report.append(f"### Scenario: {scenario}")
            report.append("")
            report.append(f"* **Optimal configuration:** {results['optimal_config']}")
            report.append(f"* **Optimal execution time:** {results['optimal_time']:.3f}s")
            report.append(f"* **Heuristic configuration:** {results['heuristic_config']}")
            report.append(f"* **Heuristic execution time:** {results['heuristic_time']:.3f}s")
            
            if results["heuristic_is_optimal"]:
                report.append("* **Result:** ✅ Heuristic is optimal")
            else:
                report.append(f"* **Result:** ❌ Heuristic is not optimal (performance difference: {results['performance_difference_percent']:.2f}%)")
            
            report.append("")
        
        if self.summary["overall"]["cases_where_heuristic_fails"]:
            report.append("## Cases Where Heuristic Fails")
            report.append("")
            
            for case in self.summary["overall"]["cases_where_heuristic_fails"]:
                report.append(f"### {case['scenario']}")
                report.append(f"* **Optimal config:** {case['optimal_config']}")
                report.append(f"* **Heuristic config:** {case['heuristic_config']}")
                report.append(f"* **Performance difference:** {case['performance_difference_percent']:.2f}%")
                report.append("")
        
        # Report speichern
        with open(output_file, 'w') as f:
            f.write('\n'.join(report))
        
        print(f"Heuristic validation report saved to: {output_file}")
        return output_file
    
    def visualize_results(self, output_dir: str = "."):
        """Visualisiert die Validierungsergebnisse."""
        if not self.summary:
            self.validate_heuristic()
        
        # 1. Tortendiagramm: Wie oft ist die Heuristik optimal?
        plt.figure(figsize=(8, 6))
        labels = ['Optimal', 'Not Optimal']
        sizes = [
            self.summary["overall"]["heuristic_optimal_count"],
            self.summary["overall"]["total_scenarios"] - self.summary["overall"]["heuristic_optimal_count"]
        ]
        colors = ['#4CAF50', '#F44336']
        plt.pie(sizes, labels=labels, colors=colors, autopct='%1.1f%%', startangle=90)
        plt.axis('equal')
        plt.title('Heuristic Optimality Across Scenarios')
        plt.savefig(os.path.join(output_dir, 'heuristic_optimality_pie.png'))
        plt.close()
        
        # 2. Balkendiagramm: Performance-Vergleich für Szenarien, in denen die Heuristik nicht optimal ist
        if self.summary["overall"]["cases_where_heuristic_fails"]:
            scenarios = []
            percentages = []
            
            for case in self.summary["overall"]["cases_where_heuristic_fails"]:
                scenarios.append(case["scenario"])
                percentages.append(case["performance_difference_percent"])
            
            plt.figure(figsize=(10, 6))
            plt.barh(scenarios, percentages)
            plt.xlabel('Performance Difference (%)')
            plt.title('Performance Loss When Using Heuristic')
            plt.tight_layout()
            plt.savefig(os.path.join(output_dir, 'heuristic_performance_difference.png'))
            plt.close()
        
        print(f"Visualizations saved to: {output_dir}")