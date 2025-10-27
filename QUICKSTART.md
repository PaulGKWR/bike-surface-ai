# 🚀 QUICK START - Bike Surface AI

## In 5 Minuten zur ersten Schadens-Visualisierung

---

## 1️⃣ DATENSAMMLUNG (Optional - für neues Trainingsset)

### Desktop: "Bike AI - Datensammlung"
```
1. Doppelklick auf Icon
2. Browser öffnet sich automatisch
3. Klicke "Start Capture"
4. Fahre deine Route (GPS muss Fix haben!)
5. Klicke "Stop Capture"
```

**Ergebnis**: `edge/data_collection/YYYYMMDD_HHMMSS/images/`

---

## 2️⃣ INFERENCE MIT DEMO-MODUS

### Desktop: "Bike AI - Inference"
```
1. Doppelklick auf Icon
2. Warte auf GPS-Fix (~30 Sek)
3. "GPS-Fix erreicht!" → Fahre Route
4. Strg+C zum Beenden
```

**Ergebnis**: `edge/inference_results/YYYYMMDD_HHMMSS/detections.json`

**Info**: DEMO-Modus ist aktiv! Simuliert Schäden für Tests.

---

## 3️⃣ WEB-VIEWER ERSTELLEN

### Desktop: "Bike AI - Workflow"
```
1. Doppelklick auf Icon
2. Wähle Session aus Liste (z.B. [1])
3. Enter drücken
4. Warte auf "EXPORT ERFOLGREICH"
```

**Ergebnis**: `edge/viewer_data_YYYYMMDD_HHMMSS/`

---

## 4️⃣ VISUALISIERUNG ÖFFNEN

### Auf Jetson:
```bash
cd ~/bike-surface-ai/edge/viewer_data_20251027_135704/
firefox viewer.html
```

### Auf Windows-PC:
```
1. Kopiere Ordner "viewer_data_XXX" per USB auf Windows
2. Doppelklick auf viewer.html
3. Fertig!
```

---

## 🎨 WAS DU SIEHST

### Interaktive Karte
- 📍 Marker für jeden Schaden
- 🔴 Farben nach Schweregrad
- 🔢 Zahl = Anzahl Bilder pro Schaden

### Popup beim Klick
- 🖼️ Bild-Galerie (bei mehreren Bildern)
- ⬅️➡️ Pfeiltasten zum Durchklicken
- 📊 Details: Typ, Confidence, GPS, Zeit

### Statistik (rechts oben)
- Gesamt-Schäden
- Gesamt-Bilder
- Aufschlüsselung nach Typ

---

## 🔥 TEST MIT DEMO-DATEN

Falls du direkt testen willst ohne eigene Inference:

```bash
cd ~/bike-surface-ai/edge

# Verwende existierende Test-Session
./workflow_complete.sh
# Wähle: [1] 20251027_135704

# Öffne Viewer
firefox viewer_data_20251027_135704/viewer.html
```

**Demo-Inhalt**:
- 3 Schadens-Gruppen
- 4 Bilder total
- 1 Gruppe mit 2 Bildern (bump)

---

## 📱 MOBILE NUTZUNG

### Hotspot aktivieren:
```
Desktop: "Bike AI - Network" → [1] Hotspot
```

### Mit Smartphone verbinden:
```
SSID: BikeAI-Jetson
Passwort: bikeai2025
```

### Browser öffnen:
```
http://10.42.0.1:5000
```

Jetzt kannst du die Datensammlung vom Smartphone steuern!

---

## ⚡ HÄUFIGE PROBLEME

### GPS bekommt keinen Fix
```bash
# Nach draußen gehen! Indoor kein GPS
# Warten: 1-2 Minuten
# Prüfen: python3 quick_gps_check.py
```

### Kamera nicht gefunden
```bash
# USB neu einstecken
# Terminal: ls /dev/video*
# Sollte /dev/video0 zeigen
```

### Web-UI lädt nicht
```bash
# Prozess beenden:
killall python3

# Neu starten:
./start_webui.sh
```

### Viewer zeigt keine Bilder
```
# Prüfe Ordnerstruktur:
viewer_data/
├── viewer.html  ← HIER öffnen!
├── damages_grouped.geojson
└── images/

# Nicht aus parent-Ordner öffnen!
```

---

## 🎯 NEXT STEPS

### Für Produktion:
1. Sammle 500+ Bilder verschiedener Schäden
2. Annotiere auf Windows (LabelImg)
3. Trainiere YOLOv8 Modell
4. Exportiere TensorRT Engine
5. Kopiere auf Jetson
6. Deaktiviere DEMO_MODE

### Für Azure:
1. Erstelle Azure Storage Account
2. Kopiere Connection String
3. Füge in `config_inference.yaml` ein
4. Teste Upload

### Für GitHub Pages:
1. Erstelle GitHub Repository
2. Aktiviere Pages
3. Upload docs/ Ordner
4. Öffentliche URL teilen

---

## 📖 MEHR INFOS

- **Vollständige Anleitung**: `edge/ANLEITUNG.md`
- **Aktueller Status**: `edge/STATUS.md`
- **Projekt-README**: `README.md`

---

## 💡 TIPPS

### Beste Ergebnisse:
- ☀️ Tageslicht (bessere Bilder)
- 🛣️ Verschiedene Straßentypen
- 🐌 Langsame Geschwindigkeit (10-20 km/h)
- 📍 Outdoor für GPS-Fix

### Effizienter Workflow:
1. Morgens: Daten sammeln (1-2h)
2. Mittags: Inference laufen lassen
3. Nachmittags: Viewer erstellen & analysieren

### Daten-Management:
```bash
# Alte Sessions löschen:
rm -rf edge/data_collection/20251027_*/

# Viewer-Daten sichern:
zip -r backup.zip viewer_data_*/

# Plattenplatz prüfen:
du -sh edge/*/
```

---

**Viel Erfolg! 🚴💨**
