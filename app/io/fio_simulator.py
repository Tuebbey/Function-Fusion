import subprocess
import json
import os
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("lambda-sim.io")

class FIOSimulator:
    """
    Simuliert I/O-Operationen mit FIO basierend auf realistischen AWS Lambda-I/O-Mustern.
    """
    
    def __init__(self, config_dir: str = "config/fio-patterns"):
        """
        Initialisiert den FIO-Simulator.
        
        Args:
            config_dir: Verzeichnis mit FIO-Konfigurationsdateien
        """
        self.config_dir = config_dir
        # Überprüfe, ob FIO installiert ist
        try:
            subprocess.run(["fio", "--version"], capture_output=True, check=True)
            self.fio_available = True
        except (subprocess.CalledProcessError, FileNotFoundError):
            self.fio_available = False
            logger.warning("FIO nicht gefunden. I/O-Simulation wird eingeschränkt sein.")
    
    def run_io_pattern(self, pattern_name: str, size_mb: int = 10, 
                      duration_sec: int = 5, tmp_dir: str = "/tmp") -> Dict[str, Any]:
        """
        Führt ein vordefiniertes I/O-Muster aus.
        
        Args:
            pattern_name: Name des I/O-Musters (z.B. 'random_read', 'random_write', 'mixed')
            size_mb: Größe des zu verwendenden Dateibereichs in MB
            duration_sec: Dauer der Ausführung in Sekunden
            tmp_dir: Verzeichnis für temporäre Dateien
            
        Returns:
            Dictionary mit I/O-Statistiken oder Fehlermeldung
        """
        if not self.fio_available:
            return self._simulate_io_pattern(pattern_name, size_mb, duration_sec)
        
        # Pfad zur FIO-Konfigurationsdatei
        config_file = os.path.join(self.config_dir, f"lambda_tmp_{pattern_name}.fio")
        
        if not os.path.exists(config_file):
            logger.error(f"FIO-Konfigurationsdatei nicht gefunden: {config_file}")
            return {"error": f"Konfigurationsdatei nicht gefunden: {pattern_name}"}
        
        # FIO-Befehl vorbereiten
        cmd = [
            "fio", 
            "--output-format=json",
            f"--directory={tmp_dir}",
            f"--size={size_mb}M",
            f"--runtime={duration_sec}",
            config_file
        ]
        
        try:
            # FIO ausführen
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            # JSON-Output parsen
            fio_stats = json.loads(result.stdout)
            
            # Relevante Statistiken extrahieren
            return self._extract_io_stats(fio_stats, pattern_name)
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Fehler bei der Ausführung von FIO: {e}")
            return {"error": f"FIO-Ausführungsfehler: {e}"}
        except json.JSONDecodeError as e:
            logger.error(f"Fehler beim Parsen der FIO-Ausgabe: {e}")
            return {"error": f"FIO-Ausgabe konnte nicht geparst werden: {e}"}
    
    def _extract_io_stats(self, fio_stats: Dict[str, Any], pattern_name: str) -> Dict[str, Any]:
        """Extrahiert relevante I/O-Statistiken aus den FIO-Ergebnissen."""
        if "jobs" not in fio_stats or not fio_stats["jobs"]:
            return {"error": "Keine gültigen FIO-Ergebnisse"}
        
        job = fio_stats["jobs"][0]
        
        # Basis-Statistiken
        stats = {
            "pattern": pattern_name,
            "iops": {
                "read": job["read"]["iops"],
                "write": job["write"]["iops"]
            },
            "latency_ns": {
                "read": {
                    "min": job["read"]["lat_ns"]["min"],
                    "max": job["read"]["lat_ns"]["max"],
                    "mean": job["read"]["lat_ns"]["mean"]
                },
                "write": {
                    "min": job["write"]["lat_ns"]["min"],
                    "max": job["write"]["lat_ns"]["max"],
                    "mean": job["write"]["lat_ns"]["mean"]
                }
            },
            "bandwidth_bytes": {
                "read": job["read"]["bw_bytes"],
                "write": job["write"]["bw_bytes"]
            }
        }
        
        return stats
    
    def _simulate_io_pattern(self, pattern_name: str, size_mb: int, duration_sec: int) -> Dict[str, Any]:
        """
        Simuliert I/O-Muster in Python, wenn FIO nicht verfügbar ist.
        Dies ist eine vereinfachte Simulation und nicht so realistisch wie FIO.
        """
        logger.warning("Verwende Python-basierte I/O-Simulation statt FIO")
        
        # Realistische I/O-Performance-Werte für AWS Lambda basierend auf Benchmarks
        io_performance = {
            "random_read": {
                "iops": 3000,
                "latency_ns": {"min": 50000, "max": 5000000, "mean": 300000},
                "bandwidth_bytes": 12 * 1024 * 1024  # 12 MB/s
            },
            "random_write": {
                "iops": 2000,
                "latency_ns": {"min": 80000, "max": 8000000, "mean": 500000},
                "bandwidth_bytes": 8 * 1024 * 1024  # 8 MB/s
            },
            "mixed": {
                "iops": 2500,
                "latency_ns": {"min": 60000, "max": 6000000, "mean": 400000},
                "bandwidth_bytes": 10 * 1024 * 1024  # 10 MB/s
            }
        }
        
        if pattern_name not in io_performance:
            return {"error": f"Unbekanntes I/O-Muster: {pattern_name}"}
        
        # Größe und Dauer berücksichtigen
        performance = io_performance[pattern_name]
        scale_factor = (size_mb / 10) * (duration_sec / 5)
        
        return {
            "pattern": pattern_name,
            "iops": {
                "read": int(performance["iops"] * scale_factor * (0.7 if pattern_name == "mixed" else 1.0)),
                "write": int(performance["iops"] * scale_factor * (0.3 if pattern_name == "mixed" else 0.0 if pattern_name == "random_read" else 1.0))
            },
            "latency_ns": performance["latency_ns"],
            "bandwidth_bytes": int(performance["bandwidth_bytes"] * scale_factor),
            "simulated": True  # Kennzeichnung, dass dies simulierte Werte sind
        }