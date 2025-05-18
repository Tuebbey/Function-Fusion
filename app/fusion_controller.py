# app/fusion_controller.py
from fastapi import FastAPI, HTTPException
import httpx
import asyncio
from typing import Dict, List, Any
import os
import logging

logger = logging.getLogger(__name__)

class FusionController:
    def __init__(self):
        self.app = FastAPI(title="Fusion Controller")
        self.http_client = None
        self.fusion_configs = {}
        self.setup_routes()
    
    def setup_routes(self):
        @self.app.on_event("startup")
        async def startup():
            self.http_client = httpx.AsyncClient(timeout=30.0)
        
        @self.app.on_event("shutdown")
        async def shutdown():
            if self.http_client:
                await self.http_client.aclose()
        
        @self.app.post("/fusion/{fusion_name}")
        async def execute_fusion(fusion_name: str, event: Dict[str, Any]):
            """Führt eine definierte Fusion aus"""
            return await self.execute_fusion_workflow(fusion_name, event)
        
        @self.app.post("/config/fusion")
        async def configure_fusion(config: Dict[str, Any]):
            """Konfiguriert eine neue Fusion"""
            self.fusion_configs[config["name"]] = config
            return {"status": "configured"}
    
    async def execute_fusion_workflow(self, fusion_name: str, event: Dict[str, Any]):
        """Führt eine Fusion basierend auf der Konfiguration aus"""
        config = self.fusion_configs.get(fusion_name)
        if not config:
            raise HTTPException(404, f"Fusion {fusion_name} not found")
        
        # Implementiere die Fusion-Logik
        results = []
        for step in config["steps"]:
            if step["type"] == "local":
                result = await self.call_local_function(step["function"], event)
            else:
                result = await self.call_remote_function(step["function"], event)
            results.append(result)
            event = result.get("body", event)  # Chain results
        
        return {"fusion": fusion_name, "results": results}
    
    async def call_remote_function(self, function_name: str, event: Dict[str, Any]):
        """Ruft eine Funktion remote auf"""
        service_name = function_name.replace("_", "-")
        port = self.get_service_port(service_name)
        url = f"http://{service_name}:8000/invoke"
        
        response = await self.http_client.post(url, json={"event": event})
        return response.json()
    
    def get_service_port(self, service_name: str) -> int:
        """Mapping von Service-Namen zu Ports"""
        port_mapping = {
            "add-cart-item": 8002,
            "cart-kv-storage": 8003,
            # weitere Services...
        }
        return port_mapping.get(service_name, 8000)

# Instanz erstellen
fusion_controller = FusionController()
app = fusion_controller.app