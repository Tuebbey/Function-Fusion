# app/communication/service_model.py

import random
import time
import logging
import json
from typing import Dict, Any, Optional, List, Tuple

logger = logging.getLogger("lambda-sim.service-model")

class ServiceCommunicationModel:
    """
    Modelliert die Service-zu-Service-Kommunikation in Serverless-Umgebungen.
    
    Diese Klasse simuliert verschiedene Kommunikationsmuster zwischen Serverless-Funktionen
    und anderen Diensten, einschließlich API Gateway, Event-basierte Dienste, und direkter 
    HTTP-Kommunikation.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        # Standard-Konfiguration
        self.config = {
            # API Gateway Konfiguration
            "api_gateway": {
                "regional_latency": 25,         # Basis-Latenz in ms für regionale Deployments
                "edge_latency": 50,             # Basis-Latenz in ms für Edge-Deployments
                "private_latency": 15,          # Basis-Latenz in ms für private Deployments
                "throttling_rate": 10000,       # Anfragen pro Sekunde
                "burst_capacity": 5000,         # Burst-Kapazität
                "authentication_overhead": {
                    "none": 0,                  # Keine Auth
                    "api_key": 5,               # API-Key Validierung in ms
                    "iam": 15,                  # IAM-Autorisierung in ms
                    "cognito": 25,              # Cognito User Pools in ms
                    "oauth": 30,                # OAuth/JWT in ms
                    "lambda_authorizer": 50,    # Lambda-Authorizer in ms
                },
                "cost_per_request": 0.000004,   # $ pro Anfrage (4$ pro 1M Anfragen)
                "cost_per_gb": 0.09             # $ pro GB Datenübertragung
            },
            
            # Event-basierte Dienste
            "event_services": {
                "sns": {
                    "publish_latency": 20,      # Basis-Latenz in ms für Veröffentlichung
                    "delivery_latency": 50,     # Basis-Latenz in ms für Zustellung
                    "cost_per_million": 0.50,   # $ pro Million Nachrichten
                },
                "sqs": {
                    "send_latency": 15,         # Basis-Latenz in ms für Senden
                    "receive_latency": 10,      # Basis-Latenz in ms für Empfang
                    "dlq_latency": 5,           # Zusätzliche Latenz für DLQ
                    "cost_per_million": 0.40,   # $ pro Million Anfragen
                },
                "eventbridge": {
                    "publish_latency": 25,      # Basis-Latenz in ms für Veröffentlichung
                    "routing_latency": 15,      # Basis-Latenz in ms für Routing
                    "cost_per_million": 1.00,   # $ pro Million Ereignisse
                },
                "kinesis": {
                    "write_latency": 15,        # Basis-Latenz in ms für Schreiben
                    "read_latency": 70,         # Basis-Latenz in ms für Lesen (inkl. Polling)
                    "cost_per_shard_hour": 0.015, # $ pro Shard-Stunde
                    "cost_per_million_put": 0.014, # $ pro Million Put-Einheiten
                }
            },
            
            # HTTP/REST Kommunikation
            "http": {
                "overhead": 5,                  # Basis-HTTP-Overhead in ms
                "connection_setup": 10,         # TCP-Verbindungsaufbau in ms
                "keep_alive_benefit": 8,        # Ersparnis bei Keep-Alive in ms
                "serialization": {
                    "json": 0.05,               # ms pro KB für JSON
                    "xml": 0.1,                 # ms pro KB für XML
                    "protobuf": 0.01,           # ms pro KB für Protocol Buffers
                    "avro": 0.02                # ms pro KB für Avro
                },
                "compression": {
                    "none": 1.0,                # Kein Kompressionsfaktor
                    "gzip": 0.3,                # Typischer gzip-Kompressionsfaktor
                    "brotli": 0.2,              # Typischer brotli-Kompressionsfaktor
                }
            },
            
            # Service Mesh
            "service_mesh": {
                "sidecar_latency": 2,           # Zusätzliche Latenz durch Sidecar in ms
                "routing_latency": 1,           # Zusätzliche Latenz für Routing in ms
                "auth_latency": 5,              # Zusätzliche Latenz für mTLS in ms
                "enabled": False                # Standardmäßig deaktiviert
            },
            
            # Datenübertragung
            "data_transfer": {
                "intra_region_cost_per_gb": 0.01,  # $ pro GB innerhalb derselben Region
                "inter_region_cost_per_gb": 0.02,  # $ pro GB zwischen Regionen
                "internet_cost_per_gb": 0.09,      # $ pro GB zum Internet
            }
        }
        
        if config:
            self._update_nested_dict(self.config, config)
        
        # Initialize counters for billing
        self.api_requests_count = 0
        self.event_messages_count = {"sns": 0, "sqs": 0, "eventbridge": 0, "kinesis": 0}
        self.data_transferred_gb = {"intra_region": 0, "inter_region": 0, "internet": 0}
    
    def _update_nested_dict(self, original: Dict, updates: Dict):
        """Helper method to update nested dictionary values."""
        for key, value in updates.items():
            if key in original and isinstance(original[key], dict) and isinstance(value, dict):
                self._update_nested_dict(original[key], value)
            else:
                original[key] = value
    
    def calculate_api_gateway_latency(self, 
                                     deployment_type: str = "regional", 
                                     auth_type: str = "none", 
                                     region: str = "us-east-1",
                                     payload_size_kb: float = 1.0,
                                     time_of_day: float = None) -> float:
        """
        Berechnet die Latenz für einen API Gateway-Aufruf.
        
        Args:
            deployment_type: "regional", "edge", oder "private"
            auth_type: Authentifizierungstyp ("none", "api_key", "iam", "cognito", "oauth", "lambda_authorizer")
            region: AWS-Region
            payload_size_kb: Größe der Payload in KB
            time_of_day: Tageszeit als Stunde (0-23), None für aktuelle Zeit
            
        Returns:
            Simulierte Latenz in Millisekunden
        """
        # Basislatenz basierend auf Deployment-Typ
        if deployment_type == "regional":
            base_latency = self.config["api_gateway"]["regional_latency"]
        elif deployment_type == "edge":
            base_latency = self.config["api_gateway"]["edge_latency"]
        elif deployment_type == "private":
            base_latency = self.config["api_gateway"]["private_latency"]
        else:
            base_latency = self.config["api_gateway"]["regional_latency"]
        
        # Authentifizierungs-Overhead hinzufügen
        auth_overhead = self.config["api_gateway"]["authentication_overhead"].get(
            auth_type, self.config["api_gateway"]["authentication_overhead"]["none"]
        )
        
        # Tageszeitabhängiger Lastfaktor (falls definiert)
        load_factor = self._calculate_time_based_load_factor(time_of_day) if time_of_day is not None else 1.0
        
        # Payload-Größeneffekt (größere Payloads brauchen mehr Zeit)
        payload_factor = 1.0 + (payload_size_kb * 0.01)  # 1% zusätzliche Zeit pro KB
        
        # Zufallsvariation für realistischere Simulation
        jitter = random.uniform(-0.1, 0.2) * base_latency  # -10% bis +20% Variation
        
        # Berechne Gesamtlatenz
        total_latency = (base_latency + auth_overhead) * load_factor * payload_factor + jitter
        
        # Aktualisiere den Zähler für die Abrechnung
        self.api_requests_count += 1
        
        return max(1.0, total_latency)  # Mindestens 1ms Latenz
    
    def calculate_api_gateway_cost(self, num_requests: int, data_gb: float) -> float:
        """
        Berechnet die Kosten für API Gateway-Nutzung.
        
        Args:
            num_requests: Anzahl der Anfragen
            data_gb: Übertragene Datenmenge in GB
            
        Returns:
            Kosten in US-Dollar
        """
        request_cost = num_requests * self.config["api_gateway"]["cost_per_request"]
        data_cost = data_gb * self.config["api_gateway"]["cost_per_gb"]
        
        return request_cost + data_cost
    
    def calculate_event_service_latency(self, 
                                       service: str,
                                       operation: str, 
                                       payload_size_kb: float = 1.0,
                                       region: str = "us-east-1",
                                       time_of_day: float = None) -> float:
        """
        Berechnet die Latenz für Event-basierte Services wie SNS, SQS, EventBridge.
        
        Args:
            service: "sns", "sqs", "eventbridge", oder "kinesis"
            operation: Operationstyp ("publish", "send", "receive" etc.)
            payload_size_kb: Größe der Payload in KB
            region: AWS-Region
            time_of_day: Tageszeit als Stunde (0-23)
            
        Returns:
            Simulierte Latenz in Millisekunden
        """
        # Überprüfe, ob der Service unterstützt wird
        if service not in self.config["event_services"]:
            logger.warning(f"Unbekannter Event-Service: {service}, verwende standardmäßig SQS")
            service = "sqs"
        
        # Mapping von Operationen zu Konfigurationsschlüsseln
        operation_mapping = {
            "sns": {"publish": "publish_latency", "deliver": "delivery_latency"},
            "sqs": {"send": "send_latency", "receive": "receive_latency", "dlq": "dlq_latency"},
            "eventbridge": {"publish": "publish_latency", "route": "routing_latency"},
            "kinesis": {"write": "write_latency", "read": "read_latency"}
        }
        
        # Bestimme den Latenzschlüssel
        service_config = self.config["event_services"][service]
        latency_key = operation_mapping.get(service, {}).get(operation)
        
        if not latency_key or latency_key not in service_config:
            logger.warning(f"Unbekannte Operation {operation} für Service {service}, verwende Standardoperation")
            latency_key = list(operation_mapping[service].values())[0]
        
        # Basislatenz aus der Konfiguration
        base_latency = service_config[latency_key]
        
        # Payload-Größeneffekt (größere Nachrichten brauchen mehr Zeit)
        payload_factor = 1.0
        if payload_size_kb > 0:
            # Für kleine Nachrichten ist der Overhead proportional größer
            if payload_size_kb < 10:
                payload_factor = 1.0 + (payload_size_kb * 0.02)  # 2% zusätzlich pro KB für kleine Nachrichten
            else:
                payload_factor = 1.0 + (payload_size_kb * 0.005)  # 0.5% zusätzlich pro KB für größere Nachrichten
                
        # Lastfaktor basierend auf Tageszeit
        load_factor = self._calculate_time_based_load_factor(time_of_day) if time_of_day is not None else 1.0
        
        # Zufallsvariation für realistischere Simulation
        jitter = random.uniform(-0.05, 0.15) * base_latency  # -5% bis +15% Variation
        
        # Berechne Gesamtlatenz
        total_latency = base_latency * payload_factor * load_factor + jitter
        
        # Aktualisiere den Zähler für die Abrechnung
        self.event_messages_count[service] += 1
        
        return max(1.0, total_latency)  # Mindestens 1ms Latenz
    
    def calculate_event_service_cost(self, service: str, num_operations: int) -> float:
        """
        Berechnet die Kosten für Event-Service-Nutzung.
        
        Args:
            service: "sns", "sqs", "eventbridge", oder "kinesis"
            num_operations: Anzahl der Operationen
            
        Returns:
            Kosten in US-Dollar
        """
        if service not in self.config["event_services"]:
            logger.warning(f"Unbekannter Event-Service: {service}, verwende standardmäßig SQS")
            service = "sqs"
            
        # Für Kinesis wird die Berechnung etwas komplexer sein, vereinfacht hier
        if service == "kinesis":
            # Angenommen, wir haben 1 Shard pro 1000 Operationen und 1 Stunde Laufzeit
            shard_hours = max(1, num_operations / 1000)
            shard_cost = shard_hours * self.config["event_services"]["kinesis"]["cost_per_shard_hour"]
            put_cost = num_operations * self.config["event_services"]["kinesis"]["cost_per_million_put"] / 1000000
            return shard_cost + put_cost
        
        # Für andere Services: Kosten pro Million Operationen
        cost_per_million = self.config["event_services"][service]["cost_per_million"]
        return (num_operations / 1000000) * cost_per_million
    
    def calculate_http_latency(self,
                             use_keep_alive: bool = True,
                             payload_size_kb: float = 1.0,
                             serialization_format: str = "json",
                             compression: str = "none",
                             auth_overhead_ms: float = 0,
                             region: str = "us-east-1",
                             time_of_day: float = None) -> float:
        """
        Berechnet die Latenz für direkte HTTP-Kommunikation.
        
        Args:
            use_keep_alive: Ob Keep-Alive verwendet wird
            payload_size_kb: Größe der Payload in KB
            serialization_format: "json", "xml", "protobuf", oder "avro"
            compression: "none", "gzip", oder "brotli"
            auth_overhead_ms: Zusätzlicher Overhead für Authentifizierung in ms
            region: AWS-Region
            time_of_day: Tageszeit als Stunde (0-23)
            
        Returns:
            Simulierte Latenz in Millisekunden
        """
        # Basis-HTTP-Overhead
        http_overhead = self.config["http"]["overhead"]
        
        # Verbindungsaufbau (nicht notwendig bei Keep-Alive)
        connection_overhead = 0 if use_keep_alive else self.config["http"]["connection_setup"]
        
        # Serialisierungskosten
        serialization_cost_per_kb = self.config["http"]["serialization"].get(
            serialization_format, self.config["http"]["serialization"]["json"]
        )
        
        # Kompression
        compression_factor = self.config["http"]["compression"].get(
            compression, self.config["http"]["compression"]["none"]
        )
        
        # Effektive Payload-Größe nach Kompression
        effective_payload_kb = payload_size_kb * compression_factor
        
        # Berechne Serialisierungszeit
        serialization_time = effective_payload_kb * serialization_cost_per_kb
        
        # Lastfaktor basierend auf Tageszeit
        load_factor = self._calculate_time_based_load_factor(time_of_day) if time_of_day is not None else 1.0
        
        # Zufallsvariation
        jitter = random.uniform(-0.05, 0.1) * http_overhead  # -5% bis +10% Variation
        
        # Berechne Gesamtlatenz
        total_latency = (http_overhead + connection_overhead + serialization_time + auth_overhead_ms) * load_factor + jitter
        
        return max(0.5, total_latency)  # Mindestens 0.5ms Latenz
    
    def calculate_service_mesh_overhead(self, 
                                       use_mtls: bool = False, 
                                       tracing_enabled: bool = False,
                                       circuit_breaker_enabled: bool = False) -> float:
        """
        Berechnet den zusätzlichen Overhead durch Service Mesh.
        
        Args:
            use_mtls: Ob mTLS für die Verbindung verwendet wird
            tracing_enabled: Ob verteiltes Tracing aktiviert ist
            circuit_breaker_enabled: Ob Circuit Breaker aktiviert ist
            
        Returns:
            Zusätzlicher Overhead in Millisekunden
        """
        if not self.config["service_mesh"]["enabled"]:
            return 0.0
            
        # Basis-Sidecar-Latenz
        overhead = self.config["service_mesh"]["sidecar_latency"]
        
        # Routing-Overhead
        overhead += self.config["service_mesh"]["routing_latency"]
        
        # Authentifizierungs-Overhead bei mTLS
        if use_mtls:
            overhead += self.config["service_mesh"]["auth_latency"]
            
        # Overhead für Tracing
        if tracing_enabled:
            overhead += 1.0  # Angenommen: 1ms Overhead für Tracing
            
        # Overhead für Circuit Breaker
        if circuit_breaker_enabled:
            overhead += 0.5  # Angenommen: 0.5ms Overhead für Circuit Breaker-Prüfungen
            
        return overhead
    
    def calculate_data_transfer_cost(self, 
                                   gb_transferred: float, 
                                   transfer_type: str = "intra_region") -> float:
        """
        Berechnet die Kosten für Datenübertragung.
        
        Args:
            gb_transferred: Menge der übertragenen Daten in GB
            transfer_type: "intra_region", "inter_region", oder "internet"
            
        Returns:
            Kosten in US-Dollar
        """
        if transfer_type not in self.config["data_transfer"]:
            logger.warning(f"Unbekannter Übertragungstyp: {transfer_type}, verwende intra_region")
            transfer_type = "intra_region"
            
        cost_per_gb = self.config["data_transfer"][f"{transfer_type}_cost_per_gb"]
        
        # Aktualisiere den Zähler für die Abrechnung
        self.data_transferred_gb[transfer_type] = self.data_transferred_gb.get(transfer_type, 0) + gb_transferred
        
        return gb_transferred * cost_per_gb
    
    def simulate_communication(self, 
                             comm_type: str, 
                             params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Simuliert die Kommunikation zwischen Services und berechnet Latenz und Kosten.
        
        Args:
            comm_type: "api_gateway", "event", "http", oder "direct"
            params: Parameter für die Simulation
            
        Returns:
            Dictionary mit simulierten Ergebnissen
        """
        result = {
            "latency_ms": 0,
            "cost": 0,
            "success": True,
            "details": {}
        }
        
        try:
            if comm_type == "api_gateway":
                # API Gateway Kommunikation
                latency = self.calculate_api_gateway_latency(
                    deployment_type=params.get("deployment_type", "regional"),
                    auth_type=params.get("auth_type", "none"),
                    region=params.get("region", "us-east-1"),
                    payload_size_kb=params.get("payload_size_kb", 1.0),
                    time_of_day=params.get("time_of_day")
                )
                
                # Datenübertragungskosten
                data_gb = params.get("payload_size_kb", 1.0) / 1024
                cost = self.calculate_api_gateway_cost(1, data_gb)
                
                result["latency_ms"] = latency
                result["cost"] = cost
                result["details"]["api_gateway"] = {
                    "deployment_type": params.get("deployment_type", "regional"),
                    "auth_type": params.get("auth_type", "none")
                }
                
            elif comm_type == "event":
                # Event-basierte Kommunikation
                service = params.get("service", "sqs")
                operation = params.get("operation", "send" if service == "sqs" else "publish")
                
                latency = self.calculate_event_service_latency(
                    service=service,
                    operation=operation,
                    payload_size_kb=params.get("payload_size_kb", 1.0),
                    region=params.get("region", "us-east-1"),
                    time_of_day=params.get("time_of_day")
                )
                
                cost = self.calculate_event_service_cost(service, 1)
                
                result["latency_ms"] = latency
                result["cost"] = cost
                result["details"]["event_service"] = {
                    "service": service,
                    "operation": operation
                }
                
            elif comm_type == "http":
                # Direkte HTTP-Kommunikation
                latency = self.calculate_http_latency(
                    use_keep_alive=params.get("use_keep_alive", True),
                    payload_size_kb=params.get("payload_size_kb", 1.0),
                    serialization_format=params.get("serialization_format", "json"),
                    compression=params.get("compression", "none"),
                    auth_overhead_ms=params.get("auth_overhead_ms", 0),
                    region=params.get("region", "us-east-1"),
                    time_of_day=params.get("time_of_day")
                )
                
                # Service Mesh Overhead hinzufügen, falls aktiviert
                if self.config["service_mesh"]["enabled"]:
                    mesh_overhead = self.calculate_service_mesh_overhead(
                        use_mtls=params.get("use_mtls", False),
                        tracing_enabled=params.get("tracing_enabled", False),
                        circuit_breaker_enabled=params.get("circuit_breaker_enabled", False)
                    )
                    latency += mesh_overhead
                    result["details"]["service_mesh"] = {
                        "overhead_ms": mesh_overhead,
                        "use_mtls": params.get("use_mtls", False)
                    }
                
                # Datenübertragungskosten
                data_gb = params.get("payload_size_kb", 1.0) / 1024
                transfer_type = params.get("transfer_type", "intra_region")
                cost = self.calculate_data_transfer_cost(data_gb, transfer_type)
                
                result["latency_ms"] = latency
                result["cost"] = cost
                result["details"]["http"] = {
                    "use_keep_alive": params.get("use_keep_alive", True),
                    "serialization": params.get("serialization_format", "json"),
                    "compression": params.get("compression", "none")
                }
                
            elif comm_type == "direct":
                # Direkte Funktionsaufrufe, minimal overhead
                latency = 0.5  # Minimaler Overhead für direkte Aufrufe
                result["latency_ms"] = latency
                result["cost"] = 0  # Direkte Aufrufe verursachen keine zusätzlichen Kosten
                result["details"]["direct"] = {"type": "direct_function_call"}
                
            else:
                logger.warning(f"Unbekannter Kommunikationstyp: {comm_type}")
                result["success"] = False
                result["error"] = f"Unbekannter Kommunikationstyp: {comm_type}"
                
        except Exception as e:
            logger.error(f"Fehler bei der Simulation von {comm_type}: {str(e)}")
            result["success"] = False
            result["error"] = str(e)
            
        return result
    
    def _calculate_time_based_load_factor(self, time_of_day: float) -> float:
        """
        Berechnet den Lastfaktor basierend auf der Tageszeit.
        
        Args:
            time_of_day: Tageszeit als Stunde (0-23), None für aktuelle Zeit
            
        Returns:
            Lastfaktor (1.0 = durchschnittliche Last)
        """
        if time_of_day is None:
            # Aktuelle Stunde verwenden
            time_of_day = float(time.localtime().tm_hour)
            
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
            
    def get_billing_summary(self) -> Dict[str, Any]:
        """
        Gibt eine Zusammenfassung der Abrechnungsinformationen zurück.
        
        Returns:
            Dictionary mit Abrechnungsinformationen
        """
        api_cost = self.api_requests_count * self.config["api_gateway"]["cost_per_request"]
        
        event_costs = {}
        total_event_cost = 0
        for service, count in self.event_messages_count.items():
            service_cost = self.calculate_event_service_cost(service, count)
            event_costs[service] = {
                "count": count,
                "cost": service_cost
            }
            total_event_cost += service_cost
            
        data_costs = {}
        total_data_cost = 0
        for transfer_type, gb in self.data_transferred_gb.items():
            cost_per_gb = self.config["data_transfer"].get(f"{transfer_type}_cost_per_gb", 0)
            cost = gb * cost_per_gb
            data_costs[transfer_type] = {
                "gb": gb,
                "cost": cost
            }
            total_data_cost += cost
            
        return {
            "api_gateway": {
                "requests": self.api_requests_count,
                "cost": api_cost
            },
            "event_services": event_costs,
            "data_transfer": data_costs,
            "total_cost": api_cost + total_event_cost + total_data_cost
        }