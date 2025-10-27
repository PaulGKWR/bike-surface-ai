# Bike Surface AI - System Architektur

## Übersicht

Das Bike Surface AI System ist eine End-to-End-Lösung zur automatischen Erkennung und Klassifizierung von Straßenoberflächen und Schäden während Fahrradfahrten.

## System-Komponenten

### 1. Hardware Setup
```
┌─────────────────────────────────────────────┐
│          Nvidia Jetson Nano                 │
│                                             │
│  ┌─────────────┐      ┌─────────────────┐  │
│  │   Camera    │      │   GPS Modul     │  │
│  │ Logitech    │      │  Navilock       │  │
│  │   C920      │      │   62756         │  │
│  └──────┬──────┘      └────────┬────────┘  │
│         │                      │            │
│         └──────────┬───────────┘            │
│                    │                        │
│         ┌──────────▼──────────┐             │
│         │   Edge Software     │             │
│         └─────────────────────┘             │
└─────────────────────────────────────────────┘
```

### 2. Software-Architektur

```
┌──────────────────────────────────────────────────────────┐
│                     Web Interface                        │
│  ┌────────────────────┐    ┌─────────────────────────┐  │
│  │  Training Data UI  │    │  Live Inference UI      │  │
│  │  - Camera Preview  │    │  - Demo Mode            │  │
│  │  - Start/Stop      │    │  - Real-time Map        │  │
│  │  - Session List    │    │  - Colored Routes       │  │
│  └──────────┬─────────┘    │  - Damage Markers       │  │
│             │               └───────────┬─────────────┘  │
└─────────────┼─────────────────────────┬─┼────────────────┘
              │                         │ │
         ┌────▼─────────────────────────▼─▼────┐
         │         Flask Web Server             │
         │  - Template Rendering                │
         │  - REST APIs                         │
         │  - Process Management                │
         └────┬──────────────────┬──────────────┘
              │                  │
    ┌─────────▼──────────┐  ┌───▼────────────────┐
    │ simple_capture.py  │  │ auto_live_system.py│
    │ - Camera Control   │  │ - AI Inference     │
    │ - GPS Logging      │  │ - Real-time Class. │
    │ - 2s Intervals     │  │ - Damage Detection │
    └──────────┬─────────┘  └────────┬───────────┘
               │                     │
         ┌─────▼─────────────────────▼─────┐
         │       Core Modules               │
         │  ┌────────────┐  ┌────────────┐ │
         │  │ gps_module │  │ ai_inference│ │
         │  └────────────┘  └────────────┘ │
         └──────────────────────────────────┘
```

## Komponenten-Details

### Edge Layer (`/edge`)

#### **web_ui.py** - Zentrale Web-Anwendung
- Flask-basierter HTTP-Server
- Serviert beide UI-Modi: Training & Live
- REST API Endpunkte:
  - `/api/status` - Training-Session Status
  - `/api/live/status` - Live-Inference Status
  - `/api/live/start` - Live-System starten
  - `/api/live/stop` - Live-System stoppen
  - `/api/gps/current` - Aktuelle GPS-Position
  - `/api/live/demo` - Demo-Modus toggle

#### **simple_capture.py** - Training-Datensammlung
- Erfasst Bilder alle 2 Sekunden
- GPS-Koordinaten pro Bild
- Speichert in `data_collection/TIMESTAMP/`
- Generiert GeoJSON-Route
- Features:
  - Funktioniert auch ohne GPS-Fix
  - Automatische Distanzberechnung
  - Zwischenspeicherung alle 10 Bilder

#### **auto_live_system.py** - Live-Inferenz
- Echtzeit-Klassifizierung während Fahrt
- Oberflächentypen: asphalt_good, asphalt_poor, cobblestone, etc.
- Schadenserkennung: pothole, crack, bump, etc.
- Schreibt `live_state.json` für Web UI
- Speichert Session in `live_sessions/TIMESTAMP/`

#### **gps_module.py** - GPS-Integration
- Navilock 62756 Unterstützung
- NMEA-Protokoll Parser
- GPS-Fix Erkennung
- Liefert: lat, lon, altitude, satellites

#### **ai_inference.py** - KI-Modul
- YOLOv8-basierte Klassifizierung
- Surface Detection Model
- Damage Detection Model
- TensorRT-Optimierung (optional)

### Web Templates (`/edge/templates`)

#### **index.html** - Training Data UI
- Live-Kamera-Preview
- Start/Stop Buttons
- Session-Liste mit Thumbnails
- Statistiken (Bilder, Distanz, Zeit)
- Navbar zur Live-Seite

