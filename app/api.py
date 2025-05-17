from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.runtime import runtime
from app.fusion import fusion_engine
from typing import List
import importlib

router = APIRouter()

# Modell für Funktionsaufruf
class FunctionCall(BaseModel):
    name: str
    event: dict

@router.post("/invoke/function")
async def invoke_function(payload: FunctionCall):
    try:
        result = await runtime.invoke(payload.name, payload.event)
        return {"output": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))



# Modell für Funktionsregistrierung
class FunctionRegistration(BaseModel):
    name: str
    module: str
    function: str

@router.post("/register/function")
def register_function(payload: FunctionRegistration):
    try:
        mod = importlib.import_module(payload.module)
        func = getattr(mod, payload.function)
        runtime.register(payload.name, func)
        return {"message": f"Funktion '{payload.name}' erfolgreich registriert."}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Fehler bei Registrierung: {str(e)}")


# 🔧 HIER: Modell für Fusion
class FusionDefinition(BaseModel):
    name: str
    functions: List[str]

@router.post("/register/fusion")
def register_fusion(payload: FusionDefinition):
    try:
        fusion_engine.register_fusion(payload.name, payload.functions)
        return {"message": f"Fusion '{payload.name}' erfolgreich registriert."}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Fehler bei Fusion: {str(e)}")

class FusionExecution(BaseModel):
    name: str
    event: dict

@router.post("/invoke/fusion")
async def invoke_fusion(payload: FusionExecution):
    """
    Führt eine registrierte Fusion asynchron aus.
    """
    try:
        result = await fusion_engine.execute(payload.name, payload.event, runtime)
        return {"output": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Fehler bei Fusion-Ausführung: {str(e)}")


