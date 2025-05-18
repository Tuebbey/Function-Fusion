# functions/webshop/cartkvstorage/handler.py

import asyncio
import json
import os
import time
import subprocess
import random
from typing import Dict, Any, Optional

async def handler(event, context=None, call_function=None):
    """
    Simuliert eine cartkvstorage-Funktion mit konfigurierbaren I/O-Operationen und optionaler FIO-Integration.
    """
    print("[cartkvstorage] Event empfangen:", event)

    operation = event.get("operation", "").lower()
    user_id = event.get("userId", "unknown")
    item = event.get("item", {})
    
    # I/O-Parameter extrahieren (falls vorhanden)
    io_params = event.get("io_params", {})
    io_iterations = io_params.get("iterations", 1)  # Standard: 1 Iteration
    io_file_size_kb = io_params.get("file_size_kb", 10)  # Standard: 10 KB
    enable_fsync = io_params.get("enable_fsync", False)  # Standard: kein fsync
    enable_fio = io_params.get("enable_fio", False)  # Standard: kein FIO

    if operation == "add":
        print(f"[cartkvstorage] Füge Artikel für User {user_id} hinzu:", item)
        start_time = time.time()
        
        try:
            # 1. CPU-Last simulieren (reduzierte Last für bessere Testbarkeit)
            await asyncio.to_thread(_simulate_workload, 5_000)
            cpu_end_time = time.time()
            cpu_time = cpu_end_time - start_time
            
            # 2. Reale Datei-I/O mit konfigurierbarer Intensität
            storage_dir = f"/tmp/fusion_storage/{user_id}"
            os.makedirs(storage_dir, exist_ok=True)
            cart_file = f"{storage_dir}/cart.json"
            
            io_stats = {
                "iterations": io_iterations, 
                "file_size_kb": io_file_size_kb,
                "fsync_enabled": enable_fsync
            }
            io_start_time = time.time()
            
            # Durchführen der konfigurierten Anzahl von I/O-Operationen
            for i in range(io_iterations):
                # Lesen, falls Datei existiert
                cart_data = []
                if os.path.exists(cart_file):
                    with open(cart_file, 'r') as f:
                        try:
                            cart_data = json.load(f)
                        except json.JSONDecodeError:
                            cart_data = []
                
                # Warenkorb erweitern und speichern
                cart_data.append({**item, "timestamp": time.time()})
                
                # Schreiben mit optionalem fsync für garantiertes Flushen auf Festplatte
                with open(cart_file, 'w') as f:
                    json.dump(cart_data, f, indent=2)
                    if enable_fsync:
                        f.flush()
                        os.fsync(f.fileno())
                
                # Zusätzliche Dateien für mehr I/O-Last
                if io_file_size_kb > 0:
                    # Erstelle eine Datei mit zufälligen Daten in der konfigurierten Größe
                    random_data = os.urandom(io_file_size_kb * 1024)
                    with open(f"{storage_dir}/data_{i}.bin", 'wb') as f:
                        f.write(random_data)
                        if enable_fsync:
                            f.flush()
                            os.fsync(f.fileno())
            
            io_end_time = time.time()
            io_time = io_end_time - io_start_time
            io_stats["time_ms"] = io_time * 1000
            
            # 3. Optional: FIO-Benchmark durchführen (nur falls aktiviert)
            fio_stats = {}
            if enable_fio:
                fio_stats = await asyncio.to_thread(_run_fio_benchmark, storage_dir, io_file_size_kb)
                fio_end_time = time.time()
                fio_stats["time_ms"] = (fio_end_time - io_end_time) * 1000
            
            end_time = time.time()
            
            return {
                "status": "added",
                "userId": user_id,
                "item": item,
                "performance": {
                    "total_time_ms": (end_time - start_time) * 1000,
                    "cpu_time_ms": cpu_time * 1000,
                    "io_time_ms": io_time * 1000,
                    "io_stats": io_stats,
                    "fio_stats": fio_stats if enable_fio else {"enabled": False}
                }
            }
        except Exception as e:
            print(f"[cartkvstorage] ❗ Fehler: {e}")
            return {
                "error": "Operation fehlgeschlagen",
                "details": str(e)
            }

    elif operation == "get":
        print(f"[cartkvstorage] Gebe Cart für User {user_id} zurück")
        start_time = time.time()
        
        try:
            # I/O-Parameter für GET-Operationen
            io_iterations = io_params.get("iterations", 1)
            io_file_size_kb = io_params.get("file_size_kb", 5)
            
            # Echtes Lesen aus dem Dateisystem
            storage_dir = f"/tmp/fusion_storage/{user_id}"
            cart_file = f"{storage_dir}/cart.json"
            
            cart_data = []
            io_start_time = time.time()
            
            # Wiederholte Lesezugriffe (konfigurierbar)
            for _ in range(io_iterations):
                if os.path.exists(cart_file):
                    with open(cart_file, 'r') as f:
                        try:
                            cart_data = json.load(f)
                        except json.JSONDecodeError:
                            cart_data = []
                
                # Zusätzliche Lesezugriffe für höhere I/O-Last
                if io_file_size_kb > 0:
                    for i in range(min(5, io_iterations)):
                        test_file = f"{storage_dir}/data_{i}.bin"
                        if os.path.exists(test_file):
                            with open(test_file, 'rb') as f:
                                _ = f.read(io_file_size_kb * 1024)
            
            io_end_time = time.time()
            io_time = io_end_time - io_start_time
            
            # Optional: FIO für Leseoperationen
            fio_stats = {}
            if enable_fio:
                fio_stats = await asyncio.to_thread(
                    _run_fio_benchmark, storage_dir, io_file_size_kb, "random_read")
            
            end_time = time.time()
            
            return {
                "userId": user_id,
                "items": cart_data,
                "performance": {
                    "total_time_ms": (end_time - start_time) * 1000,
                    "io_time_ms": io_time * 1000,
                    "io_stats": {
                        "iterations": io_iterations,
                        "file_size_kb": io_file_size_kb,
                        "time_ms": io_time * 1000
                    },
                    "fio_stats": fio_stats if enable_fio else {"enabled": False}
                }
            }
        except Exception as e:
            print(f"[cartkvstorage] ❗ Fehler beim Lesen: {e}")
            return {
                "error": "Leseoperation fehlgeschlagen",
                "details": str(e),
                "userId": user_id,
                "items": []
            }

    elif operation == "empty":
        print(f"[cartkvstorage] Leere Cart für User {user_id}")
        start_time = time.time()
        
        try:
            storage_dir = f"/tmp/fusion_storage/{user_id}"
            cart_file = f"{storage_dir}/cart.json"
            
            files_removed = 0
            
            # Lösche die Cartdatei
            if os.path.exists(cart_file):
                os.remove(cart_file)
                files_removed += 1
            
            # Lösche alle zusätzlichen Datendateien
            for i in range(50):  # Maximal 50 Datendateien suchen
                data_file = f"{storage_dir}/data_{i}.bin"
                if os.path.exists(data_file):
                    os.remove(data_file)
                    files_removed += 1
            
            # Optional: FIO für Schreiboperationen (Löschen ist auch Schreiben)
            fio_stats = {}
            if enable_fio:
                fio_stats = await asyncio.to_thread(
                    _run_fio_benchmark, storage_dir, io_params.get("file_size_kb", 10), "random_write")
            
            end_time = time.time()
            
            return {
                "status": "emptied",
                "userId": user_id,
                "performance": {
                    "total_time_ms": (end_time - start_time) * 1000,
                    "files_removed": files_removed,
                    "fio_stats": fio_stats if enable_fio else {"enabled": False}
                }
            }
        except Exception as e:
            print(f"[cartkvstorage] ❗ Fehler beim Leeren: {e}")
            return {
                "error": "Leeren fehlgeschlagen",
                "details": str(e)
            }

    else:
        print(f"[cartkvstorage] ❗ Unbekannte Operation: {operation}")
        return {
            "error": "Unbekannte Operation",
            "received_operation": operation
        }

