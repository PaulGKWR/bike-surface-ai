#!/usr/bin/env python3
"""
Quick Test für Datensammlung
Testet ob alle Module korrekt geladen werden können
"""

import sys
import os

# Füge edge-Verzeichnis zum Python Path hinzu
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("╔═══════════════════════════════════════════╗")
print("║   Module Test - Datensammlung            ║")
print("╚═══════════════════════════════════════════╝\n")

modules = [
    ("YAML", "yaml"),
    ("OpenCV", "cv2"),
    ("NumPy", "numpy"),
    ("PySerial", "serial"),
    ("PyNMEA2", "pynmea2"),
    ("Requests", "requests"),
]

all_ok = True
for name, module in modules:
    try:
        mod = __import__(module)
        version = getattr(mod, '__version__', 'OK')
        print(f"✓ {name:.<25} {version}")
    except ImportError as e:
        print(f"✗ {name:.<25} FEHLT")
        all_ok = False

print("\n" + "="*47)

if all_ok:
    print("✓ Alle Module verfügbar!")
    print("\nSie können jetzt starten:")
    print("  - Desktop Icon 'Datensammlung' klicken")
    print("  - Oder: ./start_collection.sh")
else:
    print("⚠ Einige Module fehlen. Bitte installieren Sie:")
    print("  ./setup_jetson.sh")

sys.exit(0 if all_ok else 1)
