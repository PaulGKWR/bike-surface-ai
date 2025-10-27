#!/usr/bin/env python3
"""
Schneller GPS-Test
"""

import sys
sys.path.insert(0, '/home/kwr/bike-surface-ai/edge')

from gps_module import GPSModule
import time

print("GPS Test...")

config = {'port': '/dev/ttyACM0', 'baudrate': 9600, 'timeout': 1.0}

try:
    gps = GPSModule(config)
    print("✓ GPS verbunden")
    
    print("\nLese 10 Sekunden GPS-Daten:\n")
    
    for i in range(10):
        fix = gps.get_current_position()
        if fix:
            print(f"[{i+1}] GPS: {fix['latitude']:.6f}, {fix['longitude']:.6f} | Alt: {fix['altitude']:.1f}m | Sats: {fix.get('satellites', 0)}")
        else:
            print(f"[{i+1}] Kein Fix")
        time.sleep(1)
    
    gps.close()
    print("\n✓ Test beendet")
    
except Exception as e:
    print(f"❌ Fehler: {e}")
    import traceback
    traceback.print_exc()
