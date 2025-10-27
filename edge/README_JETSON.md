# Jetson Edge System - Benutzeranleitung

## Übersicht

Das Jetson Edge System hat **zwei Betriebsmodi**:

1. **Datenerfassungs-Modus** (Data Collection): GPS + Kamera Aufzeichnung ohne KI
2. **Inferenz-Modus** (Live Detection): Echtzeit-Schadenerkennung mit trainiertem Modell

---

## 1. Datenerfassungs-Modus

### Zweck
Strecke mit GPS und Kamera aufzeichnen, um Trainingsdaten für Modellentwicklung zu sammeln.

### Verwendung

```bash
cd /home/kwr/bike-surface-ai/edge
./start_collection.sh
```

### Was passiert:
- Kamera nimmt alle 2 Sekunden ein Bild auf
- GPS-Position wird zu jedem Bild gespeichert
- **KEINE KI-Inferenz** - nur Rohdaten
- Daten werden in `data_collection/YYYYMMDD_HHMMSS/` gespeichert

### Ausgabe-Dateien:
```
data_collection/20231027_143022/
├── images/
│   ├── frame_000001.jpg
│   ├── frame_000002.jpg
│   └── ...
├── metadata.json          # GPS + Timestamp für jedes Bild
├── route.geojson         # Route als GeoJSON
└── summary.txt           # Session-Zusammenfassung
```

### Konfiguration
Bearbeiten Sie `config_collection.yaml`:
- `camera.resolution`: Bildauflösung (Standard: 1920x1080)
- `camera.fps`: Bildrate (Standard: 5)
- `collection.capture_interval`: Sekunden zwischen Aufnahmen (Standard: 2.0)
- `gps.port`: GPS-Gerät (Standard: /dev/ttyACM0)

### Nächste Schritte nach Datenerfassung:

1. **Daten auf Windows PC übertragen**:
   ```bash
   # Auf Windows PC (per SSH/SCP oder USB-Stick)
   scp -r jetson@192.168.1.x:/path/to/data_collection/20231027_143022 ./training_data/
   ```

