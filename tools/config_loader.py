# config_loader.py
import json
import os
import logging
import importlib


# Mapping von Funktionsnamen in der Konfiguration zu echten Modulpfaden
FUNCTION_NAME_MAPPING = {
    "add_to_cart": "webshop.addcartitem",
    "calculate_shipping": "webshop.shipmentquote",
    "checkout": "webshop.checkout",
    "get_cart": "webshop.getcart",
    "cartkvstorage": "webshop.cartkvstorage",
    # Füge hier nach Bedarf weitere Mappings hinzu
}

logger = logging.getLogger("config-loader")
logging.basicConfig(level=logging.INFO)

def load_fusion_config(config_path: str):
    """Lädt Fusion-Konfiguration aus einer JSON-Datei"""
    with open(config_path, 'r') as f:
        config = json.load(f)
    logger.info(f"Konfiguration geladen von: {config_path}")
    return config

def setup_fusion_environment(config, runtime, fusion_engine):
    """Richtet die Fusion-Umgebung basierend auf der Konfiguration ein"""
    for timestamp, config_data in config.items():
        for source_func, rules in config_data.get("rules", {}).items():

            # Versuche source_func zu registrieren
            _register_function_if_missing(source_func, runtime)

            for target_func, rule_data in rules.items():
                _register_function_if_missing(target_func, runtime)

                fusion_name = f"{source_func}_to_{target_func}"
                fusion_engine.register_fusion(
                    fusion_name,
                    [source_func, target_func],
                    {
                        "rules": {
                            source_func: {
                                target_func: rule_data
                            }
                        }
                    }
                )
                logger.info(f"Fusion registriert: {fusion_name}")

# Zusätzlich alle bekannten Funktionen aus dem Mapping registrieren (z.B. nested calls)
    for func_name in FUNCTION_NAME_MAPPING:
        if func_name not in runtime.functions:
            _register_function_if_missing(func_name, runtime)

def load_function_definitions(functions_path: str, runtime):
    """Lädt Funktionen aus einer JSON-Datei und registriert sie im Runtime"""
    with open(functions_path, 'r') as f:
        functions = json.load(f)

    for func_name, props in functions.items():
        try:
            module_path = props["module"]
            memory = props.get("memory", 128)
            timeout = props.get("timeout", 3)

            module = importlib.import_module(module_path)
            runtime.register(func_name, module.handler, memory=memory, timeout=timeout)
            logger.info(f"Funktion '{func_name}' erfolgreich registriert (modul: {module_path}, memory: {memory}, timeout: {timeout})")
        except Exception as e:
            logger.warning(f"Fehler beim Registrieren von Funktion '{func_name}': {str(e)}")
            runtime.register(func_name, lambda e, ctx=None, cb=None: {"warning": f"{func_name} ist ein Dummy"}, memory=64)


def _register_function_if_missing(func_name: str, runtime):
    """Hilfsfunktion zur dynamischen Funktionsregistrierung mit Fallback"""
    if func_name in runtime.functions:
        return

    # Mapping berücksichtigen
    mapped_name = FUNCTION_NAME_MAPPING.get(func_name, func_name)
    module_path = f"functions.{mapped_name}.handler"

    try:
        module = importlib.import_module(module_path)
        runtime.register(func_name, module.handler)
        logger.info(f"Funktion '{func_name}' erfolgreich registriert aus Modul '{module_path}'")
    except (ImportError, AttributeError) as e:
        logger.warning(f"Konnte Funktion '{func_name}' nicht laden: {str(e)}")
        runtime.register(func_name, lambda e, ctx=None, cb=None: {"warning": f"{func_name} ist ein Dummy"}, memory=64)
        logger.info(f"Dummy-Funktion für '{func_name}' registriert")
