import asyncio
import httpx
import logging
import json
import os
import time
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)

class ServiceDiscovery:
    def __init__(self, config_path: str = "config/services.json", ttl: int = 60):
        self.service_registry: Dict[str, str] = {}
        self.health_check_cache: Dict[str, Tuple[bool, float]] = {}  # (result, timestamp)
        self.ttl = ttl  # seconds
        self._load_config(config_path)

    def _load_config(self, path: str):
        if not os.path.exists(path):
            logger.warning(f"No service config found at {path}")
            return
        try:
            with open(path, "r") as f:
                data = json.load(f)
                for func_name, container_name in data.items():
                    self.service_registry[func_name] = container_name
            logger.info(f"Loaded service config from {path}")
        except Exception as e:
            logger.error(f"Failed to load service config: {e}")

    async def register_service(self, function_name: str, container_name: str):
        self.service_registry[function_name] = container_name

    async def discover_service(self, function_name: str) -> Optional[str]:
        if function_name in self.service_registry:
            return self.service_registry[function_name]

        fallback_name = function_name.lower().replace("_", "-")
        logger.debug(f"Using fallback service name for {function_name}: {fallback_name}")
        self.service_registry[function_name] = fallback_name
        return fallback_name

    async def health_check(self, service_name: str) -> bool:
        now = time.time()

        if service_name in self.health_check_cache:
            result, timestamp = self.health_check_cache[service_name]
            if now - timestamp < self.ttl:
                return result

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"http://{service_name}:8000/health")
                is_healthy = response.status_code == 200
        except Exception as e:
            logger.warning(f"Health check failed for {service_name}: {e}")
            is_healthy = False

        self.health_check_cache[service_name] = (is_healthy, now)
        return is_healthy


# Globale Instanz
service_discovery = ServiceDiscovery()
