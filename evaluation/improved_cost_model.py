from typing import Dict, Any, List, Optional, Tuple
import math
import logging

logger = logging.getLogger("lambda-sim.cost-model")

class ImprovedCostModel:
    """
    Erweitertes Kostenmodell für die Bewertung von Function Fusion Setups
    basierend auf realistischen Cloud-Provider-Preisen.
    """
    
    # Provider-Preismodelle (Stand: April 2025, basierend auf öffentlichen Cloud-Preisen)
    PROVIDER_PROFILES = {
        "aws_lambda": {
            "request_cost": 0.0000002,  # $ pro Request
            "gb_second_cost": 0.0000166667,  # $ pro GB-Sekunde
            "free_tier": {
                "requests": 1000000,  # 1M Requests pro Monat
                "compute": 400000,  # 400K GB-Sekunden pro Monat
            },
            "min_billing_duration": 1,  # ms
            "billing_resolution": 1,  # ms (seit 12/2020)
            "double_billing_factor": 1.0,  # Faktor für Double-Billing bei synchronen Aufrufen
        },
        "azure_functions": {
            "request_cost": 0.0000002,  # $ pro Request
            "gb_second_cost": 0.000016,  # $ pro GB-Sekunde
            "free_tier": {
                "requests": 1000000,  # 1M Requests pro Monat
                "compute": 400000,  # 400K GB-Sekunden pro Monat
            },
            "min_billing_duration": 100,  # ms
            "billing_resolution": 1,  # ms
            "double_billing_factor": 1.0,  # Faktor für Double-Billing bei synchronen Aufrufen
        },
        "google_cloud_functions": {
            "request_cost": 0.0000004,  # $ pro Request
            "gb_second_cost": 0.0000025,  # $ pro GB-Sekunde pro 100ms
            "free_tier": {
                "requests": 2000000,  # 2M Requests pro Monat
                "compute": 400000,  # 400K GB-Sekunden pro Monat
            },
            "min_billing_duration": 100,  # ms
            "billing_resolution": 100,  # ms (100ms Schritte)
            "double_billing_factor": 1.0,  # Faktor für Double-Billing bei synchronen Aufrufen
        }
    }
    
    def __init__(self, 
                 provider: str = "aws_lambda", 
                 custom_profile: Optional[Dict[str, Any]] = None,
                 apply_free_tier: bool = False):
        """
        Initialisiert das Kostenmodell.
        
        Args:
            provider: Name des Providers ("aws_lambda", "azure_functions", "google_cloud_functions")
            custom_profile: Benutzerdefiniertes Preisprofil
            apply_free_tier: Ob das Free Tier in der Kostenberechnung berücksichtigt werden soll
        """
        if custom_profile:
            self.profile = custom_profile
        elif provider in self.PROVIDER_PROFILES:
            self.profile = self.PROVIDER_PROFILES[provider]
        else:
            raise ValueError(f"Unbekannter Provider: {provider}")
        
        self.provider_name = provider
        self.apply_free_tier = apply_free_tier
        self.total_requests = 0
        self.total_compute_gb_seconds = 0
        
        logger.info(f"Kostenmodell initialisiert für Provider: {provider}")
        if self.apply_free_tier:
            logger.info("Free Tier wird in der Kostenberechnung berücksichtigt")
    
    def calculate_execution_cost(self,
                              memory_mb: int,
                              duration_ms: float,
                              is_billable: bool = True,
                              is_synchronous_call: bool = False) -> float:
        """
        Berechnet die Kosten für eine einzelne Funktionsausführung.
        
        Args:
            memory_mb: Zugewiesener Speicher in MB
            duration_ms: Ausführungsdauer in Millisekunden
            is_billable: Ob die Ausführung kostenpflichtig ist (z.B. Local-Ausführungen können anders abgerechnet werden)
            is_synchronous_call: Ob es sich um einen synchronen Aufruf handelt (relevant für Double-Billing)
            
        Returns:
            Kosten in Dollar
        """
        if not is_billable:
            return 0
        
        # Request-Kosten
        request_cost = self.profile["request_cost"]
        
        # Abrechnungsdauer berechnen (unter Berücksichtigung von Mindestdauer und Auflösung)
        min_billing_duration = self.profile["min_billing_duration"]
        billing_resolution = self.profile["billing_resolution"]
        
        # Mindestdauer anwenden
        billed_duration = max(duration_ms, min_billing_duration)
        
        # Auf Abrechnungsauflösung aufrunden
        billed_duration = math.ceil(billed_duration / billing_resolution) * billing_resolution
        
        # Berechnung der GB-Sekunden
        gb_factor = memory_mb / 1024  # Umrechnung in GB
        duration_seconds = billed_duration / 1000  # Umrechnung in Sekunden
        gb_seconds = gb_factor * duration_seconds
        
        # Kosten pro GB-Sekunde
        compute_cost = gb_seconds * self.profile["gb_second_cost"]
        
        # Double-Billing-Faktor anwenden (für synchrone Aufrufe)
        if is_synchronous_call:
            compute_cost *= self.profile["double_billing_factor"]
        
        # Gesamtkosten
        total_cost = request_cost + compute_cost
        
        # Tracking für Free Tier
        if self.apply_free_tier:
            self.total_requests += 1
            self.total_compute_gb_seconds += gb_seconds
        
        return total_cost
    
    def calculate_fusion_cost(self,
                           fusion_setup: Dict[str, Any],
                           execution_data: List[Dict[str, Any]]) -> Dict[str, float]:
        """
        Berechnet die Kosten für eine Function Fusion Konfiguration.
        
        Args:
            fusion_setup: Die zu bewertende Fusion-Konfiguration
                {
                    "groups": [["A", "B"], ["C"]],
                    "memory_configurations": {"A.B": 256, "C": 128}
                }
            execution_data: Liste mit Ausführungsdaten
                [
                    {
                        "function": "A",
                        "duration_ms": 100,
                        "memory_mb": 128,
                        "caller": null,
                        "is_sync": true
                    },
                    ...
                ]
                
        Returns:
            Dict mit aufgeschlüsselten Kosten
        """
        # Initialisiere Kostenzähler
        cost_breakdown = {
            "request_cost": 0.0,
            "compute_cost": 0.0,
            "total_cost": 0.0,
            "fusion_groups": {}
        }
        
        # Fusionsgruppen in ein Dictionary umwandeln für schnelleren Zugriff
        groups_dict = {}
        for group in fusion_setup.get("groups", []):
            group_key = ".".join(sorted(group))
            memory_mb = fusion_setup.get("memory_configurations", {}).get(group_key, 128)
            
            for func in group:
                groups_dict[func] = {
                    "group": group,
                    "group_key": group_key,
                    "memory_mb": memory_mb
                }
        
        # Verarbeite jede Ausführung
        for exec_data in execution_data:
            func_name = exec_data.get("function")
            duration_ms = exec_data.get("duration_ms", 0)
            caller = exec_data.get("caller")
            is_sync = exec_data.get("is_sync", False)
            
            # Wenn die Funktion in keiner Gruppe ist, überspringen
            if func_name not in groups_dict:
                continue
            
            # Informationen zur Fusionsgruppe abrufen
            group_info = groups_dict[func_name]
            group_key = group_info["group_key"]
            memory_mb = group_info["memory_mb"]
            
            # Kosten berechnen
            # Eine Funktion ist billable, wenn:
            # 1. Sie hat keinen Aufrufer (Root-Aufruf)
            # 2. Sie wird von einer Funktion außerhalb ihrer Gruppe aufgerufen
            is_billable = True
            if caller:
                caller_group = groups_dict.get(caller, {}).get("group_key", "")
                # Wenn Aufrufer und Funktion in derselben Gruppe sind, ist es ein lokaler Aufruf
                if caller_group == group_key:
                    is_billable = False
            
            # Berechne Kosten für diese Ausführung
            execution_cost = self.calculate_execution_cost(
                memory_mb=memory_mb,
                duration_ms=duration_ms,
                is_billable=is_billable,
                is_synchronous_call=is_sync
            )
            
            # Kosten zur Gesamtsumme und Gruppenaufschlüsselung hinzufügen
            cost_breakdown["total_cost"] += execution_cost
            
            if is_billable:
                # Request-Kosten
                cost_breakdown["request_cost"] += self.profile["request_cost"]
                
                # Compute-Kosten
                compute_cost = execution_cost - self.profile["request_cost"]
                cost_breakdown["compute_cost"] += compute_cost
                
                # Gruppenaufschlüsselung
                if group_key not in cost_breakdown["fusion_groups"]:
                    cost_breakdown["fusion_groups"][group_key] = 0
                cost_breakdown["fusion_groups"][group_key] += execution_cost
        
        # Free Tier Berechnung
        if self.apply_free_tier:
            free_tier = self.profile.get("free_tier", {})
            free_tier_requests = free_tier.get("requests", 0)
            free_tier_compute = free_tier.get("compute", 0)
            
            # Berechne, wie viel vom Free Tier bereits verbraucht wurde
            used_requests_percentage = min(1.0, self.total_requests / free_tier_requests) if free_tier_requests > 0 else 1.0
            used_compute_percentage = min(1.0, self.total_compute_gb_seconds / free_tier_compute) if free_tier_compute > 0 else 1.0
            
            # Angepasste Kosten unter Berücksichtigung des Free Tiers
            adjusted_request_cost = cost_breakdown["request_cost"] * max(0, 1 - used_requests_percentage)
            adjusted_compute_cost = cost_breakdown["compute_cost"] * max(0, 1 - used_compute_percentage)
            
            # Gesamtkosten aktualisieren
            cost_breakdown["free_tier_savings"] = adjusted_request_cost + adjusted_compute_cost
            cost_breakdown["total_cost_after_free_tier"] = cost_breakdown["total_cost"] - cost_breakdown["free_tier_savings"]
        
        return cost_breakdown
    
    def compare_fusion_setups(self,
                           setups: List[Dict[str, Any]],
                           execution_data: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
        """
        Vergleicht verschiedene Fusion-Setups basierend auf Kosten.
        
        Args:
            setups: Liste von Fusion-Setups mit Namen, Gruppen und Speicherkonfigurationen
            execution_data: Dictionary mit Ausführungsdaten für jedes Setup
                
        Returns:
            Dict mit Vergleichsergebnissen
        """
        results = {}
        
        for setup in setups:
            setup_name = setup.get("name", "unknown")
            setup_execution_data = execution_data.get(setup_name, [])
            
            # Kosten für dieses Setup berechnen
            setup_costs = self.calculate_fusion_cost(setup, setup_execution_data)
            results[setup_name] = setup_costs
        
        # Günstigstes Setup identifizieren
        cheapest_setup = min(results.items(), key=lambda x: x[1]["total_cost"])
        cheapest_name = cheapest_setup[0]
        cheapest_cost = cheapest_setup[1]["total_cost"]
        
        # Kosteneinsparungen für jedes Setup im Vergleich zur teuersten Option
        if results:
            most_expensive_setup = max(results.items(), key=lambda x: x[1]["total_cost"])
            most_expensive_cost = most_expensive_setup[1]["total_cost"]
            
            savings = {}
            for name, cost_data in results.items():
                total_cost = cost_data["total_cost"]
                absolute_savings = most_expensive_cost - total_cost
                percentage_savings = (absolute_savings / most_expensive_cost) * 100 if most_expensive_cost > 0 else 0
                savings[name] = {
                    "absolute_savings": absolute_savings,
                    "percentage_savings": percentage_savings
                }
        else:
            savings = {}
        
        return {
            "setup_costs": results,
            "cheapest_setup": cheapest_name,
            "cheapest_cost": cheapest_cost,
            "cost_savings": savings,
            "provider": self.provider_name
        }
    
    def estimate_monthly_cost(self,
                           setup: Dict[str, Any],
                           execution_data: List[Dict[str, Any]],
                           invocations_per_month: int) -> Dict[str, float]:
        """
        Schätzt die monatlichen Kosten für ein Function Fusion Setup.
        
        Args:
            setup: Das zu bewertende Fusion-Setup
            execution_data: Liste mit Ausführungsdaten
            invocations_per_month: Geschätzte Anzahl der Aufrufe pro Monat
                
        Returns:
            Dict mit monatlichen Kostenschätzungen
        """
        # Berechne die durchschnittlichen Kosten pro Aufruf
        single_execution_costs = self.calculate_fusion_cost(setup, execution_data)
        avg_cost_per_invocation = single_execution_costs["total_cost"]
        
        # Monatliche Kosten schätzen
        monthly_cost = avg_cost_per_invocation * invocations_per_month
        
        # Free Tier berücksichtigen
        monthly_cost_after_free_tier = monthly_cost
        free_tier_savings = 0
        
        if self.apply_free_tier:
            free_tier = self.profile.get("free_tier", {})
            free_tier_requests = free_tier.get("requests", 0)
            free_tier_compute = free_tier.get("compute", 0)
            
            # Geschätzter GB-Sekunden-Verbrauch pro Monat
            avg_gb_seconds_per_invocation = single_execution_costs["compute_cost"] / self.profile["gb_second_cost"]
            monthly_gb_seconds = avg_gb_seconds_per_invocation * invocations_per_month
            
            # Free Tier Anrechnung
            covered_requests = min(invocations_per_month, free_tier_requests)
            covered_gb_seconds = min(monthly_gb_seconds, free_tier_compute)
            
            # Kosteneinsparungen durch Free Tier
            request_savings = covered_requests * self.profile["request_cost"]
            compute_savings = covered_gb_seconds * self.profile["gb_second_cost"]
            free_tier_savings = request_savings + compute_savings
            
            # Monatliche Kosten nach Free Tier
            monthly_cost_after_free_tier = monthly_cost - free_tier_savings
        
        return {
            "monthly_invocations": invocations_per_month,
            "cost_per_invocation": avg_cost_per_invocation,
            "monthly_cost_before_free_tier": monthly_cost,
            "free_tier_savings": free_tier_savings,
            "monthly_cost_after_free_tier": max(0, monthly_cost_after_free_tier)
        }
    
    def reset_free_tier_tracking(self):
        """
        Setzt die Zähler für das Free Tier zurück.
        Nützlich für neue Simulationen.
        """
        self.total_requests = 0
        self.total_compute_gb_seconds = 0
        logger.info("Free Tier Tracking zurückgesetzt")
    
    def update_profile(self, profile_updates: Dict[str, Any]):
        """
        Aktualisiert das Preisprofil mit neuen Werten.
        
        Args:
            profile_updates: Dictionary mit zu aktualisierenden Werten
        """
        self.profile.update(profile_updates)
        logger.info(f"Preisprofil für {self.provider_name} aktualisiert: {profile_updates}")
    
    def set_double_billing_factor(self, factor: float):
        """
        Setzt den Faktor für Double-Billing bei synchronen Aufrufen.
        Ein höherer Wert bewertet synchrone Aufrufe stärker negativ.
        
        Args:
            factor: Double-Billing-Faktor (1.0 = standardmäßige Kostenschätzung)
        """
        self.profile["double_billing_factor"] = max(1.0, factor)
        logger.info(f"Double-Billing-Faktor gesetzt auf: {self.profile['double_billing_factor']}")