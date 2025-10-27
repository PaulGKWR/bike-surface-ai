#!/usr/bin/env python3
"""Schneller GPS-Check"""

from gps_module import GPSModule
import time

print("GPS-Check gestartet...")
print("Lese GPS für 5 Sekunden...\n")

try:
    gps = GPSModule({'port': '/dev/ttyACM0', 'baudrate': 9600, 'timeout': 1.0})
    
    for i in range(5):
        fix = gps.get_current_position()
        if fix:
            print(f"✓ FIX: Lat={fix['latitude']:.6f}, Lon={fix['longitude']:.6f}, Sats={fix.get('satellites', 0)}")
        else:
            print(f"✗ Kein Fix (Versuch {i+1}/5)")
        time.sleep(1)
    
    gps.close()
    print("\n✓ GPS-Test abgeschlossen")
    
except Exception as e:
    print(f"❌ FEHLER: {e}")
    import traceback
    traceback.print_exc()