2. **Bilder annotieren** mit Tools wie:
   - [LabelImg](https://github.com/HumanSignal/labelImg)
   - [CVAT](https://www.cvat.ai/)
   - [Roboflow](https://roboflow.com/)
   
   Klassen annotieren:
   - pothole (Schlagloch)
   - crack (Riss)
   - bump (Erhöhung/Buckel)
   - debris (Hindernisse)

3. **Modell auf Windows PC trainieren**:
   ```bash
   python training/train.py --data your_dataset.yaml --epochs 100
   ```

4. **Modell exportieren**:
   ```bash
   # ONNX Export
   python training/export_onnx.py --weights runs/train/exp/weights/best.pt
   
   # TensorRT Konvertierung (auf Jetson oder Windows mit TensorRT)
   python training/convert_tensorrt.py --onnx model.onnx --engine model.engine
   ```

5. **Modell auf Jetson übertragen**:
   ```bash
   scp model.engine jetson@192.168.1.x:/home/kwr/bike-surface-ai/edge/models/surface_detection.engine
   ```

---

## 2. Inferenz-Modus (Live Detection)

### Zweck
Fahrrad-Fahrt mit Echtzeit-Schadenerkennung aufzeichnen und Schäden auf Karte markieren.

### Voraussetzung
Trainiertes TensorRT-Modell muss vorhanden sein:
```
edge/models/surface_detection.engine
```

### Verwendung

```bash
cd /home/kwr/bike-surface-ai/edge
./start_inference.sh
```

### Was passiert:
- Kamera läuft mit 10 FPS
- **KI-Modell** erkennt Schäden in jedem Frame
- Bei Erkennung: GPS-Position + Bild + Schadentyp speichern
- Komplette Route wird aufgezeichnet
- GeoJSON für Karten-Visualisierung wird erstellt

### Ausgabe-Dateien:
```
inference_results/20231027_150045/
├── detections/
│   ├── detection_000001.jpg  # Bild mit Markierungen
│   ├── detection_000002.jpg
│   └── ...
├── detections.json           # Alle Erkennungen mit Details
├── detections.geojson        # Schäden als Punkte für Karte
├── route.geojson             # Komplette Route als Linie
└── summary.txt               # Session-Zusammenfassung
```

### Konfiguration
Bearbeiten Sie `config_inference.yaml`:
- `model.path`: Pfad zum TensorRT-Modell
- `model.confidence_threshold`: Konfidenz-Schwelle (Standard: 0.5)
- `camera.resolution`: Bildauflösung (Standard: 1280x720)
- `camera.fps`: Bildrate (Standard: 10)
- `inference.damage_classes`: Welche Klassen als Schäden gelten

### Ergebnisse visualisieren:

1. **Auf Karte anzeigen**:
   - Öffnen Sie `demo_viewer.html` im Browser
   - Laden Sie `detections.geojson` - zeigt Schäden als Punkte
   - Laden Sie `route.geojson` - zeigt komplette Route

2. **JSON-Daten analysieren**:
   ```python
   import json
   with open('detections.json') as f:
       data = json.load(f)
   print(f"Gefunden: {data['total_detections']} Schäden")
   ```

3. **Cloud-Upload** (wenn Cloud API läuft):
   ```bash
   curl -X POST http://your-cloud-api.com/upload \
        -H "Content-Type: application/json" \
        -d @detections.json
   ```

---

## Hardware Setup

### GPS-Modul (Ublox NEO-M8U)

1. **Anschluss**:
   - USB: Automatisch als `/dev/ttyACM0` erkannt
   - UART: GPIO-Pins am Jetson

2. **Testen**:
   ```bash
   # GPS-Gerät prüfen
   ls -l /dev/ttyACM*
   
   # GPS-Daten lesen
   sudo apt-get install gpsd gpsd-clients
   gpsmon /dev/ttyACM0
   ```

3. **GPS-Fix**:
   - Bei erstem Start: 1-5 Minuten warten
   - Freie Sicht zum Himmel erforderlich
   - Mindestens 4 Satelliten für 3D-Fix

### Kamera

1. **USB-Kamera**:
   - Einstecken und automatisch erkannt als `/dev/video0`
   
2. **CSI-Kamera** (Jetson Nano):
   ```python
   # In config anpassen:
   camera.device_id: 0  # Für CSI verwenden Sie GStreamer Pipeline
   ```

3. **Testen**:
   ```bash
   # Verfügbare Kameras anzeigen
   v4l2-ctl --list-devices
   
   # Kamera testen
   ffplay /dev/video0
   ```

---

## Tipps & Troubleshooting

### GPS funktioniert nicht
```bash
# Gerät prüfen
ls -l /dev/ttyACM0

# Berechtigungen setzen
sudo chmod 666 /dev/ttyACM0

# Oder User zur dialout-Gruppe hinzufügen
sudo usermod -a -G dialout $USER
# Dann neu anmelden
```

### Kamera funktioniert nicht
```bash
# V4L2-Utils installieren
sudo apt-get install v4l-utils

# Verfügbare Kameras anzeigen
v4l2-ctl --list-devices

# Camera-ID in config anpassen (z.B. device_id: 1)
```

### Mock GPS verwenden (für Tests ohne Hardware)
- System erkennt automatisch fehlendes GPS
- Simuliert Position um Berlin herum
- Für echte Aufnahmen NICHT verwenden!

### TensorRT-Modell lädt nicht
```bash
# Prüfen ob TensorRT installiert ist
python3 -c "import tensorrt; print(tensorrt.__version__)"

# Falls nicht: Jetpack SDK installieren
sudo apt-get install nvidia-jetpack

# Alternative: ONNX-Modell verwenden (langsamer)
# In config_inference.yaml: model.path auf .onnx ändern
```

### Speicherplatz
```bash
# Aktuellen Speicher prüfen
df -h

# Alte Daten löschen
rm -rf data_collection/old_session_*/
rm -rf inference_results/old_session_*/
```

---

## Performance-Tipps

### Jetson Maximale Leistung
```bash
# Jetson auf maximale Performance setzen
sudo nvpmodel -m 0
sudo jetson_clocks
```

### Kamera-Auflösung reduzieren
Für schnellere Verarbeitung in `config_inference.yaml`:
```yaml
camera:
  resolution: [640, 480]  # Statt 1280x720
  fps: 15
```

### Batch-Verarbeitung statt Echtzeit
Falls Echtzeit zu langsam ist:
1. Datenerfassungs-Modus verwenden
2. Daten auf PC übertragen
3. Batch-Inferenz auf PC durchführen

---

## Workflow-Übersicht

```
┌─────────────────────────────────────────────────────────────┐
│                    PHASE 1: DATENERFASSUNG                  │
│                     (Jetson Orin Nano)                      │
└─────────────────────────────────────────────────────────────┘
  1. Fahrt mit GPS + Kamera aufzeichnen
     → ./start_collection.sh
     → Output: data_collection/YYYYMMDD_HHMMSS/

┌─────────────────────────────────────────────────────────────┐
│                 PHASE 2: MODELL-TRAINING                    │
│                     (Windows PC)                            │
└─────────────────────────────────────────────────────────────┘
  2. Daten auf PC übertragen
  3. Bilder annotieren (LabelImg, CVAT)
  4. YOLOv8 trainieren
     → python training/train.py
  5. Modell exportieren
     → python training/export_onnx.py
     → python training/convert_tensorrt.py

┌─────────────────────────────────────────────────────────────┐
│              PHASE 3: PRODUKTIV-EINSATZ                     │
│                   (Jetson Orin Nano)                        │
└─────────────────────────────────────────────────────────────┘
  6. TensorRT-Modell auf Jetson übertragen
  7. Live-Erkennung starten
     → ./start_inference.sh
     → Output: inference_results/YYYYMMDD_HHMMSS/
  8. Ergebnisse auf Karte visualisieren
     → demo_viewer.html + detections.geojson
```

---

## Weitere Informationen

- **Hauptdokumentation**: `/README.md`
- **Setup-Anleitung**: `/SETUP.md`
- **Demo-Anleitung**: `/DEMO_ANLEITUNG.md`
- **Training-Skripte**: `/training/`
- **Cloud API**: `/cloud/`
