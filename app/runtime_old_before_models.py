# runtime.py erweitert

import inspect
import uuid
import time
import json
import asyncio
import logging
from typing import Dict, List, Any, Callable, Optional

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

class LambdaContext:
    """AWS Lambda Context-Simulation"""
    
    def __init__(self, function_name: str, memory_limit: int = 128, timeout: int = 3):
        self.function_name = function_name
        self.function_version = "$LATEST"
        self.memory_limit_in_mb = memory_limit
        self.aws_request_id = str(uuid.uuid4())
        self.log_group_name = f"/aws/lambda/{function_name}"
        self.log_stream_name = f"{time.strftime('%Y/%m/%d')}/[$LATEST]{uuid.uuid4().hex}"
        self._timeout = timeout * 1000  # in Millisekunden
        self._start_time = time.time()
        self.logs = []  # Log-Sammlung
        
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
        self.execution_logs = {}  # request_id -> logs
        self.config = {
            "default_timeout": 3,  # Sekunden
            "default_memory": 128,  # MB
            "remote_call_overhead": 0.05,  # Sekunden
            "memory_performance_factor": 0.8  # Faktor für Memory-Performance Simulation
        }
        
        # Logger für die Runtime
        self.logger = logging.getLogger("lambda-runtime")
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)
    
    def register(self, name: str, func: Callable, memory: int = 128, timeout: int = 3):
        """Registriert eine neue Lambda-Funktion"""
        self.functions[name] = {
            "handler": func,
            "memory": memory,
            "timeout": timeout
        }
        self.logger.info(f"Funktion registriert: {name}, Memory: {memory}MB, Timeout: {timeout}s")

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
        
        # Remote-Aufruf-Overhead simulieren
        if execution_mode == "remote" and hasattr(self, "performance_model"):
            # Wenn ein Performance-Modell verfügbar ist, verwende dieses für realistischere Simulationen
            payload_size = len(json.dumps(event)) / 1024  # Ungefähre Payload-Größe in KB
            overhead = self.performance_model.calculate_remote_overhead(
                payload_size, source_region, target_region
            )
            await asyncio.sleep(overhead)
        elif execution_mode == "remote":
            # Fallback auf einfaches Modell
            await asyncio.sleep(self.config["remote_call_overhead"])
        
        # Lambda-Kontext erstellen
        context = LambdaContext(
            function_name=name,
            memory_limit=memory,
            timeout=timeout
        )
        
        # Memory-Performance-Simulation - erweitert
        if hasattr(self, "performance_model"):
            # Erweiterte Simulation mit Performance-Modell
            time_of_day = None  # Verwende aktuelle Zeit
            is_cold_start = func_config.get("last_invoked", 0) < (time.time() - 300)  # > 5 Min = Cold Start
            workload_intensity = 1.0  # Standard-Intensität
            
            # I/O-Eigenschaften der Funktion (falls definiert)
            io_operations = func_config.get("io_operations", None)
            
            # Simulierte Verzögerung anwenden
            if memory < 256:
                await self.performance_model.apply_execution_delay(
                    base_execution_time=0.01,  # Kleine Basis-Verzögerung
                    memory_mb=memory,
                    is_remote=False,  # Interner Memory-Effekt, kein Remote-Call
                    is_cold_start=False,  # Cold Start wird separat behandelt
                    function_type=function_type,
                    workload_intensity=workload_intensity
                )
        elif memory < 256:
            # Einfache Simulation ohne Performance-Modell
            memory_slowdown = (256 - memory) / 256 * self.config["memory_performance_factor"]
            self.logger.debug(f"Memory-Slowdown für {name}: {memory_slowdown}s")
            await asyncio.sleep(memory_slowdown)
        
        # Funktion mit Timeout ausführen
        try:
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
            context.log(f"Event: {json.dumps(event)}")
            
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