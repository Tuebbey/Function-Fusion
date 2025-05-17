#!/bin/bash
set -e

echo "[entrypoint] Starte Funktion: $FUNCTION_NAME"

LOGFILE="/app/tc_config.log"
echo "==== Netzwerkkonfiguration für $FUNCTION_NAME ====" > "$LOGFILE"
echo "Timestamp: $(date -u)" >> "$LOGFILE"

# Vorherige Regeln entfernen (falls vorhanden)
tc qdisc del dev eth0 root 2>/dev/null || true

# NETEM-Regeln zusammensetzen
NETEM_ARGS=""

if [ -n "$LATENCY_MS" ] && [ "$LATENCY_MS" != "0" ]; then
  NETEM_ARGS="$NETEM_ARGS delay ${LATENCY_MS}ms"
  if [ -n "$LATENCY_JITTER_MS" ] && [ "$LATENCY_JITTER_MS" != "0" ]; then
    NETEM_ARGS="$NETEM_ARGS ${LATENCY_JITTER_MS}ms"
  fi
fi

if [ -n "$LOSS_PERCENT" ] && [ "$LOSS_PERCENT" != "0" ]; then
  NETEM_ARGS="$NETEM_ARGS loss ${LOSS_PERCENT}%"
fi

if [ -n "$CORRUPT_PERCENT" ] && [ "$CORRUPT_PERCENT" != "0" ]; then
  NETEM_ARGS="$NETEM_ARGS corrupt ${CORRUPT_PERCENT}%"
fi

if [ -n "$REORDER_PERCENT" ] && [ "$REORDER_PERCENT" != "0" ]; then
  NETEM_ARGS="$NETEM_ARGS reorder ${REORDER_PERCENT}%"
fi

# Falls Netem-Regeln gesetzt werden sollen
if [ -n "$NETEM_ARGS" ]; then
  echo "[entrypoint] Setze netem-Regeln: $NETEM_ARGS" | tee -a "$LOGFILE"
  tc qdisc add dev eth0 root handle 1: netem $NETEM_ARGS 2>> "$LOGFILE" || echo "⚠️ Netem konnte nicht gesetzt werden" >> "$LOGFILE"
else
  # Dummy qdisc setzen
  tc qdisc add dev eth0 root handle 1: pfifo 2>/dev/null || true
fi

# Bandbreitenlimit hinzufügen (tbf)
if [ -n "$BANDWIDTH_KBIT" ] && [ "$BANDWIDTH_KBIT" != "0" ]; then
  echo "[entrypoint] Setze TBF-Regel: ${BANDWIDTH_KBIT}kbit" | tee -a "$LOGFILE"
  tc qdisc add dev eth0 parent 1:1 handle 10: tbf rate ${BANDWIDTH_KBIT}kbit burst 32kbit latency 400ms 2>> "$LOGFILE" || echo "⚠️ TBF konnte nicht gesetzt werden" >> "$LOGFILE"
fi

echo "[entrypoint] Netzwerksetup abgeschlossen. Starte Server..." | tee -a "$LOGFILE"

# Starte die FastAPI-Anwendung
exec python server.py
