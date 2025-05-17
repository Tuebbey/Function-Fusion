# run_tests.py
import asyncio
import logging
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from tools.config_loader import load_fusion_config, setup_fusion_environment
from app.runtime import runtime
from app.fusion import fusion_engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test-runner")

TEST_CONFIG_PATH = "config/configurationMetadata.json"

TEST_CASES = [
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

async def run_tests():
    config = load_fusion_config(TEST_CONFIG_PATH)
    setup_fusion_environment(config, runtime, fusion_engine)

    for test in TEST_CASES:
        logger.info(f"\n▶ Starte Test: {test['name']} (Modus: {test['mode']})")
        result = await fusion_engine.execute(
            name=test["fusion"],
            event=test["input"],
            runtime=runtime,
            execution_mode=test["mode"]
        )
        logger.info(f"✅ Ergebnis ({test['fusion']}): {result}\n")

if __name__ == "__main__":
    asyncio.run(run_tests())
