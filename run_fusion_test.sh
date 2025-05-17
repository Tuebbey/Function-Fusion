#!/bin/bash

# Function Fusion Test Runner für Docker Setup
# Autor: System
# Beschreibung: Startet Docker Container und führt Function Fusion Tests durch

set -e

echo "=========================================="
echo "Function Fusion Test mit Docker"
echo "=========================================="

# Prüfe ob Docker läuft
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker läuft nicht. Bitte starten Sie Docker und versuchen Sie es erneut."
    exit 1
fi

# Prüfe ob docker-compose verfügbar ist
if ! command -v docker-compose &> /dev/null; then
    echo "❌ docker-compose nicht gefunden. Bitte installieren Sie docker-compose."
    exit 1
fi

echo "✅ Docker und docker-compose sind verfügbar"

# Erstelle results Verzeichnis falls nicht vorhanden
mkdir -p results

# Stoppe eventuell laufende Container
echo "🧹 Stoppe eventuell laufende Container..."
docker-compose down

# Baue und starte alle Container
echo "🔨 Baue und starte alle Container..."
docker-compose up --build -d

# Warte auf Container-Initialisierung
echo "⏳ Warte auf Container-Initialisierung (30 Sekunden)..."
sleep 30

# Prüfe ob alle Container laufen
echo "🔍 Prüfe Container Status..."
if ! docker-compose ps | grep -q "Up"; then
    echo "❌ Nicht alle Container sind gestartet. Prüfen Sie die Logs:"
    docker-compose logs
    exit 1
fi

echo "✅ Alle Container sind gestartet"

# Health Check für einige Services
echo "🏥 Führe Health Checks durch..."
services=("frontend:8001" "add-cart-item:8002" "cart-kv-storage:8003" "checkout:8012")

for service in "${services[@]}"; do
    service_name=${service%%:*}
    port=${service##*:}
    
    if curl -s "http://localhost:${port}/health" > /dev/null; then
        echo "✅ ${service_name} ist bereit"
    else
        echo "⚠️  ${service_name} antwortet nicht auf Health Check"
    fi
done

# Führe Python Test durch
echo ""
echo "🚀 Starte Function Fusion Tests..."
echo "=========================================="

# Führe den Test aus
python3 tests/run_fusion_test_docker.py

# Checke Ergebnisse
echo ""
echo "📊 Teste abgeschlossen!"

# Zeige die neuesten Ergebnisse
latest_result=$(ls -t results/docker_fusion_test_*.json 2>/dev/null | head -n1)

if [ -n "$latest_result" ]; then
    echo "📁 Neuestes Ergebnis: $latest_result"
    
    # Extrahiere einige Key-Metriken mit jq (falls verfügbar)
    if command -v jq &> /dev/null; then
        echo ""
        echo "🎯 Zusammenfassung:"
        echo "=================="
        
        # Individual vs Fusion Vergleich
        individual_time=$(jq -r '.individual_functions.total_time_ms // "N/A"' "$latest_result")
        fusion_time=$(jq -r '.fusion_simulation.fusion_call.total_time_ms // "N/A"' "$latest_result")
        
        if [ "$individual_time" != "N/A" ] && [ "$fusion_time" != "N/A" ]; then
            echo "Einfacher Test:"
            echo "  Individuelle Aufrufe: ${individual_time}ms"
            echo "  Function Fusion: ${fusion_time}ms"
            
            # Berechne Speedup (bash kann nur mit ganzen Zahlen, daher verwenden wir bc falls verfügbar)
            if command -v bc &> /dev/null; then
                speedup=$(echo "scale=2; $individual_time / $fusion_time" | bc)
                echo "  Speedup: ${speedup}x"
            fi
        fi
        
        # Komplexer Workflow
        complex_individual=$(jq -r '.complex_workflow.comparison.individual_time_ms // "N/A"' "$latest_result")
        complex_fusion=$(jq -r '.complex_workflow.comparison.fusion_time_ms // "N/A"' "$latest_result")
        
        if [ "$complex_individual" != "N/A" ] && [ "$complex_fusion" != "N/A" ]; then
            echo ""
            echo "Komplexer Workflow:"
            echo "  Individuelle Aufrufe: ${complex_individual}ms"
            echo "  Function Fusion: ${complex_fusion}ms"
            
            if command -v bc &> /dev/null; then
                speedup=$(echo "scale=2; $complex_individual / $complex_fusion" | bc)
                echo "  Speedup: ${speedup}x"
            fi
        fi
    fi
else
    echo "⚠️ Keine Ergebnisdatei gefunden"
fi

echo ""
echo "📁 Alle Ergebnisse sind im results/ Verzeichnis gespeichert"
echo ""
echo "Wollen Sie die Container laufen lassen? (j/N): "
read -r response

if [[ ! $response =~ ^[jJ]$ ]]; then
    echo "🛑 Stoppe alle Container..."
    docker-compose down
    echo "✅ Container gestoppt"
else
    echo "🏃 Container bleiben aktiv"
    echo "Stoppen Sie sie später mit: docker-compose down"
fi

echo ""
echo "✅ Function Fusion Test abgeschlossen!"