# tests/validate_fusion_heuristic.py
import asyncio
import os
import sys
import logging
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from tools.config_loader import load_fusion_config, setup_fusion_environment
from app.runtime import runtime
from app.fusion import fusion_engine
from evaluation.experiment_workflow import FusionExperimentWorkflow
from evaluation.heuristic_validator import HeuristicValidator

# Logger konfigurieren
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("heuristic-validation")

# Konfigurationspfad
CONFIG_PATH = "config/configurationMetadata.json"

async def validate_function_fusion_heuristic():
    """
    Führt einen vollständigen Validierungsprozess für die Function Fusion Heuristik durch.
    
    1. Ausführen von Experimenten mit verschiedenen Fusion-Konfigurationen
    2. Analyse der Ergebnisse
    3. Validierung der Heuristik
    4. Generierung von Berichten und Visualisierungen
    """
    # Konfiguration laden und Umgebung einrichten
    config = load_fusion_config(CONFIG_PATH)
    setup_fusion_environment(config, runtime, fusion_engine)
    
    # 1. Experimente ausführen
    logger.info("===== 1. Experimente für Heuristik-Validierung ausführen =====")
    
    workflow = FusionExperimentWorkflow("heuristic_validation")
    
    # Verschiedene Testszenarien hinzufügen
    # Kurze Funktionsketten
    workflow.add_scenario(
        name="Two-Step Chain",
        functions=["add_to_cart", "cartkvstorage"],
        test_event={"userId": "user1", "productId": "prod1", "quantity": 1},
        repetitions=5
    )
    
    # Mittlere Funktionsketten
    workflow.add_scenario(
        name="Three-Step Chain",
        functions=["add_to_cart", "calculate_shipping", "checkout"],
        test_event={
            "userId": "user2", 
            "productId": "prod2", 
            "quantity": 2,
            "address": {"country": "Germany"}
        },
        repetitions=5
    )
    
    # Längere Funktionsketten
    workflow.add_scenario(
        name="Four-Step Chain",
        functions=["add_to_cart", "calculate_shipping", "checkout", "payment"],
        test_event={
            "userId": "user3", 
            "productId": "prod3", 
            "quantity": 1,
            "address": {"country": "USA"}
        },
        repetitions=3
    )
    
    # Alle Experimente ausführen
    results = await workflow.run_all_scenarios()
    results_dir = workflow.result_dir
    
    # 2. Validierung der Heuristik
    logger.info("\n===== 2. Heuristik validieren =====")
    
    validator = HeuristicValidator(results_dir)
    validator.load_results()
    validation_results = validator.validate_heuristic()
    
    # 3. Berichte und Visualisierungen generieren
    logger.info("\n===== 3. Berichte und Visualisierungen generieren =====")
    
    report_path = validator.generate_report(os.path.join(results_dir, "heuristic_validation.md"))
    validator.visualize_results(results_dir)
    
    # 4. Zusammenfassung ausgeben
    logger.info("\n===== Validierungsergebnisse =====")
    
    optimal_percent = validation_results["overall"]["optimal_percentage"]
    logger.info(f"Die Heuristik war in {optimal_percent:.1f}% der Szenarien optimal.")
    
    if validation_results["overall"]["cases_where_heuristic_fails"]:
        logger.info("Szenarien, in denen die Heuristik nicht optimal ist:")
        for case in validation_results["overall"]["cases_where_heuristic_fails"]:
            logger.info(f"- {case['scenario']}: {case['performance_difference_percent']:.2f}% langsamer")
    
    logger.info(f"Vollständiger Bericht wurde gespeichert in: {report_path}")
    logger.info(f"Alle Ergebnisse befinden sich in: {results_dir}")

if __name__ == "__main__":
    asyncio.run(validate_function_fusion_heuristic())