# run_ignite_tests.py
import asyncio
import logging
import argparse
from lambda_ignite_manager import AWSLambdaIgniteManager

logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("ignite-tests")

async def run_single_test():
    """Führt einen einzelnen Test mit Ignite aus"""
    logger.info("Starte einzelnen Test mit Ignite")
    
    # Initialisiere den Lambda Ignite Manager
    manager = AWSLambdaIgniteManager()
    
    try:
        # Erstelle Test-Event
        event = {
            "operation": "test",
            "userId": "test_user",
            "io_params": {
                "iterations": 5,
                "file_size_kb": 10,
                "enable_fsync": False
            }
        }
        
        # Führe Test für cartkvstorage aus
        logger.info("Teste cartkvstorage-Funktion")
        result = manager.invoke_function("cartkvstorage", event, memory_mb=128)
        logger.info(f"Ergebnis: {result}")
        
        # Führe Test mit Fusion aus
        logger.info("Teste Fusion von getcart und cartkvstorage")
        fusion_event = {
            "operation": "fusion_test",
            "userId": "test_user",
            "fusion_group": ["getcart", "cartkvstorage"],
            "io_params": {
                "iterations": 5,
                "file_size_kb": 10,
                "enable_fsync": False
            }
        }
        
        fusion_result = manager.invoke_function("getcart", fusion_event, memory_mb=256)
        logger.info(f"Fusion-Ergebnis: {fusion_result}")
        
    finally:
        # Bereinige VMs
        await manager.cleanup()
        logger.info("Test abgeschlossen und VMs bereinigt")

async def run_fusion_optimizer():
    """Führt den FunctionFusionOptimizer mit Ignite aus"""
    logger.info("Starte FunctionFusionOptimizer mit Ignite")
    
    # Importiere den Optimizer
    from app.optimizer.fusion_optimizer import FunctionFusionOptimizer, run_function_fusion_optimization
    
    # Starte Optimierung
    await run_function_fusion_optimization(test_count=10, parallel=True, max_workers=4)
    
    logger.info("Optimierung abgeschlossen")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ignite-basierte Tests für Function Fusion")
    parser.add_argument("--mode", choices=["single", "optimize"], default="single",
                      help="Testmodus: 'single' für einen einzelnen Test, 'optimize' für den Optimizer")
    parser.add_argument("--debug", action="store_true", help="Debug-Logging aktivieren")
    
    args = parser.parse_args()
    
    if args.debug:
        for logger_name in ["ignite-tests", "ignite-manager", "lambda-ignite-manager", "fusion_optimizer"]:
            logging.getLogger(logger_name).setLevel(logging.DEBUG)
    
    if args.mode == "single":
        asyncio.run(run_single_test())
    else:
        asyncio.run(run_fusion_optimizer())