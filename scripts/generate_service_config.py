import os
import json

# Basisverzeichnis mit deinen Funktionen
FUNCTIONS_DIR = "functions/webshop"
OUTPUT_PATH = "config/services.json"

def function_to_container_name(name: str) -> str:
    return name.lower().replace("_", "-")

def scan_functions(base_dir: str) -> dict:
    services = {}

    for root, dirs, files in os.walk(base_dir):
        for d in dirs:
            func_name = d
            full_path = os.path.join(root, d)
            handler_path = os.path.join(full_path, "handler.py")

            if os.path.exists(handler_path):
                clean_name = func_name.lower()
                services[clean_name] = function_to_container_name(clean_name)

        break  # Nur oberstes Verzeichnis scannen (keine tiefe Rekursion)

    return services

def save_to_json(data: dict, path: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"✅ Service config written to: {path}")

if __name__ == "__main__":
    services = scan_functions(FUNCTIONS_DIR)
    save_to_json(services, OUTPUT_PATH)
