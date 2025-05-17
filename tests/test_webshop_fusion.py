# tests/test_webshop_fusion.py
import asyncio
import logging
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from tools.config_loader import load_fusion_config, setup_fusion_environment
from app.runtime import runtime
from app.fusion import fusion_engine
from evaluation.experiment_workflow import FusionExperimentWorkflow

# Logger konfigurieren
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("webshop-test")

# Konfigurationspfad
CONFIG_PATH = "config/configurationMetadata.json"

async def run_webshop_experiments():
    """Führt umfassende Experimente für den Webshop-Workflow durch."""
    
    # Konfiguration laden und Umgebung einrichten
    config = load_fusion_config(CONFIG_PATH)
    setup_fusion_environment(config, runtime, fusion_engine)
    
    # Experiment-Workflow erstellen
    workflow = FusionExperimentWorkflow("webshop_benchmark")
    
    # Grundlegendes Hinzufügen von Artikeln zum Warenkorb
    workflow.add_scenario(
        name="Add to Cart Flow",
        functions=["add_to_cart", "cartkvstorage"],
        test_event={
            "userId": "user123",
            "productId": "product456",
            "quantity": 2
        },
        repetitions=5
    )
    
    # Vollständiger Checkout-Prozess
    workflow.add_scenario(
        name="Complete Checkout Flow",
        functions=["add_to_cart", "calculate_shipping", "checkout", "payment"],
        test_event={
            "userId": "user789",
            "productId": "product101",
            "quantity": 1,
            "address": {
                "street": "Main St 123",
                "city": "Berlin",
                "zip": "10115",
                "country": "Germany"
            }
        },
        repetitions=3
    )
    
    # Produktsuche und -empfehlung
    workflow.add_scenario(
        name="Product Search and Recommendations",
        functions=["searchproducts", "listrecommendations"],
        test_event={
            "query": "smartphone",
            "limit": 5
        },
        repetitions=3
    )
    
    # Alle Szenarien ausführen
    await workflow.run_all_scenarios()
    
    # Bericht generieren
    workflow.generate_report()
    
    logger.info("Alle Webshop-Experimente abgeschlossen")

if __name__ == "__main__":
    asyncio.run(run_webshop_experiments())