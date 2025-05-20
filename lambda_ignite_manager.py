# lambda_ignite_manager.py
import threading
import math
import time
import random
import os
import logging
from ignite_manager import IgniteManager

logger = logging.getLogger("lambda-ignite-manager")

class LambdaInstancePool:
    def __init__(self, ttl_seconds=600):  # AWS hält Instanzen ~10 Minuten warm
        self.instances = {}  # function_name -> Liste von VM-Instanzen
        self.last_used = {}  # instance_id -> Zeitstempel der letzten Nutzung
        self.ttl_seconds = ttl_seconds
        self.invocation_count = {}  # Zählt Aufrufe pro Funktion für Metriken
        self.lock = threading.Lock()
        
    def get_instance(self, function_name, memory_mb=128, network_config=None):
        """Gibt eine warme Instanz zurück oder erstellt eine neue (Cold Start)"""
        with self.lock:
            current_time = time.time()
            
            # Prüfen, ob warme Instanzen verfügbar sind
            if function_name in self.instances:
                warm_instances = []
                for instance_id in self.instances[function_name]:
                    last_used = self.last_used.get(instance_id, 0)
                    # Prüfen, ob die Instanz noch warm ist
                    if current_time - last_used < self.ttl_seconds:
                        warm_instances.append(instance_id)
                
                # Wenn warme Instanzen vorhanden sind, wähle eine aus
                if warm_instances:
                    # Wähle die zuletzt genutzte Instanz (AWS-Verhalten)
                    instance_id = max(warm_instances, key=lambda i: self.last_used.get(i, 0))
                    
                    # Aktualisiere Zeitstempel
                    self.last_used[instance_id] = current_time
                    
                    logger.info(f"CACHE HIT: Warme Instanz {instance_id} für {function_name} wiederverwendet")
                    
                    # Erfasse Metriken
                    self.invocation_count[function_name] = self.invocation_count.get(function_name, 0) + 1
                    return {"instance_id": instance_id, "is_cold_start": False}
            
            # Keine warme Instanz verfügbar, erstelle eine neue (Cold Start)
            instance_id = f"{function_name}_{int(time.time())}_{random.randint(1000, 9999)}"
            
            if function_name not in self.instances:
                self.instances[function_name] = []
                
            self.instances[function_name].append(instance_id)
            self.last_used[instance_id] = current_time
            
            logger.info(f"COLD START: Neue Instanz {instance_id} für {function_name} erstellt")
            
            # Erfasse Metriken
            self.invocation_count[function_name] = self.invocation_count.get(function_name, 0) + 1
            
            return {"instance_id": instance_id, "is_cold_start": True}
    
    def run_cleanup(self):
        """Entfernt abgelaufene Instanzen (wird periodisch ausgeführt)"""
        with self.lock:
            current_time = time.time()
            expired_instances = []
            
            for instance_id, last_used in self.last_used.items():
                if current_time - last_used > self.ttl_seconds:
                    expired_instances.append(instance_id)
            
            for instance_id in expired_instances:
                # Entferne aus allen Datenstrukturen
                for function_name, instances in self.instances.items():
                    if instance_id in instances:
                        instances.remove(instance_id)
                
                if instance_id in self.last_used:
                    del self.last_used[instance_id]
                
                logger.info(f"Instanz {instance_id} abgelaufen und entfernt")

class LambdaIOEmulator:
    def __init__(self):
        self.file_cache = {}  # Pfad -> {"last_accessed": Zeitstempel, "cached": Boolean}
        self.layer_files = set()  # Dateien in Lambda Layers (unterschiedliches Caching)
        self.lock = threading.Lock()
        
    def simulate_file_read(self, file_path, is_cold_start=False, is_layer_file=False):
        """Simuliert das Lesen einer Datei mit AWS Lambda-ähnlichem Verhalten"""
        with self.lock:
            current_time = time.time()
            read_count = 1  # Standardmäßig einmal lesen
            
            # Bei Cold Start oder nicht-gecachten Dateien zweimal lesen
            if is_cold_start or file_path not in self.file_cache:
                read_count = 2  # Zweimal von Disk lesen
                
                # Datei im Cache speichern
                self.file_cache[file_path] = {
                    "last_accessed": current_time,
                    "cached": True
                }
                
                if is_layer_file:
                    self.layer_files.add(file_path)
                    
                logger.debug(f"DISK READ x2: {file_path} (Cold: {is_cold_start})")
            else:
                # Datei ist im Cache, aktualisiere Zeitstempel
                self.file_cache[file_path]["last_accessed"] = current_time
                logger.debug(f"DISK READ x1: {file_path} (Cached)")
            
            # Simuliere tatsächliches Lesen
            file_size = 0
            if os.path.exists(file_path):
                file_size = os.path.getsize(file_path)
                
            # Berechne Lese-Latenz basierend auf Dateigröße
            # (AWS Lambda hat ~ 40-100 MB/s Lesegeschwindigkeit)
            latency_per_read_ms = file_size / (50 * 1024 * 1024) * 1000  # ~50 MB/s
            total_latency_ms = latency_per_read_ms * read_count
            
            return {
                "reads": read_count,
                "latency_ms": total_latency_ms,
                "file_size_bytes": file_size
            }
    
    def cleanup_cache(self, max_age_seconds=300):
        """Bereinigt den Dateicache (Layer-Dateien bleiben länger im Cache)"""
        with self.lock:
            current_time = time.time()
            paths_to_remove = []
            
            for path, info in self.file_cache.items():
                # Layer-Dateien bleiben länger im Cache
                max_age = max_age_seconds * 10 if path in self.layer_files else max_age_seconds
                
                if current_time - info["last_accessed"] > max_age:
                    paths_to_remove.append(path)
                    
            for path in paths_to_remove:
                del self.file_cache[path]
                if path in self.layer_files:
                    self.layer_files.remove(path)
                    
            logger.debug(f"Cache-Bereinigung abgeschlossen: {len(paths_to_remove)} Einträge entfernt")

