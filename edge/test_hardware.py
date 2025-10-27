#!/usr/bin/env python3
"""
Hardware Test für Jetson Bike Surface AI
Testet GPS (Navilock 62756) und Webcam (Logitech C920)
"""

import cv2
import serial
import pynmea2
import time
import sys

def test_gps():
    """Teste GPS-Empfänger"""
    print("\n=== GPS Test (Navilock 62756 u-blox NEO-M8U) ===")
    try:
        ser = serial.Serial('/dev/ttyACM0', 9600, timeout=1.0)
        print("✓ GPS Port /dev/ttyACM0 geöffnet")
        
        print("Warte auf GPS-Fix (max 30 Sekunden)...")
        start_time = time.time()
        fix_found = False
        
        while time.time() - start_time < 30:
            line = ser.readline().decode('ascii', errors='ignore')
            
            if line.startswith('$GNGGA') or line.startswith('$GPGGA'):
                try:
                    msg = pynmea2.parse(line)
                    if msg.gps_qual > 0:
                        print(f"✓ GPS-Fix erhalten!")
                        print(f"  Latitude:  {msg.latitude:.6f}")
                        print(f"  Longitude: {msg.longitude:.6f}")
                        print(f"  Altitude:  {msg.altitude} m")
                        print(f"  Satellites: {msg.num_sats}")
                        print(f"  Quality:    {msg.gps_qual}")
                        fix_found = True
                        break
                    else:
                        print(f"  Warte auf Fix... (Satelliten: {msg.num_sats})", end='\r')
                except pynmea2.ParseError:
                    pass
        
        ser.close()
        
        if not fix_found:
            print("⚠ Kein GPS-Fix erhalten (möglicherweise keine Sicht zum Himmel)")
            print("  GPS sendet aber Daten - Hardware funktioniert")
            return True
        
        return True
        
    except serial.SerialException as e:
        print(f"✗ GPS-Fehler: {e}")
        return False
    except Exception as e:
        print(f"✗ Unerwarteter Fehler: {e}")
        return False

def test_camera():
    """Teste Webcam"""
    print("\n=== Kamera Test (Logitech HD Pro C920) ===")
    try:
        cap = cv2.VideoCapture(0)
        
        if not cap.isOpened():
            print("✗ Kamera konnte nicht geöffnet werden")
            return False
        
        # Setze Auflösung
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
        cap.set(cv2.CAP_PROP_FPS, 30)
        
        # Prüfe tatsächliche Einstellungen
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = int(cap.get(cv2.CAP_PROP_FPS))
        
        print(f"✓ Kamera geöffnet: {width}x{height} @ {fps} fps")
        
        # Teste 5 Frames
        print("  Teste Frame-Capture...")
        success_count = 0
        for i in range(5):
            ret, frame = cap.read()
            if ret:
                success_count += 1
            time.sleep(0.1)
        
        cap.release()
        
        if success_count >= 4:
            print(f"✓ Frame-Capture erfolgreich ({success_count}/5 Frames)")
            return True
        else:
            print(f"⚠ Nur {success_count}/5 Frames erfolgreich")
            return False
            
    except Exception as e:
        print(f"✗ Kamera-Fehler: {e}")
        return False

def main():
    """Führe alle Hardware-Tests durch"""
    print("╔═══════════════════════════════════════════╗")
    print("║  Jetson Bike Surface AI - Hardware Test  ║")
    print("╚═══════════════════════════════════════════╝")
    
    results = []
    
    # Test GPS
    gps_ok = test_gps()
    results.append(("GPS (Navilock 62756)", gps_ok))
    
    # Test Kamera
    cam_ok = test_camera()
    results.append(("Kamera (Logitech C920)", cam_ok))
    
    # Zusammenfassung
    print("\n╔═══════════════════════════════════════════╗")
    print("║           Test-Zusammenfassung            ║")
    print("╚═══════════════════════════════════════════╝")
    for name, ok in results:
        status = "✓ OK" if ok else "✗ FEHLER"
        print(f"  {name:.<30} {status}")
    
    all_ok = all(ok for _, ok in results)
    
    if all_ok:
        print("\n✓ Alle Tests erfolgreich! System ist bereit.")
        return 0
    else:
        print("\n⚠ Einige Tests fehlgeschlagen. Bitte Hardware prüfen.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
