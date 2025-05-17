FROM python:3.9-slim

# Systempakete für tc und Tools installieren
RUN apt-get update && apt-get install -y \
    iproute2 \
    net-tools \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Arbeitsverzeichnis setzen
WORKDIR /app

# requirements.txt kopieren und Pakete installieren
COPY requirements.txt .
RUN pip install -r requirements.txt

# Funktion spezifische Dateien einfügen (abhängig vom Build-Arg)
ARG FUNCTION_NAME
COPY functions/${FUNCTION_NAME}/ ./

# entrypoint.sh kopieren und ausführbar machen
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Umgebungsvariablen setzen
ENV FUNCTION_NAME=${FUNCTION_NAME}
ENV PORT=8000

# Port freigeben
EXPOSE 8000

# entrypoint starten (setzt Netzwerkeffekte und startet Python-App)
ENTRYPOINT ["/entrypoint.sh"]
