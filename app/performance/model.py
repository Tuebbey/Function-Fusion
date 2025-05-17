import random
import math
import time
import asyncio
from typing import Dict, Any, List, Optional, Tuple

class PerformanceModel:
    """Modelliert die Leistungscharakteristika einer Lambda-Funktion."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = {
            # CPU-Skalierungsfaktoren basierend auf Speicher
            "memory_cpu_ratio": 1769,  # 1,769 MB = 1 vCPU
            "base_cpu_factor": 0.5,
            
            # I/O-Simulation
            "io_latency_base": 5,  # ms
            "io_latency_jitter": 2,  # ms
            
            # Memory-Nutzung
            "memory_usage_factor": 0.3,  # Faktor der zugewiesenen Speichergröße
            "memory_usage_jitter": 0.1,  # Zufällige Variation
            
            # Cold-Start-Simulation
            "cold_start_enabled": True,
            "cold_start_base": 0.3,  # Basis-Cold-Start-Zeit (s)
            "cold_start_memory_factor": 0.3,  # Einfluss des Speichers auf Cold-Start
            
            # Workload-Typen
            "workload_factors": {
                "cpu_intensive": 1.0,  # Basiswert für CPU-intensive Funktionen
                "memory_intensive": 0.7,  # Memory-intensive Funktionen profitieren mehr von höherem Memory
                "io_intensive": 0.3  # I/O-intensive Funktionen profitieren weniger von höherem Memory
            }
        }
        
        if config:
            self.config.update(config)
    
    def simulate_execution_time(self, base_time: float, memory_mb: int, workload_type: str = "cpu_intensive") -> float:
        """Berechnet die simulierte Ausführungszeit basierend auf den Ressourcenparametern."""
        # CPU-Skalierung basierend auf Memory
        vcpu_equivalent = memory_mb / self.config["memory_cpu_ratio"]
        
        # Workload-abhängiger Skalierungsfaktor
        workload_factor = self.config["workload_factors"].get(workload_type, 1.0)
        
        # Nicht-lineare Skalierung
        if memory_mb < 512:
            scaling_factor = 1.0 / (self.config["base_cpu_factor"] + 
                                 (1 - self.config["base_cpu_factor"]) * (memory_mb / 512))
        else:
            scaling_factor = 1.0 / (self.config["base_cpu_factor"] + 
                                 (1 - self.config["base_cpu_factor"]) * vcpu_equivalent)
        
        # Zufällige Variation hinzufügen
        jitter = random.uniform(-0.05, 0.1)
        
        return base_time * scaling_factor * workload_factor * (1 + jitter)
    
    def estimate_memory_usage(self, memory_mb: int, base_usage_mb: Optional[float] = None) -> float:
        """Schätzt die Speichernutzung einer Funktion."""
        if base_usage_mb is None:
            # Standardnutzung basierend auf zugewiesener Speichergröße
            base_usage_mb = memory_mb * self.config["memory_usage_factor"]
        
        # Zufällige Variation
        jitter = random.uniform(
            -self.config["memory_usage_jitter"],
            self.config["memory_usage_jitter"]
        )
        
        return min(memory_mb, max(10, base_usage_mb * (1 + jitter)))
    
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
        memory_normalized = min(1, memory_mb / 3000)  # Maximal 3000MB betrachten
        
        # Mehr Speicher = längerer Cold-Start (wegen größerem Container)
        memory_effect = memory_normalized * self.config["cold_start_memory_factor"]
        
        # Basis-Cold-Start + Speichereffekt + Jitter
        jitter = random.uniform(-0.05, 0.1)  # -50ms bis +100ms
        
        return self.config["cold_start_base"] * (1 + memory_effect) + jitter
    
    def simulate_io_operation(self, operation_type: str, data_size_kb: float = 1.0) -> float:
        """Simuliert eine I/O-Operation mit realistischer Verzögerung."""
        # Basis-Latenz für verschiedene Operationstypen
        base_latencies = {
            "read": self.config["io_latency_base"],
            "write": self.config["io_latency_base"] * 2,
            "query": self.config["io_latency_base"] * 4,
            "scan": self.config["io_latency_base"] * 8
        }
        
        # Standardwert, falls Operationstyp unbekannt
        base_latency = base_latencies.get(operation_type, self.config["io_latency_base"])
        
        # Datengröße-Faktor (größere Datenmengen = mehr Zeit, aber nicht linear)
        size_factor = math.log1p(data_size_kb) * 0.1
        
        # Jitter hinzufügen
        jitter = random.uniform(
            -self.config["io_latency_jitter"],
            self.config["io_latency_jitter"]
        )
        
        return (base_latency + size_factor + jitter) / 1000  # Umrechnung in Sekunden
        
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
            Details zur simulierten Ausführung
        """
        delay, details = self.simulate_execution_time_detailed(
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
    
    def simulate_execution_time_detailed(self,
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
        time_multiplier = self.simulate_execution_time(base_execution_time, memory_mb, function_type)
        cpu_execution_time = base_execution_time * time_multiplier
        details["components"]["cpu_execution"] = cpu_execution_time
        
        total_execution_time = cpu_execution_time
        
        # Remote-Overhead, falls anwendbar
        remote_overhead = 0
        if is_remote:
            # Einfacher Overhead-Wert für Remote-Aufrufe
            remote_overhead = 0.05  # 50ms Overhead
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
                data_size = op.get("data_size_kb", 1.0)
                io_time = self.simulate_io_operation(op_type, data_size)
                io_total_time += io_time
                io_details.append({"operation": op_type, "time": io_time})
            
            total_execution_time += io_total_time
            details["components"]["io_operations"] = io_total_time
            details["io_details"] = io_details
        
        details["total_execution_time"] = total_execution_time
        return total_execution_time, details