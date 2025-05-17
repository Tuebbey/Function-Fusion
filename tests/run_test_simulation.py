import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from evaluation.performance_model import PerformanceModel

def main():
    # Beispielkonfiguration (kann angepasst werden)
    config = {
        "cold_start_enabled": True  # Cold Start aktivieren für den Test
    }

    # Instanz des PerformanceModels erstellen
    model = PerformanceModel(config=config)

    # Beispiel-Testparameter (ähnlich wie aus FunctionFusion)
    test_params = {
        "base_execution_time": 0.5,          # Basis-Ausführungszeit der Funktion in Sekunden
        "memory_mb": 1024,                   # Zugewiesener Speicher
        "is_remote": False,                  # Lokal statt remote
        "is_cold_start": True,               # Cold Start simulieren
        "payload_size_kb": 256,              # Größe der übertragenen Daten
        "function_type": "cpu_intensive",    # Typ der Funktion
        "source_region": "us-east-1",
        "target_region": "us-east-1",
        "time_of_day": 10.0,                 # 10 Uhr morgens = Spitzenzeit
        "workload_intensity": 0.8,           # Mittlere Last
        "io_operations": [
            {
                "operation_type": "read",
                "data_size_kb": 100,
                "storage_type": "dynamodb",
                "region": "us-east-1"
            },
            {
                "operation_type": "write",
                "data_size_kb": 50,
                "storage_type": "s3",
                "region": "us-east-1"
            }
        ]
    }

    # Simulation ausführen
    total_time, details = model.simulate_execution_time(**test_params)

    # Ergebnis anzeigen
    print("==== Simulationsergebnis ====")
    print(f"Gesamtausführungszeit: {total_time:.4f} Sekunden")
    print("Details:")
    for key, value in details.items():
        print(f"{key}: {value}")

if __name__ == "__main__":
    main()
