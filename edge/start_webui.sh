#!/bin/bash
# Starte Web-UI für Bike Surface AI

cd "$(dirname "$0")"

echo "╔═══════════════════════════════════════════╗"
echo "║   Starte Bike Surface AI Web-UI...       ║"
echo "╚═══════════════════════════════════════════╝"
echo ""

# Prüfe Flask
if ! python3 -c "import flask" 2>/dev/null; then
    echo "Installiere Flask..."
    pip3 install flask
fi

# Starte Server
python3 web_ui.py