def _simulate_workload(limit: int = 5_000):
    """Rechenintensive Aufgabe (Primzahlen finden) – simuliert CPU-Last."""
    primes = []
    nums = list(range(2, limit))
    for i in nums:
        if all(i % p != 0 for p in primes):
            primes.append(i)
    return primes

def _run_fio_benchmark(directory: str, size_mb: int = 1, pattern: str = "random_write") -> Dict[str, Any]:
    """
    Führt einen FIO-Benchmark mit konfigurierbaren Parametern durch.
    
    Args:
        directory: Verzeichnis für die Testdateien
        size_mb: Dateigröße in MB (1-10)
        pattern: FIO-Testmuster ('random_read', 'random_write', 'mixed')
        
    Returns:
        Dict mit FIO-Statistiken oder Fehlermeldung
    """
    try:
        os.makedirs(directory, exist_ok=True)
        
        # Testdateiname
        test_file = f"{directory}/fio_test_{int(time.time())}.dat"
        
        # FIO-Parameter basierend auf dem gewählten Muster
        if pattern == "random_read":
            rw_param = "randread"
        elif pattern == "random_write":
            rw_param = "randwrite"
        else:  # mixed
            rw_param = "randrw"
            
        # Begrenze Dateigröße und Laufzeit für effiziente Tests
        size_mb = min(10, max(1, size_mb))
        
        # Bereite FIO-Befehl vor
        cmd = [
            "fio", "--name=test", f"--filename={test_file}",
            f"--rw={rw_param}", "--bs=4k", 
            f"--size={size_mb}M", "--direct=1", "--ioengine=libaio",
            "--runtime=1", "--time_based", "--output-format=json"
        ]
        
        # Mixread-Parameter falls gemischter Test
        if pattern == "mixed":
            cmd.extend(["--rwmixread=70"])
        
        # FIO ausführen
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            try:
                fio_data = json.loads(result.stdout)
                
                # Vereinfachte Metriken extrahieren
                job = fio_data.get("jobs", [{}])[0]
                simplified_stats = {
                    "pattern": pattern,
                    "size_mb": size_mb,
                    "iops": {
                        "read": job.get("read", {}).get("iops", 0),
                        "write": job.get("write", {}).get("iops", 0)
                    },
                    "bandwidth_kb": {
                        "read": job.get("read", {}).get("bw", 0) / 1024,
                        "write": job.get("write", {}).get("bw", 0) / 1024
                    },
                    "latency_ms": {
                        "read": job.get("read", {}).get("lat_ns", {}).get("mean", 0) / 1000000,
                        "write": job.get("write", {}).get("lat_ns", {}).get("mean", 0) / 1000000
                    }
                }
                return simplified_stats
                
            except json.JSONDecodeError:
                return {"error": "Konnte FIO-Output nicht parsen"}
        else:
            return {"error": f"FIO-Fehler: {result.stderr}"}
            
    except Exception as e:
        return {"error": f"Exception bei FIO-Ausführung: {str(e)}"}