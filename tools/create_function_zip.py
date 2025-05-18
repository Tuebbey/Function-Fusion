import os
import json
import shutil
from pathlib import Path

# Basis-Verzeichnis
base_dir = Path("example_function_project")
fusionables_dir = base_dir / "fusionables"
metadata_dir = base_dir / "metadata"

# Vorheriges Beispiel ggf. löschen
if base_dir.exists():
    shutil.rmtree(base_dir)
if Path("function.zip").exists():
    Path("function.zip").unlink()

# Funktionen definieren
functions = {
    "A": 'print("Function A running...")\nimport time\ntime.sleep(1)\nprint("Function A done.")',
    "B": 'print("Function B running...")\nimport time\ntime.sleep(1)\nprint("Function B done.")',
    "C": 'print("Function C running...")\nimport time\ntime.sleep(1)\nprint("Function C done.")',
}

# Projektstruktur anlegen
for fname, code in functions.items():
    func_dir = fusionables_dir / fname
    func_dir.mkdir(parents=True, exist_ok=True)
    with open(func_dir / "handler.py", "w") as f:
        f.write(f"def handler():\n    " + code.replace("\n", "\n    "))

# Beispiel-Konfiguration
config = {
    "1234567890": {
        "traceName": 1234567890,
        "rules": {
            "A": {
                "A": {"sync": {"strategy": "local"}, "async": {"strategy": "local"}},
                "B": {"sync": {"strategy": "local"}, "async": {"strategy": "remote", "url": "B"}}
            },
            "B": {
                "C": {"sync": {"strategy": "remote", "url": "C"}, "async": {"strategy": "remote", "url": "C"}}
            }
        }
    }
}
metadata_dir.mkdir(parents=True, exist_ok=True)
with open(metadata_dir / "configurationMetadata.json", "w") as f:
    json.dump(config, f, indent=4)

# Archiv erstellen
shutil.make_archive("function", "zip", root_dir=base_dir)

print("✅ function.zip wurde erfolgreich erzeugt.")
