from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import httpx
import logging
import os
import asyncio
from datetime import datetime
from typing import Dict, Any
from. import handler

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title=f"Lambda Function Server - {os.getenv('FUNCTION_NAME', 'unknown')}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

http_client = None

@app.on_event("startup")
async def startup_event():
    global http_client
    http_client = httpx.AsyncClient(
        timeout=httpx.Timeout(30.0),
        limits=httpx.Limits(max_keepalive_connections=20, max_connections=100)
    )
    logger.info(f"Started function server for {os.getenv('FUNCTION_NAME', 'unknown')}")

@app.on_event("shutdown")
async def shutdown_event():
    global http_client
    if http_client:
        await http_client.aclose()
    logger.info("Shutdown complete")

async def call_function(name: str, payload: dict, sync: bool = True) -> dict:
    if not http_client:
        raise RuntimeError("HTTP client not initialized")
    
    target_service = resolve_function_service(name)
    url = f"http://{target_service}:8000/invoke"

    enhanced_payload = {
        "name": name,
        "event": payload,
        "metadata": {
            "caller": os.getenv('FUNCTION_NAME', 'unknown'),
            "timestamp": datetime.utcnow().isoformat(),
            "sync": sync,
            "trace_id": payload.get("trace_id") if payload else None
        }
    }

    try:
        start_time = asyncio.get_event_loop().time()

        if sync:
            response = await http_client.post(url, json=enhanced_payload)
            response.raise_for_status()
            result = response.json()
        else:
            asyncio.create_task(http_client.post(url, json=enhanced_payload))
            result = {"status": "async_called"}

        end_time = asyncio.get_event_loop().time()
        duration_ms = (end_time - start_time) * 1000
        logger.info(f"Called {name} ({sync=}) in {duration_ms:.2f}ms")

        return result

    except httpx.TimeoutException:
        logger.error(f"Timeout calling {name}")
        raise HTTPException(status_code=504, detail=f"Function {name} timed out")
    except httpx.RequestError as e:
        logger.error(f"Network error calling {name}: {e}")
        raise HTTPException(status_code=503, detail=f"Cannot reach function {name}")
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error calling {name}: {e.response.status_code}")
        raise HTTPException(status_code=e.response.status_code, detail=f"Function {name} returned error")

def resolve_function_service(function_name: str) -> str:
    return function_name.lower().replace("_", "-")

@app.post("/invoke")
async def invoke(request: Request):
    try:
        payload = await request.json()
        function_name = payload.get("name", os.getenv('FUNCTION_NAME'))
        event = payload.get("event", payload)
        metadata = payload.get("metadata", {})

        context = create_lambda_context(metadata)

        async def call_function_wrapper(name: str, event: dict, sync: bool = True):
            return await call_function(name, event, sync)

        start_time = asyncio.get_event_loop().time()
        result = await handler.handler(event, context, call_function_wrapper)
        end_time = asyncio.get_event_loop().time()
        duration_ms = (end_time - start_time) * 1000

        return {
            "statusCode": 200,
            "body": result,
            "executionTime": duration_ms,
            "metadata": {
                "function": function_name,
                "timestamp": datetime.utcnow().isoformat(),
                "duration_ms": duration_ms
            }
        }

    except Exception as e:
        logger.error(f"Error during invocation: {e}", exc_info=True)
        return {
            "statusCode": 500,
            "body": {"error": str(e), "type": type(e).__name__},
            "metadata": {
                "function": os.getenv('FUNCTION_NAME', 'unknown'),
                "timestamp": datetime.utcnow().isoformat(),
                "error": True
            }
        }

def create_lambda_context(metadata: dict) -> dict:
    return {
        "function_name": os.getenv('FUNCTION_NAME', 'unknown'),
        "function_version": "$LATEST",
        "invoked_function_arn": f"arn:aws:lambda:local:123456789012:function:{os.getenv('FUNCTION_NAME', 'unknown')}",
        "memory_limit_in_mb": int(os.getenv('MEMORY_SIZE', '128')),
        "remaining_time_in_millis": lambda: 60000,
        "log_group_name": f"/aws/lambda/{os.getenv('FUNCTION_NAME', 'unknown')}",
        "log_stream_name": "local-stream",
        "aws_request_id": metadata.get("trace_id", "local-request-id"),
        "metadata": metadata
    }

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "function": os.getenv('FUNCTION_NAME', 'unknown'),
        "timestamp": datetime.utcnow().isoformat()
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv('PORT', 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
