# ignite_manager.py
import subprocess
import json
import time
import os
import logging
import uuid
import threading
import math
import random

logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("ignite-manager")

class IgniteManager:
    def __init__(self):
        self.vms = {}  # function_name -> vm_name
        self.port_mapping = self._load_port_mapping()
        
    def _load_port_mapping(self):
        """Lädt die Port-Mappings aus der docker-compose.yml"""
        # Dies ist eine vereinfachte Version deiner docker-compose.yml
        return {
            "frontend": "8001:8000",
            "addcartitem": "8002:8000",
            "cartkvstorage": "8003:8000",
            "getcart": "8004:8000",
            "emptycart": "8005:8000",
            "listproducts": "8006:8000",
            "getproduct": "8007:8000",
            "searchproducts": "8008:8000",
            "listrecommendations": "8009:8000",
            "shipmentquote": "8010:8000",
            "shiporder": "8011:8000",
            "checkout": "8012:8000",
            "payment": "8013:8000",
            "currency": "8014:8000",
            "supportedcurrencies": "8015:8000",
            "getads": "8016:8000",
            "email": "8017:8000"
        }
    
    def create_vm(self, function_name, memory_mb=128, cpu_count=1, network_config=None):
        """Erstellt eine neue VM für die gegebene Funktion"""
        logger.info(f"Erstelle VM für Funktion {function_name}")
        
        # Überprüfe, ob die Funktion bereits eine VM hat
        if function_name in self.vms:
            vm_name = self.vms[function_name]
            logger.info(f"VM {vm_name} für {function_name} existiert bereits")
            
            # Prüfe, ob die VM läuft
            vm_status = self._get_vm_status(vm_name)
            if vm_status == "running":
                logger.info(f"VM {vm_name} läuft bereits")
                # Aktualisiere Netzwerkkonfiguration, falls angegeben
                if network_config:
                    self.update_vm_network(function_name, network_config)
                return vm_name
            elif vm_status == "stopped":
                logger.info(f"VM {vm_name} ist gestoppt, starte neu")
                self._start_vm(vm_name)
                return vm_name
            else:
                logger.info(f"VM {vm_name} existiert nicht mehr, erstelle neu")
                # VM existiert nicht mehr, entferne aus Mapping
                del self.vms[function_name]
        
        # Generiere einen eindeutigen VM-Namen
        vm_name = f"{function_name}-{uuid.uuid4().hex[:8]}"
        
        # Erstelle ein temporäres Dockerfile für diese Funktion
        docker_file = self._create_function_dockerfile(function_name)
        
        # Port-Mapping erhalten
        port_mapping = self.port_mapping.get(function_name, "8000:8000")
        host_port, container_port = port_mapping.split(":")
        
        # Umgebungsvariablen festlegen
        env_vars = [
            f"FUNCTION_NAME={function_name}",
            f"MEMORY_SIZE={memory_mb}",
            f"PORT={container_port}"
        ]
        
        # Netzwerkkonfiguration hinzufügen
        if network_config:
            network_vars = self._network_config_to_env(network_config)
            env_vars.extend(network_vars)
        
        # Kommando zum Erstellen der VM
        cmd = [
            "sudo", "ignite", "run",
            "--name", vm_name,
            "--cpus", str(cpu_count),
            "--memory", f"{memory_mb}MB",
            "--ssh",
            "--ports", port_mapping
        ]
        
        # Umgebungsvariablen hinzufügen
        for env in env_vars:
            cmd.extend(["-e", env])
        
        # Kernel und Image angeben
        cmd.extend([
            "--kernel", "weaveworks/ignite-kernel:5.10.51",
            "--image", "lambda-base-image"
        ])
        
        # Kopiere Funktionsdateien in die VM
        # Wir erstellen einen Befehl zum Erstellen der benötigten Verzeichnisse
        # und zum Kopieren der Dateien
        cmd.extend([
            "--copy-files", f"{docker_file}:/tmp/Dockerfile",
            "--copy-files", f"functions/webshop/{function_name}/:/app/function/",
            "--copy-files", "docker/entrypoint.sh:/app/entrypoint.sh"
        ])
        
        # VM starten
        logger.info(f"Starte VM mit Kommando: {' '.join(cmd)}")
        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            logger.info(f"VM erstellt: {result.stdout.strip()}")
        except subprocess.CalledProcessError as e:
            logger.error(f"Fehler beim Erstellen der VM: {e.stderr}")
            raise
        
        # VM im Dictionary speichern
        self.vms[function_name] = vm_name
        
        # Warte, bis der Service in der VM bereit ist
        self._wait_for_service_ready(host_port)
        
        logger.info(f"VM {vm_name} für {function_name} bereit")
        return vm_name
    
    def _create_function_dockerfile(self, function_name):
        """Erstellt ein temporäres Dockerfile für die Funktion"""
        temp_dir = "/tmp/ignite_dockerfiles"
        os.makedirs(temp_dir, exist_ok=True)
        
        dockerfile_path = f"{temp_dir}/Dockerfile_{function_name}"
        
        with open(dockerfile_path, "w") as f:
            f.write(f"""
FROM lambda-base-image

# Kopiere Funktionsdateien
COPY /app/function/ /app/

# Mache entrypoint.sh ausführbar
RUN chmod +x /app/entrypoint.sh

# Setze Umgebungsvariablen
ENV FUNCTION_NAME={function_name}
ENV PORT=8000

# Starte entrypoint
ENTRYPOINT ["/app/entrypoint.sh"]
""")
        
        return dockerfile_path
    
    def _network_config_to_env(self, network_config):
        """Konvertiert Netzwerkkonfiguration in Umgebungsvariablen"""
        env_vars = []
        
        if "latency_ms" in network_config:
            env_vars.append(f"LATENCY_MS={network_config['latency_ms']}")
            
        if "latency_jitter_ms" in network_config:
            env_vars.append(f"LATENCY_JITTER_MS={network_config['latency_jitter_ms']}")
        else:
            env_vars.append("LATENCY_JITTER_MS=5")  # Standardwert
            
        if "loss_percent" in network_config:
            env_vars.append(f"LOSS_PERCENT={network_config['loss_percent']}")
            
        if "corrupt_percent" in network_config:
            env_vars.append(f"CORRUPT_PERCENT={network_config['corrupt_percent']}")
            
        if "reorder_percent" in network_config:
            env_vars.append(f"REORDER_PERCENT={network_config['reorder_percent']}")
            
        if "bandwidth_kbit" in network_config and network_config["bandwidth_kbit"]:
            env_vars.append(f"BANDWIDTH_KBIT={network_config['bandwidth_kbit']}")
            
        return env_vars
    
    def _get_vm_status(self, vm_name):
        """Überprüft den Status einer VM"""
        try:
            result = subprocess.run(
                ["sudo", "ignite", "ps", "-q"],
                check=True,
                capture_output=True,
                text=True
            )
            
            # Überprüfe, ob die VM in der Liste der laufenden VMs ist
            running_vms = result.stdout.strip().split("\n")
            for vm_line in running_vms:
                if vm_name in vm_line:
                    return "running"
            
            # Überprüfe, ob die VM in der Liste der gestoppten VMs ist
            result = subprocess.run(
                ["sudo", "ignite", "ps", "-q", "--all"],
                check=True,
                capture_output=True,
                text=True
            )
            
            all_vms = result.stdout.strip().split("\n")
            for vm_line in all_vms:
                if vm_name in vm_line:
                    return "stopped"
            
            return "not_exists"
            
        except subprocess.CalledProcessError:
            logger.error(f"Fehler beim Überprüfen des VM-Status für {vm_name}")
            return "error"
    
    def _start_vm(self, vm_name):
        """Startet eine gestoppte VM"""
        try:
            subprocess.run(
                ["sudo", "ignite", "start", vm_name],
                check=True,
                capture_output=True,
                text=True
            )
            logger.info(f"VM {vm_name} gestartet")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Fehler beim Starten der VM {vm_name}: {e.stderr}")
            return False
    
    def _wait_for_service_ready(self, port, timeout=60):
        """Wartet, bis der Service auf dem angegebenen Port bereit ist"""
        start_time = time.time()
        
        logger.info(f"Warte auf Service-Bereitschaft auf Port {port}")
        
        while time.time() - start_time < timeout:
            try:
                # Prüfe, ob der Service erreichbar ist
                result = subprocess.run(
                    ["curl", "-s", f"http://localhost:{port}/health"],
                    capture_output=True,
                    text=True,
                    check=False
                )
                
                if result.returncode == 0 and "healthy" in result.stdout:
                    logger.info(f"Service auf Port {port} ist bereit")
                    return True
            except Exception as e:
                logger.debug(f"Fehler beim Prüfen des Service: {e}")
            
            # Warte kurz vor dem nächsten Versuch
            time.sleep(1)
        
        logger.warning(f"Timeout beim Warten auf Service-Bereitschaft auf Port {port}")
        return False
    
    def invoke_function(self, function_name, event_data):
        """Ruft eine Funktion in einer VM auf"""
        # Prüfe, ob eine VM für diese Funktion existiert
        if function_name not in self.vms:
            logger.info(f"Keine VM für {function_name} gefunden, erstelle eine neue")
            self.create_vm(function_name)
        
        vm_name = self.vms[function_name]
        
        # Überprüfe, ob die VM läuft
        status = self._get_vm_status(vm_name)
        if status != "running":
            logger.info(f"VM {vm_name} läuft nicht, starte sie neu")
            if not self._start_vm(vm_name):
                logger.error(f"Konnte VM {vm_name} nicht starten, erstelle eine neue")
                self.create_vm(function_name)
                vm_name = self.vms[function_name]
        
        # Port für den Funktionsaufruf ermitteln
        port_mapping = self.port_mapping.get(function_name, "8000:8000")
        host_port = port_mapping.split(":")[0]
        
        # Event-Daten als JSON
        event_json = json.dumps(event_data)
        
        # Funktion aufrufen
        logger.info(f"Rufe Funktion {function_name} in VM {vm_name} auf Port {host_port} auf")
        try:
            result = subprocess.run(
                ["curl", "-X", "POST",
                 "-H", "Content-Type: application/json",
                 "-d", event_json,
                 f"http://localhost:{host_port}/invoke"],
                capture_output=True,
                text=True,
                check=True
            )
            
            # Parsen der Antwort
            response = json.loads(result.stdout)
            logger.info(f"Funktionsaufruf erfolgreich: {response.get('statusCode', 'unknown')}")
            return response
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Fehler beim Aufruf der Funktion {function_name}: {e.stderr}")
            return {"error": f"Funktionsaufruf fehlgeschlagen: {e}"}
        except json.JSONDecodeError:
            logger.error(f"Ungültige JSON-Antwort von Funktion {function_name}")
            return {"error": "Ungültige Antwort"}
    
    def update_vm_network(self, function_name, network_config):
        """Aktualisiert die Netzwerkkonfiguration einer VM"""
        if function_name not in self.vms:
            logger.warning(f"Keine VM für {function_name} gefunden")
            return False
        
        vm_name = self.vms[function_name]
        
        # Überprüfe, ob die VM läuft
        if self._get_vm_status(vm_name) != "running":
            logger.warning(f"VM {vm_name} läuft nicht, kann Netzwerk nicht aktualisieren")
            return False
        
        # Port für den Konfigurationsendpunkt ermitteln
        port_mapping = self.port_mapping.get(function_name, "8000:8000")
        host_port = port_mapping.split(":")[0]
        
        # Netzwerkkonfiguration als JSON
        network_json = json.dumps(network_config)
        
        # Konfiguration aktualisieren
        logger.info(f"Aktualisiere Netzwerkkonfiguration für {function_name} in VM {vm_name}")
        try:
            result = subprocess.run(
                ["curl", "-X", "POST",
                 "-H", "Content-Type: application/json",
                 "-d", network_json,
                 f"http://localhost:{host_port}/network"],
                capture_output=True,
                text=True,
                check=True
            )
            
            logger.info(f"Netzwerkkonfiguration aktualisiert: {result.stdout}")
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Fehler beim Aktualisieren der Netzwerkkonfiguration: {e.stderr}")
            return False
    
    def stop_vm(self, function_name):
        """Stoppt eine VM"""
        if function_name not in self.vms:
            logger.warning(f"Keine VM für {function_name} gefunden")
            return False
        
        vm_name = self.vms[function_name]
        
        # Stoppt die VM
        logger.info(f"Stoppe VM {vm_name} für {function_name}")
        try:
            subprocess.run(
                ["sudo", "ignite", "stop", vm_name],
                check=True,
                capture_output=True,
                text=True
            )
            
            logger.info(f"VM {vm_name} gestoppt")
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Fehler beim Stoppen der VM {vm_name}: {e.stderr}")
            return False
    
    def cleanup(self):
        """Bereinigt alle erstellten VMs"""
        logger.info("Beginne Bereinigung aller VMs")
        
        # Sammle alle VM-Namen
        vm_names = list(self.vms.values())
        
        for vm_name in vm_names:
            try:
                # Versuche, die VM zu stoppen
                subprocess.run(
                    ["sudo", "ignite", "stop", vm_name],
                    check=False,
                    capture_output=True,
                    text=True
                )
                
                # Versuche, die VM zu löschen
                subprocess.run(
                    ["sudo", "ignite", "rm", "-f", vm_name],
                    check=False,
                    capture_output=True,
                    text=True
                )
                
                logger.info(f"VM {vm_name} bereinigt")
                
            except Exception as e:
                logger.error(f"Fehler beim Bereinigen der VM {vm_name}: {e}")
        
        # Leere das VM-Dictionary
        self.vms.clear()
        logger.info("Bereinigung abgeschlossen")