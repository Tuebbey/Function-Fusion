import random
import time
import asyncio
import uuid
from typing import Dict, Tuple, List, Any, Optional

class NetworkModel:
    """Modelliert das Netzwerkverhalten zwischen Lambda-Funktionen."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = {
            # Regions-Latenzmatrix (in ms)
            "region_latency": {
                ("us-east-1", "us-east-1"): 1,
                ("us-east-1", "us-west-2"): 65,
                ("us-east-1", "eu-west-1"): 85,
                ("us-west-2", "us-west-2"): 1,
                ("us-west-2", "eu-west-1"): 130,
                ("eu-west-1", "eu-west-1"): 1
            },
            
            # Bandbreiteneinschränkungen (in Mbps)
            "region_bandwidth": {
                "us-east-1": 10000,  # 10 Gbps
                "us-west-2": 10000,
                "eu-west-1": 8000
            },
            
            # Fehlerraten
            "network_failure_rate": 0.01,  # 1% Basiswahrscheinlichkeit
            "network_failure_rate_cross_region": 0.02,  # 2% für regionsübergreifende Aufrufe
            
            # Aufrufverzögerungen
            "invoke_overhead": 20,  # ms für einen Function-Call innerhalb einer Region
            "invoke_overhead_cross_region": 40  # ms für einen Function-Call zwischen Regionen
        }
        
        if config:
            self.config.update(config)
        
        # Aktive Transfers für Bandbreitensimulation
        self.active_transfers = {}
    
    def calculate_network_latency(self, source_region: str, target_region: str, 
                                 payload_size_kb: float = 0) -> float:
        """Berechnet die Netzwerklatenz zwischen zwei Regionen."""
        # Finde die Basislatenz
        region_pair = (source_region, target_region)
        reverse_pair = (target_region, source_region)
        
        if region_pair in self.config["region_latency"]:
            base_latency = self.config["region_latency"][region_pair]
        elif reverse_pair in self.config["region_latency"]:
            base_latency = self.config["region_latency"][reverse_pair]
        else:
            # Standardlatenz für unbekannte Paare
            base_latency = 100
        
        # Füge Jitter hinzu
        jitter = random.uniform(-base_latency * 0.1, base_latency * 0.2)
        
        # Payload-Größeneffekte
        size_factor = 0.01 * payload_size_kb
        
        return max(1, base_latency + jitter + size_factor)
    
    def should_simulate_failure(self, source_region: str, target_region: str) -> bool:
        """Bestimmt, ob ein Netzwerkfehler simuliert werden soll."""
        if source_region == target_region:
            return random.random() < self.config["network_failure_rate"]
        else:
            return random.random() < self.config["network_failure_rate_cross_region"]
    
    async def simulate_function_invocation(self, source_region: str, target_region: str, 
                                          payload_size_kb: float = 0) -> float:
        """Simuliert die Verzögerung bei einem Funktionsaufruf."""
        # Bestimme Overhead basierend auf Regionen
        if source_region == target_region:
            overhead = self.config["invoke_overhead"]
        else:
            overhead = self.config["invoke_overhead_cross_region"]
        
        # Netzwerklatenz basierend auf Regionen und Payload
        latency = self.calculate_network_latency(source_region, target_region, payload_size_kb)
        
        # Gesamtverzögerung
        total_delay_ms = overhead + latency
        
        # Simuliere die Verzögerung
        await asyncio.sleep(total_delay_ms / 1000)
        
        return total_delay_ms
    
    async def transfer_data(self, source_region: str, target_region: str, size_kb: float) -> float:
        """
        Simuliert eine Datenübertragung zwischen zwei Regionen mit Berücksichtigung von Bandbreite.
        
        Args:
            source_region: Quellregion
            target_region: Zielregion
            size_kb: Größe der zu übertragenden Daten in KB
            
        Returns:
            Übertragungszeit in ms
        """
        # Bestimme verfügbare Bandbreite
        source_bandwidth = self.config["region_bandwidth"].get(source_region, 5000)  # Mbps
        target_bandwidth = self.config["region_bandwidth"].get(target_region, 5000)  # Mbps
        
        # Die langsamere Region bestimmt die Geschwindigkeit
        bandwidth_mbps = min(source_bandwidth, target_bandwidth)
        
        # Berücksichtige aktive Transfers in der Region
        active_count_source = sum(1 for t in self.active_transfers.values() 
                               if t["source"] == source_region or t["target"] == source_region)
        active_count_target = sum(1 for t in self.active_transfers.values() 
                               if t["source"] == target_region or t["target"] == target_region)
        
        # Teile Bandbreite durch aktive Transfers + 1 (dieser Transfer)
        if active_count_source > 0:
            source_bandwidth /= (active_count_source + 1)
        if active_count_target > 0:
            target_bandwidth /= (active_count_target + 1)
        
        effective_bandwidth = min(source_bandwidth, target_bandwidth)
        
        # Berechne Übertragungszeit (KB * 8 = Kilobits)
        transfer_time_ms = (size_kb * 8) / effective_bandwidth * 1000
        
        # Registriere den aktiven Transfer
        transfer_id = str(uuid.uuid4())
        self.active_transfers[transfer_id] = {
            "source": source_region,
            "target": target_region,
            "size_kb": size_kb,
            "start_time": time.time()
        }
        
        # Simuliere die Übertragungszeit
        await asyncio.sleep(transfer_time_ms / 1000)
        
        # Entferne den Transfer aus den aktiven Transfers
        del self.active_transfers[transfer_id]
        
        return transfer_time_ms