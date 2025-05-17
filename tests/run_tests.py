# tests/run_tests.py
import asyncio
import logging
import sys
import os
import json
from datetime import datetime

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from tools.config_loader import (
    load_fusion_config, 
    setup_fusion_environment, 
    load_function_definitions
)
from app.runtime import runtime
from app.fusion import fusion_engine
from evaluation.performance_model import PerformanceModel
from evaluation.cost_model import FaaSCostModel
from evaluation.experiment_runner import FusionTestRunner

# Logger konfigurieren
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test-runner")

# Konfigurationspfad
TEST_CONFIG_PATH = "config/configurationMetadata.json"
FUNCTION_CONFIG_PATH = "config/Function_set_1.json"

# Einfache Testfälle
SIMPLE_TEST_CASES = [
    {
        "name": "Test Local Fusion",
        "fusion": "add_to_cart_to_calculate_shipping",
        "input": {
            "userId": "u123",
            "productId": "p456",
            "quantity": 2
        },
        "mode": "sync"
    }
]

# Erweiterte Testszenarien
AUTOMATED_TEST_SCENARIOS = [
    {
        "name": "Webshop Checkout Flow",
        "functions": ["add_to_cart", "calculate_shipping", "process_payment"],
        "input": {
            "userId": "user123",
            "productId": "prod456",
            "quantity": 2
        },
        "repetitions": 3,
        "modes": ["sync"]
    },
    # Weitere Szenarien hier ergänzen ...
]

async def run_simple_tests():
    """Führt einfache Tests mit vordefinierten Fusionen durch."""
    load_function_definitions(FUNCTION_CONFIG_PATH, runtime)
    config = load_fusion_config(TEST_CONFIG_PATH)
    setup_fusion_environment(config, runtime, fusion_engine)

    for test in SIMPLE_TEST_CASES:
        logger.info(f"\n▶ Starte Test: {test['name']} (Modus: {test['mode']})")
        result = await fusion_engine.execute(
            name=test["fusion"],
            event=test["input"],
            runtime=runtime,
            execution_mode=test["mode"]
        )
        logger.info(f"✅ Ergebnis ({test['fusion']}): {result}\n")

async def run_automated_tests():
    """Führt automatisierte Tests mit verschiedenen Fusion-Konfigurationen durch."""
    load_function_definitions(FUNCTION_CONFIG_PATH, runtime)
    config = load_fusion_config(TEST_CONFIG_PATH)
    setup_fusion_environment(config, runtime, fusion_engine)

    performance_model = PerformanceModel()
    cost_model = FaaSCostModel(provider="aws_lambda")
    test_runner = FusionTestRunner(runtime, fusion_engine, cost_model, performance_model)

    os.makedirs("results", exist_ok=True)

    for scenario in AUTOMATED_TEST_SCENARIOS:
        logger.info(f"\n===== Starte automatisiertes Testszenario: {scenario['name']} =====")
        results = await test_runner.run_batch_tests(
            functions=scenario["functions"],
            test_event=scenario["input"],
            repetitions=scenario.get("repetitions", 3),
            modes=scenario.get("modes", ["sync"])
        )
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"results/{scenario['name'].replace(' ', '_').lower()}_{timestamp}.json"
        test_runner.save_results(filename)

        logger.info("\n===== Testergebnis-Zusammenfassung =====")
        if "analysis" in results:
            analysis = results["analysis"]
            if "fastest_configuration" in analysis:
                fastest = analysis["fastest_configuration"]
                logger.info(f"Schnellste Konfiguration: {fastest['name']} ({fastest['avg_execution_time']:.2f}s)")
            if "most_reliable_configuration" in analysis:
                reliable = analysis["most_reliable_configuration"]
                logger.info(f"Zuverlässigste Konfiguration: {reliable['name']} (Erfolgsrate: {reliable['success_rate']*100:.1f}%)")

async def main():
    """Hauptfunktion zum Ausführen der Tests."""
    test_mode = "simple"
    if len(sys.argv) > 1:
        test_mode = sys.argv[1]

    if test_mode in ["auto", "all"]:
        await run_automated_tests()
    if test_mode in ["simple", "all"]:
        await run_simple_tests()

if __name__ == "__main__":
    asyncio.run(main())
