# app/evaluation/performance_model.py
import random
import time
import asyncio
import math
import datetime
from typing import Dict, Any, Optional, Tuple, List

class PerformanceModel:
    """
    Modelliert das Performance-Verhalten von FaaS-Funktionen unter verschiedenen Bedingungen.
    
    Diese Klasse bietet realistischere Simulationen für:
    - Remote vs. lokale Ausführung
    - Memory-Auswirkungen
    - Cold-Start-Verzögerungen (optional)
    - Netzwerklatenz
    - I/O-Performance (Datenbank-Zugriffe, Speicheroperationen)
    - Regionale und tageszeitabhängige Latenzunterschiede
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        # Standard-Konfiguration
        self.config = {
            # Remote-Aufruf-Overhead (in Sekunden)
            "remote_overhead_base": 0.08,      # Basis-Overhead für Remote-Aufrufe
            "remote_overhead_jitter": 0.02,    # Zufällige Variation im Overhead
            
            # Memory-Performance-Simulation
            "memory_min": 128,                 # Minimaler Speicher (MB)
            "memory_max": 10240,               # Maximaler Speicher (MB)
            "memory_performance_factor": 0.7,  # Einfluss des Speichers auf Performance
            
            # Cold-Start-Simulation (optional)
            "cold_start_enabled": False,       # Cold-Start-Simulation aktivieren/deaktivieren
            "cold_start_base": 0.3,            # Basis-Cold-Start-Zeit (s)
            "cold_start_memory_factor": 0.3,   # Einfluss des Speichers auf Cold-Start
            
            # Payload-Größen-Effekte
            "payload_size_factor": 0.0001,     # Einfluss der Payload-Größe auf Latenz
            
            # Funktionstyp-spezifische Faktoren
            "function_type_factors": {
                "cpu_intensive": 1.0,          # Basiswert für CPU-intensive Funktionen
                "memory_intensive": 0.7,       # Memory-intensive Funktionen profitieren mehr von höherem Memory
                "io_intensive": 0.3            # I/O-intensive Funktionen profitieren weniger von höherem Memory
            },
            
            # Regionale Latenz-Konfiguration
            "regions": {
                "us-east-1": {"base_latency": 0.02, "peak_factor": 1.3},
                "us-east-2": {"base_latency": 0.025, "peak_factor": 1.25},
                "us-west-1": {"base_latency": 0.03, "peak_factor": 1.2},
                "us-west-2": {"base_latency": 0.025, "peak_factor": 1.2},
                "eu-west-1": {"base_latency": 0.02, "peak_factor": 1.4},
                "eu-central-1": {"base_latency": 0.025, "peak_factor": 1.35},
                "ap-northeast-1": {"base_latency": 0.03, "peak_factor": 1.3},
                "ap-southeast-1": {"base_latency": 0.035, "peak_factor": 1.25},
                "ap-southeast-2": {"base_latency": 0.04, "peak_factor": 1.2}
            },
            
            # I/O-Operationen Konfiguration
            "io_operations": {
                "dynamodb": {
                    "read": {"base_latency": 0.005, "cost_per_kb": 0.0000002},
                    "write": {"base_latency": 0.01, "cost_per_kb": 0.000001},
                    "query": {"base_latency": 0.02, "cost_per_kb": 0.0000004},
                    "scan": {"base_latency": 0.05, "cost_per_kb": 0.0000008}
                },
                "s3": {
                    "read": {"base_latency": 0.015, "cost_per_kb": 0.0000001},
                    "write": {"base_latency": 0.03, "cost_per_kb": 0.0000005},
                    "query": {"base_latency": None, "cost_per_kb": 0},
                    "scan": {"base_latency": None, "cost_per_kb": 0}
                },
                "rds": {
                    "read": {"base_latency": 0.01, "cost_per_kb": 0.0000003},
                    "write": {"base_latency": 0.02, "cost_per_kb": 0.0000012},
                    "query": {"base_latency": 0.03, "cost_per_kb": 0.0000005},
                    "scan": {"base_latency": 0.08, "cost_per_kb": 0.000001}
                },
                "efs": {
                    "read": {"base_latency": 0.02, "cost_per_kb": 0.0000004},
                    "write": {"base_latency": 0.025, "cost_per_kb": 0.0000006},
                    "query": {"base_latency": None, "cost_per_kb": 0},
                    "scan": {"base_latency": None, "cost_per_kb": 0}
                }
            }
        }
        
        # Konfiguration überschreiben, wenn angegeben
        if config:
            self.config.update(config)
    
    def calculate_remote_overhead(self, 
                                 payload_size_kb: float = 0,
                                 source_region: str = "us-east-1",
                                 target_region: str = "us-east-1",
                                 time_of_day: float = None) -> float:
        """
        Berechnet den Overhead für einen Remote-Funktionsaufruf mit realistischer Variabilität.
        
        Args:
            payload_size_kb: Größe der Payload in KB
            source_region: Quellregion der aufrufenden Funktion
            target_region: Zielregion der aufgerufenen Funktion
            time_of_day: Tageszeit als Stunde (0-23), None für aktuelle Zeit
            
        Returns:
            Simulierte Verzögerung in Sekunden
        """
        # Netzwerklatenz zwischen Regionen berechnen
        network_latency = self.calculate_network_latency(
            source_region, target_region, time_of_day, payload_size_kb
        )
        
        # Basis-Overhead für Funktionsaufruf
        base = self.config["remote_overhead_base"]
        jitter = random.uniform(-self.config["remote_overhead_jitter"], 
                                self.config["remote_overhead_jitter"])
        
        # Zusätzliche Verzögerung basierend auf Payload-Größe
        payload_delay = payload_size_kb * self.config["payload_size_factor"]
        
        # Gesamtverzögerung berechnen
        total_overhead = base + jitter + payload_delay + network_latency
        
        return max(0.015, total_overhead)  # Mindestens 15ms
    
    def calculate_network_latency(self, 
                                 source_region: str = "us-east-1",
                                 target_region: str = "us-east-1",
                                 time_of_day: float = None,
                                 payload_size_kb: float = 0) -> float:
        """
        Berechnet realistische Netzwerklatenz zwischen FaaS-Funktionen.
        
        Args:
            source_region: Quellregion der aufrufenden Funktion
            target_region: Zielregion der aufgerufenen Funktion
            time_of_day: Tageszeit als Stunde (0-23), None für aktuelle Zeit
            payload_size_kb: Größe der Payload in KB
        
        Returns:
            Simulierte Netzwerklatenz in Sekunden
        """
        # Verwende aktuelle Stunde, wenn keine Zeit angegeben ist
        if time_of_day is None:
            time_of_day = datetime.datetime.now().hour
        
        # Regionen-Informationen abrufen
        regions = self.config["regions"]
        source_info = regions.get(source_region, {"base_latency": 0.03, "peak_factor": 1.25})
        target_info = regions.get(target_region, {"base_latency": 0.03, "peak_factor": 1.25})
        
        # Inter-Region-Latenz-Matrix (vereinfacht)
        inter_region_latency = {
            ("us-east-1", "us-east-2"): 0.035,
            ("us-east-1", "us-west-1"): 0.07,
            ("us-east-1", "us-west-2"): 0.08,
            ("us-east-1", "eu-west-1"): 0.09,
            ("us-east-1", "eu-central-1"): 0.095,
            ("us-east-1", "ap-northeast-1"): 0.12,
            ("us-east-1", "ap-southeast-1"): 0.14,
            ("us-east-1", "ap-southeast-2"): 0.17,
            ("us-east-2", "us-west-1"): 0.065,
            ("us-east-2", "us-west-2"): 0.075,
            ("us-east-2", "eu-west-1"): 0.095,
            ("us-west-1", "us-west-2"): 0.025,
            ("eu-west-1", "eu-central-1"): 0.03,
            # Weitere Kombinationen können nach Bedarf hinzugefügt werden
        }
        
        # Basis-Latenz ermitteln
        if source_region == target_region:
            base_latency = source_info["base_latency"]
        else:
            region_pair = (source_region, target_region)
            region_pair_reversed = (target_region, source_region)
            
            if region_pair in inter_region_latency:
                base_latency = inter_region_latency[region_pair]
            elif region_pair_reversed in inter_region_latency:
                base_latency = inter_region_latency[region_pair_reversed]
            else:
                # Fallback: Ungefähre Schätzung basierend auf den individuellen Regionen
                base_latency = (source_info["base_latency"] + target_info["base_latency"] + 0.05)
        
        # Tageszeit-Faktor (erhöhte Latenz während Spitzenzeiten)
        time_factor = self._calculate_time_based_load_factor(time_of_day)
        
        # Regionale Peak-Faktoren berücksichtigen
        peak_factor = max(source_info["peak_factor"], target_info["peak_factor"]) if time_factor > 1.1 else 1.0
        
        # Zufallsfaktor für Netzwerkfluktuationen
        # Normalverteilung mit Mittelwert 1.0 und Standardabweichung 0.1
        jitter_factor = random.normalvariate(1.0, 0.1)
        
        # Payload-Einfluss (größere Payloads erhöhen die Latenz)
        payload_factor = max(1.0, 1.0 + payload_size_kb * 0.0001)
        
        # Gesamtlatenz berechnen
        total_latency = base_latency * time_factor * peak_factor * jitter_factor * payload_factor
        
        return max(0.01, total_latency)  # Mindestens 10ms
    
    def calculate_memory_performance_effect(
        self,
        memory_mb: int,
        function_type: str = "cpu_intensive",
        workload_intensity: float = 1.0
    ) -> float:
        memory_to_vcpu_mapping = {
            128: 0.125, 256: 0.25, 512: 0.5, 1024: 1.0, 1536: 1.5,
            2048: 2.0, 3008: 2.5, 4096: 3.0, 5120: 3.5, 6144: 4.0,
            7168: 4.5, 8192: 5.0, 10240: 6.0
        }

        memory_values = sorted(memory_to_vcpu_mapping.keys())

        if memory_mb <= memory_values[0]:
            vcpu_allocation = memory_to_vcpu_mapping[memory_values[0]]
        elif memory_mb >= memory_values[-1]:
            vcpu_allocation = memory_to_vcpu_mapping[memory_values[-1]]
        elif memory_mb in memory_to_vcpu_mapping:
            vcpu_allocation = memory_to_vcpu_mapping[memory_mb]
        else:
            lower_memory = max([m for m in memory_values if m < memory_mb])
            upper_memory = min([m for m in memory_values if m > memory_mb])

            lower_vcpu = memory_to_vcpu_mapping[lower_memory]
            upper_vcpu = memory_to_vcpu_mapping[upper_memory]

            if upper_memory == lower_memory:
                vcpu_allocation = lower_vcpu  # Kein Bruch möglich
            else:
                fraction = (memory_mb - lower_memory) / (upper_memory - lower_memory)
                vcpu_allocation = lower_vcpu + fraction * (upper_vcpu - lower_vcpu)

        type_factors = self.config["function_type_factors"]
        type_factor = type_factors.get(function_type, type_factors["cpu_intensive"])

        base_performance = 1.0

        if function_type == "cpu_intensive":
            performance_gain = vcpu_allocation * type_factor * workload_intensity
        elif function_type == "memory_intensive":
            performance_gain = math.log1p(vcpu_allocation * 2) * type_factor * workload_intensity
        else:
            performance_gain = math.sqrt(vcpu_allocation) * type_factor * workload_intensity

        return max(0.2, base_performance - min(0.8, performance_gain))

    
    def calculate_cold_start_delay(self, memory_mb: int) -> float:
        """
        Berechnet die Cold-Start-Verzögerung basierend auf zugewiesenem Speicher.
        
        Args:
            memory_mb: Zugewiesener Speicher in MB
            
        Returns:
            Cold-Start-Verzögerung in Sekunden
        """
        if not self.config["cold_start_enabled"]:
            return 0
        
        # Normalisiere memory_mb
        memory_normalized = (memory_mb - self.config["memory_min"]) / (
            self.config["memory_max"] - self.config["memory_min"]
        )
        memory_normalized = max(0, min(1, memory_normalized))
        
        # Mehr Speicher = längerer Cold-Start
        memory_effect = memory_normalized * self.config["cold_start_memory_factor"]
        
        return self.config["cold_start_base"] * (1 + memory_effect)
    
    def simulate_io_operation(self,
                             operation_type: str,
                             data_size_kb: float = 1.0,
                             storage_type: str = "dynamodb",
                             region: str = "us-east-1",
                             time_of_day: float = None) -> Dict[str, Any]:
        """
        Simuliert verschiedene I/O-Operationen und gibt Ausführungszeit und Kosten zurück.
        
        Args:
            operation_type: Art der Operation (read, write, query, scan)
            data_size_kb: Datengröße in KB
            storage_type: Speichertyp (dynamodb, s3, rds, efs, etc.)
            region: AWS-Region
            time_of_day: Tageszeit als Stunde (0-23)
        
        Returns:
            Dict mit Latenz und Kosten der Operation
        """
        # Verwende aktuelle Stunde, wenn keine Zeit angegeben ist
        if time_of_day is None:
            time_of_day = datetime.datetime.now().hour
            
        # I/O-Operationen Konfiguration abrufen
        io_operations = self.config["io_operations"]
        
        # Standardwerte für unbekannte Speichertypen
        default_ops = {
            "read": {"base_latency": 0.015, "cost_per_kb": 0.0000002},
            "write": {"base_latency": 0.025, "cost_per_kb": 0.000001},
            "query": {"base_latency": 0.03, "cost_per_kb": 0.0000004},
            "scan": {"base_latency": 0.06, "cost_per_kb": 0.0000008}
        }
        
        # Storage-Typ Informationen abrufen
        storage_ops = io_operations.get(storage_type, default_ops)
        operation_info = storage_ops.get(operation_type, default_ops[operation_type]) if operation_type in storage_ops else None
        
        if not operation_info or operation_info.get("base_latency") is None:
            return {
                "success": False,
                "error": f"Operation {operation_type} nicht unterstützt für {storage_type}",
                "latency": 0,
                "cost": 0
            }
        
        # Datengröße-Faktor (größere Datenmengen = mehr Zeit, aber nicht linear)
        size_factor = 1.0
        if data_size_kb > 0:
            # Logarithmische Skalierung - doppelte Datenmenge ≠ doppelte Zeit
            if operation_type in ["read", "write"]:
                size_factor = 1.0 + math.log10(max(1, data_size_kb)) * 0.3
            elif operation_type in ["query", "scan"]:
                size_factor = 1.0 + math.log10(max(1, data_size_kb)) * 0.5
        
        # Auslastungsfaktor basierend auf Tageszeit
        load_factor = self._calculate_time_based_load_factor(time_of_day)
        
        # Regionale Latenz-Variationen
        region_factor = 1.0
        if region != "us-east-1":  # us-east-1 als Referenz
            # Leichte Variationen je nach Region
            region_variations = {
                "us-east-2": 1.05,
                "us-west-1": 1.1,
                "us-west-2": 1.05,
                "eu-west-1": 1.1,
                "eu-central-1": 1.15,
                "ap-northeast-1": 1.2,
                "ap-southeast-1": 1.25,
                "ap-southeast-2": 1.3,
            }
            region_factor = region_variations.get(region, 1.15)
        
        # Zufällige Variation für realistische Streuung
        variation_factor = random.normalvariate(1.0, 0.15)  # 15% Standardabweichung
        
        # Latenz und Kosten berechnen
        latency = (operation_info["base_latency"] * size_factor * 
                  load_factor * region_factor * variation_factor)
        
        # Kosten berechnen
        cost = data_size_kb * operation_info["cost_per_kb"]
        
        return {
            "success": True,
            "latency": latency,
            "cost": cost,
            "storage_type": storage_type,
            "operation_type": operation_type,
            "data_size_kb": data_size_kb
        }
    
    def _calculate_time_based_load_factor(self, time_of_day: float = None) -> float:
        """
        Berechnet den Lastfaktor basierend auf der Tageszeit.
        
        Args:
            time_of_day: Tageszeit als Stunde (0-23), None für aktuelle Zeit
            
        Returns:
            Lastfaktor (1.0 = durchschnittliche Last)
        """
        if time_of_day is None:
            time_of_day = datetime.datetime.now().hour
        
        # Typisches Tageslastprofil
        if 0 <= time_of_day < 6:  # Nachts
            return 0.7
        elif 6 <= time_of_day < 9:  # Morgen ramp-up
            return 0.9 + (time_of_day - 6) * 0.1
        elif 9 <= time_of_day < 12:  # Vormittag (Spitzenzeit)
            return 1.3
        elif 12 <= time_of_day < 14:  # Mittagszeit
            return 1.1
        elif 14 <= time_of_day < 17:  # Nachmittag (Spitzenzeit)
            return 1.3
        elif 17 <= time_of_day < 20:  # Abend ramp-down
            return 1.2 - (time_of_day - 17) * 0.1
        else:  # Spätabend
            return 0.8
    
    def simulate_execution_time(self, 
                               base_execution_time: float,
                               memory_mb: int,
                               is_remote: bool, 
                               is_cold_start: bool = False,
                               payload_size_kb: float = 0,
                               function_type: str = "cpu_intensive",
                               source_region: str = "us-east-1",
                               target_region: str = "us-east-1",
                               time_of_day: float = None,
                               workload_intensity: float = 1.0,
                               io_operations: List[Dict[str, Any]] = None) -> Tuple[float, Dict[str, Any]]:
        """
        Simuliert die Ausführungszeit einer Funktion unter Berücksichtigung aller Faktoren.
        
        Args:
            base_execution_time: Basis-Ausführungszeit ohne Berücksichtigung von Faktoren
            memory_mb: Zugewiesener Speicher in MB
            is_remote: Ob die Funktion remote aufgerufen wird
            is_cold_start: Ob es sich um einen Cold-Start handelt
            payload_size_kb: Größe der Payload in KB
            function_type: Art der Funktion
            source_region: Quellregion der aufrufenden Funktion
            target_region: Zielregion der aufgerufenen Funktion
            time_of_day: Tageszeit als Stunde (0-23)
            workload_intensity: Intensität der Arbeitslast (0.0 - 1.0)
            io_operations: Liste von I/O-Operationen, die während der Ausführung durchgeführt werden
            
        Returns:
            Tuple mit (simulierte_ausführungszeit, details_dict)
        """
        details = {
            "base_time": base_execution_time,
            "memory_mb": memory_mb,
            "is_remote": is_remote,
            "is_cold_start": is_cold_start,
            "function_type": function_type,
            "components": {}
        }
        
        # Basis-Faktoren: CPU/Memory-Performance
        time_multiplier = self.calculate_memory_performance_effect(memory_mb, function_type, workload_intensity)
        cpu_execution_time = base_execution_time * time_multiplier
        details["components"]["cpu_execution"] = cpu_execution_time
        
        total_execution_time = cpu_execution_time
        
        # Remote-Overhead, falls anwendbar
        if is_remote:
            remote_overhead = self.calculate_remote_overhead(
                payload_size_kb, source_region, target_region, time_of_day
            )
            total_execution_time += remote_overhead
            details["components"]["remote_overhead"] = remote_overhead
        
        # Cold-Start-Verzögerung, falls anwendbar
        if is_cold_start:
            cold_start_delay = self.calculate_cold_start_delay(memory_mb)
            total_execution_time += cold_start_delay
            details["components"]["cold_start"] = cold_start_delay
        
        # I/O-Operationen, falls vorhanden
        io_total_time = 0
        io_details = []
        
        if io_operations:
            for op in io_operations:
                op_type = op.get("operation_type", "read")
                storage_type = op.get("storage_type", "dynamodb")
                data_size = op.get("data_size_kb", 1.0)
                op_region = op.get("region", target_region)
                
                io_result = self.simulate_io_operation(
                    op_type, data_size, storage_type, op_region, time_of_day
                )
                
                if io_result["success"]:
                    io_total_time += io_result["latency"]
                    io_details.append(io_result)
            
            total_execution_time += io_total_time
            details["components"]["io_operations"] = io_total_time
            details["io_details"] = io_details
        
        details["total_execution_time"] = total_execution_time
        
        return total_execution_time, details
    
    async def apply_execution_delay(self, 
                                  base_execution_time: float,
                                  memory_mb: int,
                                  is_remote: bool, 
                                  is_cold_start: bool = False,
                                  payload_size_kb: float = 0,
                                  function_type: str = "cpu_intensive",
                                  source_region: str = "us-east-1", 
                                  target_region: str = "us-east-1",
                                  time_of_day: float = None,
                                  workload_intensity: float = 1.0,
                                  io_operations: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Wendet die simulierte Ausführungsverzögerung an und gibt Details zurück.
        
        Args:
            Gleiche Parameter wie simulate_execution_time
            
        Returns:
            Details zur simulierten Ausführung
        """
        delay, details = self.simulate_execution_time(
            base_execution_time, memory_mb, is_remote, 
            is_cold_start, payload_size_kb, function_type,
            source_region, target_region, time_of_day,
            workload_intensity, io_operations
        )
        
        # Simulierte Verzögerung anwenden
        await asyncio.sleep(delay)
        
        # Rückgabewert erweitern
        details["applied_delay"] = delay
        
        return details