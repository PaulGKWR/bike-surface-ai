#!/usr/bin/env python3
"""
Einfaches Capture-Script für Bike Surface AI
Stabil und ohne GUI-Konflikte
"""

import cv2
import time
import json
import sys
from pathlib import Path
from datetime import datetime
from math import radians, cos, sin, asin, sqrt

# GPS Import
try:
    from gps_module import GPSModule
    GPS_AVAILABLE = True
except ImportError:
    GPS_AVAILABLE = False
    print("⚠ GPS-Modul nicht verfügbar")


def calculate_distance(lat1, lon1, lat2, lon2):
    """Berechne Distanz zwischen zwei GPS-Punkten (Haversine)"""
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    return c * 6371000  # Erdradius in Metern


def main():
    print("="*60)
    print("  🚴 Bike Surface AI - Datensammlung")
    print("="*60)
    
    # Config aus Argument oder Default
    if len(sys.argv) > 1:
        # Output-Dir als Argument übergeben
        output_dir = Path(sys.argv[1])
        if not output_dir.exists():
            output_dir.mkdir(parents=True, exist_ok=True)
            (output_dir / "images").mkdir(exist_ok=True)
        
        # Log-Datei erstellen
        log_file = output_dir / "capture.log"
        log_handle = open(log_file, 'w', buffering=1)  # Line buffered
        
        # Umleiten von stdout zu Log
        original_stdout = sys.stdout
        
        class TeeOutput:
            def __init__(self, *files):
                self.files = files
            def write(self, data):
                for f in self.files:
                    f.write(data)
                    f.flush()
            def flush(self):
                for f in self.files:
                    f.flush()
        
        sys.stdout = TeeOutput(original_stdout, log_handle)
        
        print(f"📝 Log wird geschrieben nach: {log_file}")
        
        config = {
            "camera": {"device_id": 0, "resolution": [1920, 1080], "fps": 10},
            "gps": {"port": "/dev/ttyACM0", "baudrate": 9600, "timeout": 1.0},
            "collection": {"capture_interval": 2.0, "image_quality": 95}
        }
    else:
        # Default Config
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = Path(f"data_collection/{timestamp}")
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "images").mkdir(exist_ok=True)
        
        config = {
            "camera": {"device_id": 0, "resolution": [1920, 1080], "fps": 10},
            "gps": {"port": "/dev/ttyACM0", "baudrate": 9600, "timeout": 1.0},
            "collection": {"capture_interval": 2.0, "image_quality": 95}
        }
    
    print(f"\n📁 Output: {output_dir}")
    print(f"⚙️  Intervall: {config['collection']['capture_interval']}s")
    print(f"📷 Auflösung: {config['camera']['resolution']}")
    
    # Kamera öffnen
    print("\n📷 Öffne Kamera...")
    cap = cv2.VideoCapture(config['camera']['device_id'])
    
    if not cap.isOpened():
        print("❌ Kamera konnte nicht geöffnet werden!")
        return 1
    
    width, height = config['camera']['resolution']
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    cap.set(cv2.CAP_PROP_FPS, config['camera']['fps'])
    
    actual_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    actual_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"✓ Kamera: {actual_width}x{actual_height}")
    
    # GPS öffnen
    gps = None
    if GPS_AVAILABLE:
        print("\n🌍 Öffne GPS...")
        try:
            gps = GPSModule(config['gps'])
            print("✓ GPS verbunden")
            
            # Warte auf Fix
            print("⏳ Warte auf GPS-Fix (max 30s)...")
            start_wait = time.time()
            has_fix = False
            while time.time() - start_wait < 30:
                fix = gps.get_current_position()
                if fix and fix.get('latitude') is not None:
                    sats = int(fix.get('satellites', 0)) if fix.get('satellites') else 0
                    print(f"✓ GPS-Fix: {fix['latitude']:.6f}, {fix['longitude']:.6f}")
                    print(f"  Satelliten: {sats}")
                    has_fix = True
                    break
                print(".", end="", flush=True)
                time.sleep(1)
            
            if not has_fix:
                print("\n⚠ Kein GPS-Fix erhalten")
                print("  WICHTIG: Bilder werden NUR mit GPS-Fix gespeichert!")
                print("  Bitte ins Freie gehen oder GPS-Antenne prüfen")
        except Exception as e:
            print(f"⚠ GPS-Fehler: {e}")
            gps = None
    else:
        print("\n⚠ GPS-Modul nicht verfügbar - keine Bilder ohne GPS!")
    
    # Capture-Loop
    print("\n" + "="*60)
    print("🟢 AUFNAHME GESTARTET")
    print("="*60)
    print("Drücke Strg+C zum Beenden\n")
    
    route_points = []
    image_count = 0
    last_capture = time.time()
    start_time = time.time()
    total_distance = 0.0
    
    capture_interval = config['collection']['capture_interval']
    image_quality = config['collection']['image_quality']
    
    try:
        while True:
            # Frame lesen
            ret, frame = cap.read()
            
            if not ret:
                print("⚠ Kein Frame empfangen")
                time.sleep(0.1)
                continue
            
            # Zeit für nächstes Bild?
            current_time = time.time()
            if current_time - last_capture >= capture_interval:
                
                # GPS lesen (falls vorhanden). Wir speichern jetzt auch ohne GPS-Fix,
                # damit die Aufnahme nicht komplett blockiert wird. Vorherige
                # Implementierungen haben hier Bilder verhindert.
                gps_fix = None
                if gps:
                    gps_fix = gps.get_current_position()
                    if not gps_fix:
                        print("⚠ GPS-Fix nicht vorhanden - speichere Bild ohne GPS")
                else:
                    print("⚠ Kein GPS-Modul - speichere Bild ohne GPS")

                # Bild speichern (auch ohne GPS)
                img_name = f"img_{image_count:06d}.jpg"
                img_path = output_dir / "images" / img_name
                img_path.parent.mkdir(parents=True, exist_ok=True)

                cv2.imwrite(str(img_path), frame, [cv2.IMWRITE_JPEG_QUALITY, image_quality])

                # GPS/Metadaten (falls vorhanden)
                point = {
                    "image": img_name,
                    "timestamp": datetime.now().isoformat(),
                    "latitude": gps_fix["latitude"] if gps_fix and gps_fix.get("latitude") is not None else None,
                    "longitude": gps_fix["longitude"] if gps_fix and gps_fix.get("longitude") is not None else None,
                    "altitude": gps_fix.get("altitude") if gps_fix and gps_fix.get("altitude") is not None else None
                }
                route_points.append(point)

                # Distanz berechnen nur wenn beide Punkte Koordinaten haben
                if len(route_points) > 1 and route_points[-2]["latitude"] is not None and route_points[-1]["latitude"] is not None:
                    p1 = route_points[-2]
                    p2 = route_points[-1]
                    dist = calculate_distance(
                        p1['latitude'], p1['longitude'],
                        p2['latitude'], p2['longitude']
                    )
                    total_distance += dist

                image_count += 1
                last_capture = current_time

                # Status ausgeben
                elapsed = int(current_time - start_time)
                if point['latitude'] is not None:
                    print(f"[{elapsed:04d}s] 📸 Bild {image_count:04d} | GPS: {point['latitude']:.5f},{point['longitude']:.5f} | Dist: {total_distance:.1f}m")
                else:
                    print(f"[{elapsed:04d}s] 📸 Bild {image_count:04d} | GPS: N/A | Dist: {total_distance:.1f}m")

                # Zwischenspeicherung alle 10 Bilder
                if image_count % 10 == 0:
                    save_route_data(output_dir, route_points, total_distance)
            
            time.sleep(0.05)  # 20 Hz Check
            
    except KeyboardInterrupt:
        print("\n\n🛑 Beende Aufnahme...")
    
    finally:
        # Cleanup
        print("\n📝 Speichere Daten...")
        
        if route_points:
            save_route_data(output_dir, route_points, total_distance)
            print(f"✓ Route gespeichert: {len(route_points)} Punkte")
        
        cap.release()
        if gps:
            gps.close()
        
        # Zusammenfassung
        elapsed = int(time.time() - start_time)
        print("\n" + "="*60)
        print("📊 ZUSAMMENFASSUNG")
        print("="*60)
        print(f"Bilder:   {image_count}")
        print(f"Distanz:  {total_distance:.1f} m ({total_distance/1000:.2f} km)")
        print(f"Laufzeit: {elapsed//60}:{elapsed%60:02d} min")
        print(f"Ordner:   {output_dir}")
        print("="*60)
    
    return 0


def save_route_data(output_dir, route_points, total_distance):
    """Speichere Route als GeoJSON und Metadaten"""
    
    # GeoJSON
    # Build coordinates only from points that have valid lat/lon
    coords = []
    for p in route_points:
        if p.get('latitude') is not None and p.get('longitude') is not None:
            coords.append([p['longitude'], p['latitude'], p.get('altitude', 0.0)])

    geojson = {
        "type": "FeatureCollection",
        "features": []
    }

    if coords:
        geojson['features'].append({
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": coords
            },
            "properties": {
                "name": "Bike Route",
                "timestamp": datetime.now().isoformat(),
                "images": len(route_points),
                "distance_m": round(total_distance, 2)
            }
        })
    
    with open(output_dir / "route.geojson", "w") as f:
        json.dump(geojson, f, indent=2)
    
    # Metadaten
    metadata = {
        "session_start": route_points[0]["timestamp"] if route_points else None,
        "session_end": datetime.now().isoformat(),
        "total_images": len(route_points),
        "distance_m": round(total_distance, 2),
        "camera": "Logitech C920",
        "resolution": "1920x1080",
        "gps": "Navilock 62756",
        "points": route_points
    }
    
    with open(output_dir / "metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"\n❌ FEHLER: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
