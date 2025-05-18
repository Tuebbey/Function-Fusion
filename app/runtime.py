import inspect
import uuid
import time
import json
import asyncio
import logging
import random
import math
from typing import Dict, List, Any, Callable, Optional

# Klassen für Performance- und Netzwerkmodellierung
class PerformanceModel:
    """Modelliert das Performance-Verhalten von FaaS-Funktionen unter verschiedenen Bedingungen."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        # Standard-Konfiguration
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
            
            # Payload-Größeneffekte
            "payload_size_factor": 0.0001,  # Einfluss der Payload-Größe auf Latenz
            
            # Funktionstyp-spezifische Faktoren
            "function_type_factors": {
                "cpu_intensive": 1.0,  # Basiswert für CPU-intensive Funktionen
                "memory_intensive": 0.7,  # Memory-intensive Funktionen profitieren mehr von höherem Memory
                "io_intensive": 0.3  # I/O-intensive Funktionen profitieren weniger von höherem Memory
            }
        }
        
        # Konfiguration überschreiben, wenn angegeben
        if config:
            self.config.update(config)
    
    def calculate_remote_overhead(self, payload_size_kb: float = 0) -> float:
        """
        Berechnet den Overhead für einen Remote-Funktionsaufruf.
        Args:
            payload_size_kb: Größe der Payload in KB
        Returns:
            Simulierte Verzögerung in Sekunden
        """
        base = 0.05  # 50ms Basis-Overhead
        jitter = random.uniform(-0.01, 0.01)  # ±10ms Jitter
        
        # Zusätzliche Verzögerung basierend auf Payload-Größe
        payload_delay = payload_size_kb * self.config["payload_size_factor"]
        
        return max(0, base + jitter + payload_delay)
    
    def calculate_memory_performance_effect(self, 
                                           memory_mb: int,
                                           function_type: str = "cpu_intensive") -> float:
        """
        Berechnet den Performance-Effekt basierend auf zugewiesenem Speicher.
        Args:
            memory_mb: Zugewiesener Speicher in MB
            function_type: Art der Funktion (cpu_intensive, memory_intensive, io_intensive)
        Returns:
            Multiplikator für die Ausführungszeit (niedriger = schneller)
        """
        # Standardwert, wenn function_type nicht bekannt
        type_factor = self.config["function_type_factors"].get(
            function_type, 
            self.config["function_type_factors"]["cpu_intensive"]
        )
        
        # CPU-Skalierung basierend auf Memory
        vcpu_equivalent = memory_mb / self.config["memory_cpu_ratio"]
        
        # Nicht-lineare Skalierung
        if memory_mb < 512:
            scaling_factor = 1.0 / (self.config["base_cpu_factor"] + 
                                  (1 - self.config["base_cpu_factor"]) * (memory_mb / 512))
        else:
            scaling_factor = 1.0 / (self.config["base_cpu_factor"] + 
                                  (1 - self.config["base_cpu_factor"]) * vcpu_equivalent)
        
        # Anpassen basierend auf Funktionstyp
        adjusted_factor = scaling_factor * type_factor
        
        return adjusted_factor
    
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
    
    def simulate_execution_time(self,
                               base_execution_time: float,
                               memory_mb: int,
                               is_remote: bool,
                               is_cold_start: bool = False,
                               payload_size_kb: float = 0,
                               function_type: str = "cpu_intensive") -> float:
        """
        Simuliert die Ausführungszeit einer Funktion unter Berücksichtigung aller Faktoren.
        
        Args:
            base_execution_time: Basis-Ausführungszeit ohne Berücksichtigung von Faktoren
            memory_mb: Zugewiesener Speicher in MB
            is_remote: Ob die Funktion remote aufgerufen wird
            is_cold_start: Ob es sich um einen Cold-Start handelt
            payload_size_kb: Größe der Payload in KB
            function_type: Art der Funktion
        Returns:
            Simulierte Ausführungszeit in Sekunden
        """
        # Basis-Faktoren
        time_multiplier = self.calculate_memory_performance_effect(memory_mb, function_type)
        execution_time = base_execution_time * time_multiplier
        
        # Remote-Overhead, falls anwendbar
        if is_remote:
            execution_time += self.calculate_remote_overhead(payload_size_kb)
        
        # Cold-Start-Verzögerung, falls anwendbar
        if is_cold_start:
            execution_time += self.calculate_cold_start_delay(memory_mb)
        
        return execution_time
    
    async def apply_execution_delay(self,
                                  base_execution_time: float,
                                  memory_mb: int,
                                  is_remote: bool,
                                  is_cold_start: bool = False,
                                  payload_size_kb: float = 0,
                                  function_type: str = "cpu_intensive"):
        """
        Wendet die simulierte Ausführungsverzögerung an.
        Args:
            Gleiche Parameter wie simulate_execution_time
        """
        delay = self.simulate_execution_time(
            base_execution_time, memory_mb, is_remote,
            is_cold_start, payload_size_kb, function_type
        )
        
        # Simulierte Verzögerung anwenden
        await asyncio.sleep(delay)
        return delay


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


# Spezifische Exception-Klassen
class LambdaFunctionNotFound(Exception):
    """Ausnahme für nicht gefundene Lambda-Funktionen"""
    pass

class LambdaTimeoutError(Exception):
    """Ausnahme für Timeouts in Lambda-Funktionen"""
    pass

class LambdaExecutionError(Exception):
    """Ausnahme für allgemeine Fehler bei der Ausführung von Lambda-Funktionen"""
    pass

class NetworkError(Exception):
    """Ausnahme für Netzwerkfehler bei Function-Calls"""
    pass

class LambdaContext:
    """AWS Lambda Context-Simulation"""
    def __init__(self, function_name: str, memory_limit: int = 128, timeout: int = 3):
        self.function_name = function_name
        self.function_version = "$LATEST"
        self.memory_limit_in_mb = memory_limit
        self.aws_request_id = str(uuid.uuid4())
        self.log_group_name = f"/aws/lambda/{function_name}"
        self.log_stream_name = f"{time.strftime('%Y/%m/%d')}/[$LATEST]{uuid.uuid4().hex}"
        self._timeout = timeout * 1000 # in Millisekunden
        self._start_time = time.time()
        self.logs = [] # Log-Sammlung

    def get_remaining_time_in_millis(self) -> int:
        """Gibt die verbleibende Ausführungszeit in Millisekunden zurück"""
        elapsed = int((time.time() - self._start_time) * 1000)
        remaining = self._timeout - elapsed
        return max(0, remaining)

    def log(self, message: str, level: str = "INFO"):
        """Fügt einen Log-Eintrag hinzu"""
        timestamp = time.time()
        log_entry = {
            "timestamp": timestamp,
            "time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(timestamp)),
            "level": level,
            "message": message,
            "request_id": self.aws_request_id
        }
        self.logs.append(log_entry)
        # Auch in die Konsole ausgeben
        print(f"[{log_entry['time']}] [{level}] [{self.function_name}] {message}")

    def to_dict(self) -> Dict[str, Any]:
        """Konvertiert den Kontext in ein Dictionary"""
        return {
            "function_name": self.function_name,
            "function_version": self.function_version,
            "memory_limit_in_mb": self.memory_limit_in_mb,
            "aws_request_id": self.aws_request_id,
            "log_group_name": self.log_group_name,
            "log_stream_name": self.log_stream_name,
            "remaining_time_in_millis": self.get_remaining_time_in_millis(),
            "logs": self.logs
        }

class LambdaRuntime:
    def __init__(self):
        self.functions = {}
        self.execution_logs = {} # request_id -> logs
        self.config = {
            "default_timeout": 3, # Sekunden
            "default_memory": 128, # MB
            "remote_call_overhead": 0.05, # Sekunden
            "memory_performance_factor": 0.8 # Faktor für Memory-Performance Simulation
        }
        
        # Performance- und Netzwerkmodelle initialisieren
        self.performance_model = PerformanceModel()
        self.network_model = NetworkModel()
        
        # Logger für die Runtime
        self.logger = logging.getLogger("lambda-runtime")
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)

    def register(self, name: str, func: Callable, memory: int = 128, timeout: int = 3, 
                region: str = "us-east-1", function_type: str = "cpu_intensive"):
        """Registriert eine neue Lambda-Funktion"""
        self.functions[name] = {
            "handler": func,
            "memory": memory,
            "timeout": timeout,
            "region": region,
            "function_type": function_type,
            "last_invoked": 0  # Zeitstempel der letzten Ausführung (für Cold-Start-Simulation)
        }
        self.logger.info(f"Funktion registriert: {name}, Memory: {memory}MB, Timeout: {timeout}s, Region: {region}, Typ: {function_type}")

    async def invoke(self, name: str, event: Dict[str, Any],
                   execution_mode: str = "local",
                   source_region: str = "us-east-1",
                   function_type: str = "cpu_intensive") -> Dict[str, Any]:
        """
        Führt eine Lambda-Funktion aus.

        Args:
            name: Name der aufzurufenden Funktion
            event: Event-Daten für die Funktion
            execution_mode: 'local' oder 'remote'
            source_region: Quellregion der aufrufenden Funktion
            function_type: Art der Funktion (cpu_intensive, memory_intensive, io_intensive)
            
        Returns:
            Ergebnis der Funktionsausführung
            
        Raises:
            LambdaFunctionNotFound: Wenn die Funktion nicht gefunden wurde
            LambdaTimeoutError: Wenn die Funktion das Timeout überschreitet
            LambdaExecutionError: Bei anderen Ausführungsfehlern
        """
        self.logger.info(f"Führe '{name}' im {execution_mode}-Modus aus mit Event: {event}")
        
        if name not in self.functions:
            error_msg = f"Funktion '{name}' nicht registriert."
            self.logger.error(error_msg)
            raise LambdaFunctionNotFound(error_msg)
        
        func_config = self.functions[name]
        func = func_config["handler"]
        timeout = func_config["timeout"]
        memory = func_config["memory"]
        target_region = func_config.get("region", "us-east-1")
        function_type = func_config.get("function_type", function_type)
        
        # Cold-Start prüfen (> 5 Minuten seit letzter Ausführung)
        is_cold_start = func_config.get("last_invoked", 0) < (time.time() - 300)
        
        # Payload-Größe berechnen (für Netzwerk-Overhead)
        try:
            payload_size_kb = len(json.dumps(event, default=str)) / 1024
        except:
            payload_size_kb = 1  # Fallback, falls Serialisierung fehlschlägt
            
        # Remote-Aufruf-Overhead simulieren
        if execution_mode == "remote":
            # Netzwerkfehler simulieren?
            if self.network_model and self.network_model.should_simulate_failure(source_region, target_region):
                error_msg = f"Simulierter Netzwerkfehler beim Aufruf von '{name}'"
                self.logger.error(error_msg)
                raise NetworkError(error_msg)
            
            # Netzwerkverzögerung simulieren
            if self.network_model:
                await self.network_model.simulate_function_invocation(
                    source_region, target_region, payload_size_kb
                )
            else:
                # Einfache Verzögerung, wenn kein Netzwerkmodell vorhanden
                await asyncio.sleep(self.config["remote_call_overhead"])
        
        # Lambda-Kontext erstellen
        context = LambdaContext(
            function_name=name,
            memory_limit=memory,
            timeout=timeout
        )
        
        # Memory-Performance-Simulation
        if self.performance_model:
            # Verzögerung basierend auf der Performance-Modellierung
            await self.performance_model.apply_execution_delay(
                0.01,  # Basis-Ausführungszeit in Sekunden
                memory,
                is_remote=(execution_mode == "remote"),
                is_cold_start=is_cold_start,
                payload_size_kb=payload_size_kb,
                function_type=function_type
            )
        elif memory < 256:
            # Einfache Verzögerung, wenn kein Performance-Modell vorhanden
            memory_slowdown = (256 - memory) / 256 * self.config["memory_performance_factor"]
            self.logger.debug(f"Memory-Slowdown für {name}: {memory_slowdown}s")
            await asyncio.sleep(memory_slowdown)
        
        # Funktion mit Timeout ausführen
        try:
            # Cold-Start-Verzögerung simulieren
            if is_cold_start and self.performance_model:
                cold_start_delay = self.performance_model.calculate_cold_start_delay(memory)
                if cold_start_delay > 0:
                    self.logger.info(f"Simuliere Cold-Start für '{name}': {cold_start_delay:.2f}s")
                    await asyncio.sleep(cold_start_delay)
            
            # Funktion ausführen
            task = self._execute_function(func, event, context)
            result = await asyncio.wait_for(task, timeout=timeout)
            
            # Aktualisiere den Zeitpunkt der letzten Ausführung
            func_config["last_invoked"] = time.time()
            
            # Logs speichern
            self.execution_logs[context.aws_request_id] = context.logs
            return result
            
        except asyncio.TimeoutError:
            error_msg = f"Funktion '{name}' hat das Timeout von {timeout}s überschritten"
            context.log(error_msg, "ERROR")
            self.logger.error(error_msg)
            
            # Logs speichern
            self.execution_logs[context.aws_request_id] = context.logs
            raise LambdaTimeoutError(error_msg)
            
        except Exception as e:
            error_msg = f"Fehler bei Aufruf von '{name}': {e}"
            context.log(error_msg, "ERROR")
            self.logger.error(error_msg)
            
            # Logs speichern
            self.execution_logs[context.aws_request_id] = context.logs
            
            # Spezifische Lambda-Exception wrappen
            raise LambdaExecutionError(error_msg) from e

    async def _execute_function(self, func, event, context):
        """Führt die eigentliche Funktion mit dem richtigen Kontext aus"""
        sig = inspect.signature(func)
        params = sig.parameters
        
        # Log-Methode für die Funktion
        def log_callback(message, level="INFO"):
            context.log(message, level)
        
        # Callback für Nested-Invoke
        async def call_function(inner_name, inner_event, mode="local"):
            return await self.invoke(inner_name, inner_event, execution_mode=mode)
        
        # Funktion ausführen mit der richtigen Anzahl von Parametern
        try:
            # Start-Log
            context.log(f"START RequestId: {context.aws_request_id} Version: {context.function_version}")
            context.log(f"Event: {json.dumps(event, default=str)}")
            
            # Eigentliche Ausführung
            result = None
            start_time = time.time()
            
            if inspect.iscoroutinefunction(func):
                if len(params) == 3:
                    result = await func(event, context.to_dict(), call_function)
                elif len(params) == 2:
                    param_names = list(params)
                    if param_names[1] in ["context", "ctx"]:
                        result = await func(event, context.to_dict())
                    else:
                        result = await func(event, call_function)
                elif len(params) == 1:
                    result = await func(event)
                else:
                    raise ValueError(f"Unsupported number of parameters in async function: {len(params)}")
            else:
                if len(params) == 3:
                    result = func(event, context.to_dict(), call_function)
                elif len(params) == 2:
                    param_names = list(params)
                    if param_names[1] in ["context", "ctx"]:
                        result = func(event, context.to_dict())
                    else:
                        result = func(event, call_function)
                elif len(params) == 1:
                    result = func(event)
                else:
                    raise ValueError(f"Unsupported number of parameters in sync function: {len(params)}")
            
            duration = time.time() - start_time
            
            # End-Log
            context.log(f"END RequestId: {context.aws_request_id}")
            context.log(f"REPORT RequestId: {context.aws_request_id} Duration: {duration * 1000:.2f} ms " +
                       f"Memory Size: {context.memory_limit_in_mb} MB")
            
            return result
            
        except Exception as e:
            # Log des Fehlers
            context.log(f"ERROR: {str(e)}", "ERROR")
            context.log(f"END RequestId: {context.aws_request_id}")
            
            # Fehler weiterleiten
            raise

    def get_logs(self, request_id: str) -> List[Dict[str, Any]]:
        """Gibt die Logs für eine bestimmte Request-ID zurück"""
        return self.execution_logs.get(request_id, [])

    def clear_logs(self):
        """Löscht alle gespeicherten Logs"""
        self.execution_logs.clear()

# Globale Instanz
runtime = LambdaRuntime()