# docker_fusion_tester.py
import asyncio
import httpx
import json
import os

class DockerFusionTester:
    """Führt Tests mit Docker-basierten Funktionen durch."""
    
    def __init__(self, services_url_base="http://localhost"):
        self.services_url_base = services_url_base
        self.http_client = None
    
    async def setup(self):
        """Initialisiert den Tester."""
        self.http_client = httpx.AsyncClient(timeout=30.0)
        print("DockerFusionTester bereit")
    
    async def cleanup(self):
        """Räumt Ressourcen auf."""
        if self.http_client:
            await self.http_client.aclose()
    
    async def invoke_function(self, function_name, event_data):
        """Ruft eine Funktion auf und gibt das Ergebnis zurück."""
        # Service-Port bestimmen (z.B. 8000 + Service-Index)
        service_name = function_name.lower().replace("_", "-")
        url = f"{self.services_url_base}:{self._get_service_port(service_name)}/invoke"
        
        # Aufruf durchführen
        try:
            start_time = asyncio.get_event_loop().time()
            response = await self.http_client.post(url, json=event_data)
            end_time = asyncio.get_event_loop().time()
            
            if response.status_code == 200:
                result = response.json()
                # Ausführungszeit hinzufügen
                execution_time = (end_time - start_time) * 1000  # ms
                result["execution_time_ms"] = execution_time
                return result
            else:
                return {
                    "error": f"Status {response.status_code}",
                    "execution_time_ms": (end_time - start_time) * 1000
                }
                
        except Exception as e:
            return {"error": str(e), "execution_time_ms": 0}
    
    async def update_function_config(self, function_name, config_updates):
        """Aktualisiert die Konfiguration einer Funktion (z. B. Memory)."""
        service_name = function_name.lower().replace("_", "-")
        url = f"{self.services_url_base}:{self._get_service_port(service_name)}/config"
        
        try:
            response = await self.http_client.post(url, json=config_updates)
            return response.status_code == 200
        except Exception as e:
            print(f"Fehler beim Aktualisieren der Konfiguration: {e}")
            return False
        
    async def update_network_config(self, function_name, network_config):
        """Aktualisiert die Netzwerkkonfiguration einer Funktion."""
        service_name = function_name.lower().replace("_", "-")
        url = f"{self.services_url_base}:{self._get_service_port(service_name)}/network"
        
        try:
            response = await self.http_client.post(url, json=network_config)
            return response.status_code == 200
        except Exception as e:
            print(f"Fehler beim Aktualisieren der Netzwerkkonfiguration: {e}")
            return False


    def _get_service_port(self, service_name):
        """Gibt den Port für einen Service zurück."""
        # Idealerweise aus einer Konfigurationsdatei oder Environment lesen
        service_ports = {
            "addcartitem": 8001,
            "cartkvstorage": 8002,
            "checkout": 8003,
            "currency": 8004,
            "email": 8005,
            "emptycart": 8006,
            "frontend": 8007,
            "getads": 8008,
            "getcart": 8009,
            "getproduct": 8010,
            "listproducts": 8011,
            "listrecommendations": 8012,
            "payment": 8013,
            "searchproducts": 8014,
            "shipmentquote": 8015,
            "shiporder": 8016,
            "supportedcurrencies": 8017
        }
        return service_ports.get(service_name, 8000)