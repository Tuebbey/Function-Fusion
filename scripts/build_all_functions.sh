#!/bin/bash
# scripts/build_all_functions.sh

set -e

BASE_DIR=$(dirname "$0")/..
cd "$BASE_DIR"

# Liste aller Webshop-Funktionen
FUNCTIONS=(
    "webshop/frontend"
    "webshop/addcartitem"
    "webshop/cartkvstorage"
    "webshop/getcart"
    "webshop/emptycart"
    "webshop/listproducts"
    "webshop/getproduct"
    "webshop/searchproducts"
    "webshop/listrecommendations"
    "webshop/shipmentquote"
    "webshop/shiporder"
    "webshop/checkout"
    "webshop/payment"
    "webshop/currency"
    "webshop/supportedcurrencies"
    "webshop/getads"
    "webshop/email"
)

# Kopiere Templates (server.py, Dockerfile, requirements.txt) in alle Funktionsverzeichnisse
for func in "${FUNCTIONS[@]}"; do
    echo "🔧 Setting up $func..."

    FUNC_DIR="functions/$func"
    mkdir -p "$FUNC_DIR"

    # server.py kopieren
    cp docker/server_template.py "$FUNC_DIR/server.py"

    # Dockerfile kopieren, wenn nicht vorhanden
    if [ ! -f "$FUNC_DIR/Dockerfile" ]; then
        cp docker/function.Dockerfile "$FUNC_DIR/Dockerfile"
    fi

    # requirements.txt generieren, wenn nicht vorhanden
    if [ ! -f "$FUNC_DIR/requirements.txt" ]; then
        cat > "$FUNC_DIR/requirements.txt" << EOF
fastapi>=0.68.0
uvicorn>=0.15.0
httpx>=0.24.0
pydantic>=1.8.0
EOF
    fi
done

echo "✅ Alle Webshop-Funktionen sind bereit für Docker-Container."
