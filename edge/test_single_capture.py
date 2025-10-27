#!/usr/bin/env python3
"""Test: Ein einzelnes Bild mit GPS capturen"""

import cv2
import time
from gps_module import GPSModule
from pathlib import Path
from datetime import datetime

print("="*60)
print("TEST: Einzelbild mit GPS")
print("="*60)

# GPS starten
print("\n1️⃣ GPS verbinden...")
gps = GPSModule({'port': '/dev/ttyACM0', 'baudrate': 9600, 'timeout': 1.0})

# Auf Fix warten
print("2️⃣ Warte auf GPS-Fix (max 10s)...")
fix = None
for i in range(10):
    fix = gps.get_current_position()
    if fix and fix.get('latitude') is not None:
        sats = int(fix.get('satellites', 0)) if fix.get('satellites') else 0
        print(f"   ✓ GPS-Fix: {fix['latitude']:.6f}, {fix['longitude']:.6f}")
        print(f"   ✓ Satelliten: {sats}")
        break
    print(f"   ⏳ Warte... ({i+1}/10)")
    time.sleep(1)

if not fix:
    print("   ❌ Kein GPS-Fix! Gehe ins Freie!")
    gps.close()
    exit(1)

# Kamera öffnen
print("\n3️⃣ Kamera öffnen...")
cap = cv2.VideoCapture(0)
if not cap.isOpened():
    print("   ❌ Kamera fehlt!")
    gps.close()
    exit(1)

cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
print(f"   ✓ Kamera: {int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))}x{int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))}")

# Bild aufnehmen
print("\n4️⃣ Bild aufnehmen...")
ret, frame = cap.read()
if not ret:
    print("   ❌ Kein Frame!")
    cap.release()
    gps.close()
    exit(1)

# Speichern
output_dir = Path("test_capture")
output_dir.mkdir(exist_ok=True)
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
img_path = output_dir / f"test_{timestamp}.jpg"

cv2.imwrite(str(img_path), frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
print(f"   ✓ Gespeichert: {img_path}")
print(f"   ✓ GPS: {fix['latitude']:.6f}, {fix['longitude']:.6f}")

# Cleanup
cap.release()
gps.close()

print("\n" + "="*60)
print("✓ TEST ERFOLGREICH!")
print("="*60)
print(f"\nBild: {img_path}")
print(f"GPS: {fix['latitude']:.6f}, {fix['longitude']:.6f}")
print(f"Größe: {img_path.stat().st_size / 1024 / 1024:.2f} MB")
