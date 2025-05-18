# app/evaluation/cost_model.py
from typing import Dict, Any, List, Optional

class FaaSCostModel:
    """
    Modelliert die Kosten für verschiedene FaaS-Provider und Konfigurationen.
    
    Unterstützt:
    - Unterschiedliche Speicherkonfigurationen
    - Ausführungszeit-basierte Berechnung
    - Request-basierte Kosten
    - Verschiedene Provider-Profile
    """
    
    # Provider-Preismodelle (Beispielwerte, müssen an aktuelle Preise angepasst werden)
    PROVIDER_PROFILES = {
        "aws_lambda": {
            "request_cost": 0.0000002,  # $ pro Request
            "gb_second_cost": 0.0000166667,  # $ pro GB-Sekunde
            "free_tier": {
                "requests": 1000000,  # 1M Requests pro Monat
                "compute": 400000,    # 400K GB-Sekunden pro Monat
            }
        },
        "azure_functions": {
            "request_cost": 0.0000002,  # $ pro Request
            "gb_second_cost": 0.000016,  # $ pro GB-Sekunde
            "free_tier": {
                "requests": 1000000,  # 1M Requests pro Monat
                "compute": 400000,    # 400K GB-Sekunden pro Monat
            }
        },
        "google_cloud_functions": {
            "request_cost": 0.0000004,  # $ pro Request
            "gb_second_cost": 0.0000025,  # $ pro GB-Sekunde pro 100ms
            "free_tier": {
                "requests": 2000000,  # 2M Requests pro Monat
                "compute": 400000,    # 400K GB-Sekunden pro Monat
            }
        }
    }
    
    def __init__(self, provider: str = "aws_lambda", custom_profile: Optional[Dict[str, Any]] = None):
        """
        Initialisiert das Kostenmodell.
        
        Args:
            provider: Name des Providers ("aws_lambda", "azure_functions", "google_cloud_functions")
            custom_profile: Benutzerdefiniertes Preisprofil
        """
        if custom_profile:
            self.profile = custom_profile
        elif provider in self.PROVIDER_PROFILES:
            self.profile = self.PROVIDER_PROFILES[provider]
        else:
            raise ValueError(f"Unbekannter Provider: {provider}")
    
    def calculate_execution_cost(self, 
                                memory_mb: int, 
                                duration_ms: float, 
                                is_billable: bool = True) -> float:
        """
        Berechnet die Kosten für eine einzelne Funktionsausführung.
        
        Args:
            memory_mb: Zugewiesener Speicher in MB
            duration_ms: Ausführungsdauer in Millisekunden
            is_billable: Ob die Ausführung kostenpflichtig ist (z.B. Local-Ausführungen sind nicht direkt kostenpflichtig)
            
        Returns:
            Kosten in Dollar
        """
        if not is_billable:
            return 0
        
        # Request-Kosten
        request_cost = self.profile["request_cost"]
        
        # Berechnung der GB-Sekunden
        gb_factor = memory_mb / 1024  # Umrechnung in GB
        duration_seconds = duration_ms / 1000  # Umrechnung in Sekunden
        gb_seconds = gb_factor * duration_seconds
        
        # Kosten pro GB-Sekunde
        compute_cost = gb_seconds * self.profile["gb_second_cost"]
        
        # Gesamtkosten
        total_cost = request_cost + compute_cost
        
        return total_cost
    
    def calculate_fusion_cost(self, 
                             memory_mb: int, 
                             durations_ms: List[float], 
                             remote_invocations: List[bool]) -> Dict[str, float]:
        """
        Berechnet die Kosten für eine Fusion-Ausführung.
        
        Args:
            memory_mb: Zugewiesener Speicher in MB
            durations_ms: Liste der Ausführungsdauern in Millisekunden
            remote_invocations: Liste, die angibt, ob die entsprechende Ausführung remote ist
            
        Returns:
            Dict mit aufgeschlüsselten Kosten
        """
        total_remote_cost = 0
        total_local_cost = 0
        
        # Jede Ausführung berechnen
        for i, duration in enumerate(durations_ms):
            is_remote = remote_invocations[i] if i < len(remote_invocations) else False
            
            # Remote-Aufrufe verursachen Kosten
            if is_remote:
                cost = self.calculate_execution_cost(memory_mb, duration, True)
                total_remote_cost += cost
            else:
                # Lokale Aufrufe verursachen keine direkten Kosten, aber wir tracken sie trotzdem
                cost = self.calculate_execution_cost(memory_mb, duration, False)
                total_local_cost += cost
        
        # Gesamtkosten zurückgeben
        return {
            "remote_cost": total_remote_cost,
            "local_cost": total_local_cost,
            "total_billable_cost": total_remote_cost,
            "total_execution_cost": total_remote_cost + total_local_cost
        }
    
    def compare_fusion_setups(self, 
                             setups: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Vergleicht verschiedene Fusion-Setups basierend auf Kosten.
        
        Args:
            setups: Liste von Fusion-Setups, jedes mit:
                   - 'name': Name des Setups
                   - 'memory_mb': Zugewiesener Speicher
                   - 'durations_ms': Liste von Ausführungsdauern
                   - 'remote_invocations': Liste, ob Aufrufe remote sind
                   
        Returns:
            Dict mit Vergleichsergebnissen
        """
        results = {}
        
        for setup in setups:
            name = setup["name"]
            costs = self.calculate_fusion_cost(
                setup["memory_mb"],
                setup["durations_ms"],
                setup["remote_invocations"]
            )
            
            results[name] = costs
        
        # Günstigstes Setup identifizieren
        cheapest_setup = min(results.items(), key=lambda x: x[1]["total_billable_cost"])
        
        return {
            "setup_costs": results,
            "cheapest_setup": cheapest_setup[0],
            "cheapest_cost": cheapest_setup[1]["total_billable_cost"]
        }