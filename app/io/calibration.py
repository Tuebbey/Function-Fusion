# app/io/calibration.py

import json
import os
import subprocess
import time
from typing import Dict, List, Any

class IOCalibrator:
    """Tool zur Kalibrierung zwischen einfacher I/O und FIO-Metriken."""
    
    def __init__(self, base_dir="/tmp/io_calibration"):
        self.base_dir = base_dir
        os.makedirs(base_dir, exist_ok=True)
    
    def calibrate(self, iterations_range=[1, 5, 10, 20, 50], file_sizes_kb=[1, 10, 100, 1000], 
                 runs_per_config=3) -> Dict[str, Any]:
        """
        Führt Kalibrierungstests durch und erstellt ein Mapping zwischen 
        einfachen I/O-Operationen und FIO-Metriken.
        """
        results = {}
        
        for iterations in iterations_range:
            for file_size_kb in file_sizes_kb:
                key = f"iter_{iterations}_size_{file_size_kb}"
                results[key] = {}
                
                # Einfache I/O-Tests
                simple_times = []
                for _ in range(runs_per_config):
                    start_time = time.time()
                    self._run_simple_io(iterations, file_size_kb)
                    end_time = time.time()
                    simple_times.append((end_time - start_time) * 1000)
                
                # FIO-Tests
                fio_results = []
                for _ in range(runs_per_config):
                    fio_result = self._run_fio_test(file_size_kb)
                    fio_results.append(fio_result)
                
                # Ergebnisse aggregieren
                results[key]["simple_io"] = {
                    "avg_time_ms": sum(simple_times) / len(simple_times),
                    "min_time_ms": min(simple_times),
                    "max_time_ms": max(simple_times),
                    "iterations": iterations,
                    "file_size_kb": file_size_kb
                }
                
                results[key]["fio"] = self._aggregate_fio_results(fio_results)
        
        # Speichere Kalibrierungsdaten
        os.makedirs("config", exist_ok=True)
        with open("config/io_calibration.json", "w") as f:
            json.dump(results, f, indent=2)
        
        return results
    
    def _run_simple_io(self, iterations, file_size_kb):
        """Führt einfache I/O-Operationen durch."""
        test_dir = f"{self.base_dir}/simple_io_{int(time.time())}"
        os.makedirs(test_dir, exist_ok=True)
        
        for i in range(iterations):
            # Schreiben
            with open(f"{test_dir}/test_{i}.dat", "wb") as f:
                f.write(os.urandom(file_size_kb * 1024))
                f.flush()
                os.fsync(f.fileno())
            
            # Lesen
            with open(f"{test_dir}/test_{i}.dat", "rb") as f:
                _ = f.read()
    
    def _run_fio_test(self, size_mb):
        """Führt einen FIO-Test durch."""
        test_file = f"{self.base_dir}/fio_test_{int(time.time())}.dat"
        
        cmd = [
            "fio", "--name=test", f"--filename={test_file}",
            "--rw=randrw", "--rwmixread=70", "--bs=4k", 
            f"--size={max(1, size_mb / 1024)}M", "--direct=1", 
            "--ioengine=libaio", "--runtime=2", "--time_based", 
            "--output-format=json"
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                return json.loads(result.stdout)
            else:
                return {"error": f"FIO-Fehler: {result.stderr}"}
        except Exception as e:
            return {"error": f"Exception: {str(e)}"}
    
    def _aggregate_fio_results(self, fio_results):
        """Aggregiert mehrere FIO-Ergebnisse."""
        if not fio_results or "error" in fio_results[0]:
            return {"error": "Keine gültigen FIO-Ergebnisse"}
        
        aggregated = {
            "read_iops": 0,
            "write_iops": 0,
            "read_bw_kb": 0,
            "write_bw_kb": 0
        }
        
        count = 0
        for result in fio_results:
            if "jobs" in result and result["jobs"]:
                job = result["jobs"][0]
                aggregated["read_iops"] += job["read"]["iops"]
                aggregated["write_iops"] += job["write"]["iops"]
                aggregated["read_bw_kb"] += job["read"]["bw"] / 1024
                aggregated["write_bw_kb"] += job["write"]["bw"] / 1024
                count += 1
        
        if count > 0:
            for key in aggregated:
                aggregated[key] /= count
        
        return aggregated