class AWSLambdaIgniteManager(IgniteManager):
    def __init__(self):
        super().__init__()
        self.instance_pool = LambdaInstancePool(ttl_seconds=600)
        self.io_emulator = LambdaIOEmulator()
        
        # Starte den Cleanup-Thread
        self._start_cleanup_thread()
        
    def _start_cleanup_thread(self):
        """Startet einen Thread, der abgelaufene Instanzen und Cache-Einträge bereinigt"""
        def cleanup_worker():
            while True:
                try:
                    # Instanzen bereinigen
                    self.instance_pool.run_cleanup()
                    # Dateicache bereinigen
                    self.io_emulator.cleanup_cache()
                except Exception as e:
                    logger.error(f"Fehler im Cleanup-Thread: {e}")
                
                # Alle 60 Sekunden ausführen
                time.sleep(60)
        
        cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True)
        cleanup_thread.start()
        logger.info("Cleanup-Thread gestartet")
        
    def invoke_function(self, function_name, event_data, memory_mb=128, network_config=None):
        """Ruft eine Funktion mit realistischem AWS Lambda-Verhalten auf"""
        start_time = time.time()
        
        # Instanz aus Pool abrufen oder neue erstellen
        instance_info = self.instance_pool.get_instance(
            function_name, 
            memory_mb, 
            network_config
        )
        
        is_cold_start = instance_info["is_cold_start"]
        instance_id = instance_info["instance_id"]
        
        # VM erstellen oder abrufen
        if is_cold_start:
            # Tatsächlich neue VM erstellen oder vorhandene VM aktualisieren
            vm_name = self.create_vm(function_name, memory_mb, 1, network_config)
            
            # Cold-Start-Verzögerung simulieren
            cold_start_delay_ms = self._simulate_cold_start(function_name, memory_mb)
            
            # Dateisystem-Initialisierung simulieren
            filesystem_init_time_ms = self._simulate_filesystem_init(function_name, is_cold_start)
            
            logger.info(f"Cold Start für {function_name}: {cold_start_delay_ms + filesystem_init_time_ms:.2f}ms")
            
            # Warte entsprechend der simulierten Verzögerung
            time.sleep((cold_start_delay_ms + filesystem_init_time_ms) / 1000)
        else:
            # Prüfen, ob die VM bereits existiert
            if function_name not in self.vms:
                logger.warning(f"Warme Instanz {instance_id} gefunden, aber VM existiert nicht. Erstelle neu.")
                vm_name = self.create_vm(function_name, memory_mb, 1, network_config)
            else:
                # VM existiert bereits, möglicherweise Netzwerkkonfiguration aktualisieren
                vm_name = self.vms[function_name]
                if network_config:
                    self.update_vm_network(function_name, network_config)
        
        # Jetzt tatsächlich die Funktion aufrufen
        event_data["_aws_lambda_context"] = {
            "instance_id": instance_id,
            "is_cold_start": is_cold_start,
            "memory_mb": memory_mb,
            "start_time": start_time
        }
        
        # Simuliere zusätzlich das Lambda-Abrechnungsverhalten
        execution_start_time = time.time()
        
        # Funktion aufrufen (verwende die Basisimplementierung)
        response = super().invoke_function(function_name, event_data)
        
        # Ausführungszeit berechnen (in ms)
        execution_time_ms = (time.time() - execution_start_time) * 1000
        
        # Billingdauer berechnen (aufgerundet auf die nächste ms)
        billed_duration_ms = math.ceil(execution_time_ms)
        
        # AWS Lambda-spezifische Metriken hinzufügen
        if isinstance(response, dict) and "body" in response:
            response["aws_lambda_metrics"] = {
                "instance_id": instance_id,
                "is_cold_start": is_cold_start,
                "execution_time_ms": execution_time_ms,
                "billed_duration_ms": billed_duration_ms,
                "memory_mb": memory_mb,
                "max_memory_used_mb": self._estimate_memory_usage(memory_mb, function_name)
            }
        
        return response
    
    def _simulate_cold_start(self, function_name, memory_mb):
        """Simuliert die Cold-Start-Verzögerung basierend auf AWS Lambda-Verhalten"""
        # AWS Lambda Cold-Start-Zeit hängt von verschiedenen Faktoren ab:
        # 1. Code-Größe
        # 2. Runtime (Python ist schneller als z.B. Java)
        # 3. Speichergröße (mehr Speicher = mehr CPU = schnellerer Cold Start)
        
        # Basis-Cold-Start-Zeit (100-400ms für Python)
        base_cold_start_ms = random.uniform(100, 400)
        
        # Speichereffekt: mehr Speicher = schnellerer Cold Start
        # (normalisiert von 128MB bis 10GB)
        memory_factor = 1.0 - (memory_mb - 128) / (10240 - 128) * 0.5  # 50% Verbesserung bei max Speicher
        memory_factor = max(0.5, memory_factor)  # Maximal 50% Verbesserung
        
        # Funktion hat vermutlich unterschiedliche Code-Größen
        # (vereinfachte Annahme basierend auf Funktionsnamen)
        code_size_factor = 1.0
        if "cart" in function_name or "checkout" in function_name:
            code_size_factor = 1.2  # 20% langsamer für komplexere Funktionen
        elif "payment" in function_name:
            code_size_factor = 1.3  # 30% langsamer
            
        # VPC-Funktionen sind langsamer beim Cold Start
        # (vereinfachte Annahme: nur payment-Funktionen in VPC)
        vpc_factor = 1.5 if "payment" in function_name else 1.0
        
        # Gesamtverzögerung berechnen
        cold_start_ms = base_cold_start_ms * memory_factor * code_size_factor * vpc_factor
        
        logger.debug(f"Cold-Start-Verzögerung für {function_name}: {cold_start_ms:.2f}ms (Basis: {base_cold_start_ms:.2f}ms, Memory: {memory_factor:.2f}, Code: {code_size_factor:.2f}, VPC: {vpc_factor:.2f})")
        
        return cold_start_ms
    
    def _simulate_filesystem_init(self, function_name, is_cold_start):
        """Simuliert die Initialisierung des Dateisystems (inkl. zweimaliges Lesen)"""
        if not is_cold_start:
            return 0  # Keine Initialisierung bei warmen Starts
            
        # Simuliere das Lesen verschiedener Dateien
        total_io_time_ms = 0
        
        # Konfigurationsdateien
        config_file = f"functions/webshop/{function_name}/Dockerfile"
        io_result = self.io_emulator.simulate_file_read(config_file, is_cold_start=True)
        total_io_time_ms += io_result["latency_ms"]
        
        # Handler-Datei
        handler_file = f"functions/webshop/{function_name}/handler.py" 
        io_result = self.io_emulator.simulate_file_read(handler_file, is_cold_start=True)
        total_io_time_ms += io_result["latency_ms"]
        
        # Server-Datei
        server_file = f"functions/webshop/{function_name}/server.py"
        io_result = self.io_emulator.simulate_file_read(server_file, is_cold_start=True)
        total_io_time_ms += io_result["latency_ms"]
        
        # Gemeinsame Bibliotheken (Layer-ähnlich)
        common_libs = ["docker/server_template.py", "docker/entrypoint.sh"]
        for lib in common_libs:
            io_result = self.io_emulator.simulate_file_read(lib, is_cold_start=True, is_layer_file=True)
            total_io_time_ms += io_result["latency_ms"]
        
        logger.debug(f"Dateisystem-Initialisierung für {function_name}: {total_io_time_ms:.2f}ms")
        
        return total_io_time_ms
    
    def _estimate_memory_usage(self, allocated_memory_mb, function_name):
        """Schätzt die maximale Speichernutzung basierend auf zugewiesenem Speicher"""
        # Typischerweise nutzen Funktionen 30-60% des zugewiesenen Speichers
        base_usage_percent = random.uniform(30, 60)
        
        # Funktionsabhängige Anpassungen
        if "cartkvstorage" in function_name or "checkout" in function_name:
            # Diese Funktionen nutzen vermutlich mehr Speicher
            base_usage_percent += 10
        
        # Berechne tatsächliche Nutzung
        max_memory_used = allocated_memory_mb * (base_usage_percent / 100)
        
        return max_memory_used