#### **live_inference.html** - Live Inference UI
- Leaflet.js Karte
- Demo-Mode Toggle
- Start/Stop Controls
- Farbcodierte Route nach Oberflächentyp:
  - Grün: Guter Asphalt
  - Gelb: Mittelmäßiger Asphalt
  - Rot: Schlechter Asphalt
  - Blau: Kopfsteinpflaster
  - Orange: Kies
- Schaden-Marker mit Schweregrad-Farben
- Legende mit Oberflächentypen
- Echtzeit-Statistiken

## Datenfluss

### Training-Modus
```
Camera → simple_capture.py → Disk Storage
  ↓                              ↓
GPS → simple_capture.py → metadata.json + route.geojson
       ↓
  web_ui.py (Status API) → Browser UI
```

### Live-Modus
```
Camera → auto_live_system.py → AI Inference
  ↓                               ↓
GPS → auto_live_system.py → Classification + Damage Detection
       ↓                           ↓
  live_state.json ← Continuous Updates
       ↓
  web_ui.py (Live API) → Browser UI → Leaflet Map
```

## Konfiguration

### GPS Config (`config*.yaml`)
```yaml
gps:
  port: "/dev/ttyACM0"
  baudrate: 9600
  timeout: 1.0
```

### Kamera Config
```yaml
camera:
  device_id: 0
  resolution: [1920, 1080]
  fps: 10
```

### Collection Config
```yaml
collection:
  capture_interval: 2.0  # Sekunden
  image_quality: 95      # JPEG Quality
```

## Deployment

### Voraussetzungen
- Nvidia Jetson Nano (4GB empfohlen)
- Python 3.8+
- CUDA 10.2+
- USB-Kamera (Logitech C920 oder kompatibel)
- GPS-Modul mit USB (Navilock 62756 oder kompatibel)

### Installation
```bash
cd edge
pip3 install -r requirements.txt
```

### Start Web UI
```bash
python3 web_ui.py
```

Öffne Browser: `http://<jetson-ip>:5000`

## API-Referenz

### GET /api/status
Training-Session Status
```json
{
  "is_running": true,
  "session_id": "20251027_140530",
  "image_count": 127,
  "duration": 254
}
```

### GET /api/live/status
Live-Inference Status
```json
{
  "is_running": true,
  "session_id": "20251027_170742",
  "stats": {
    "total_images": 95,
    "total_distance_km": 3.45,
    "avg_speed_kmh": 18.3
  },
  "current_position": [48.2904, 11.0434],
  "route_points": [...],
  "recent_damages": [...]
}
```

### POST /api/live/start
Startet auto_live_system.py
```json
{
  "status": "started",
  "pid": 12345
}
```

### GET /api/gps/current
Aktuelle GPS-Position
```json
{
  "latitude": 48.2904,
  "longitude": 11.0434,
  "fix": true,
  "satellites": 8
}
```

## Dateisystem-Struktur

```
bike-surface-ai/
├── edge/
│   ├── web_ui.py              # Haupt-Web-Server
│   ├── simple_capture.py      # Training Data Collection
│   ├── auto_live_system.py    # Live Inference System
│   ├── gps_module.py          # GPS-Integration
│   ├── ai_inference.py        # KI-Klassifizierung
│   ├── requirements.txt       # Python Dependencies
│   ├── config*.yaml           # Konfigurationsdateien
│   ├── templates/             # Web Templates
│   │   ├── index.html         # Training UI
│   │   └── live_inference.html # Live UI
│   ├── data_collection/       # Training Sessions (gitignored)
│   │   └── TIMESTAMP/
│   │       ├── images/
│   │       ├── metadata.json
│   │       └── route.geojson
│   └── live_sessions/         # Live Sessions (gitignored)
│       └── TIMESTAMP/
│           ├── images/
│           ├── damages/
│           ├── session.json
│           └── route.geojson
├── training/                  # ML Training Scripts
│   ├── train.py
│   └── yolov8_config.yaml
└── cloud/                     # Cloud Backend (optional)
    ├── api/
    ├── db/
    └── web/
```

## Entwicklung

### Hinzufügen neuer Oberflächentypen
1. Update `SURFACE_COLORS` in `live_inference.html`
2. Update `SURFACE_NAMES` in `live_inference.html`
3. Trainiere Modell neu mit neuen Labels

### Debugging
- Web UI Logs: `/tmp/webui.log`
- Browser Console: Öffne DevTools (F12)
- GPS-Test: `python3 quick_gps_check.py`
- Kamera-Test: `python3 test_hardware.py`

## Performance

- Training Data Capture: 0.5 FPS (alle 2s)
- Live Inference: 1-2 FPS (abhängig von Hardware)
- GPS Update Rate: 1 Hz
- Web UI Refresh: 2s Intervall

## Lizenz

Siehe LICENSE Datei
