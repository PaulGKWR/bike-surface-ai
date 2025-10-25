# 🚴 Demo-Anleitung: Route Ried → Baindlkirch

## Schnellstart

### 1. Demo-Daten generieren
```powershell
python demo.py
```

Dies erstellt eine simulierte Fahrradroute von **Ried nach Baindlkirch** mit realistischen Problemerkennungen (Schlaglöcher, Risse, Flickstellen, etc.).

### 2. Lokalen Server starten
```powershell
python -m http.server 8080
```

Der Server muss laufen, um CORS-Probleme beim Laden der GeoJSON-Datei zu vermeiden.

### 3. Demo öffnen
Öffne im Browser:
```
http://localhost:8080/demo_viewer_route.html
```

Die Route wird **automatisch geladen**!

---

## Features der Demo

### ✅ Routendarstellung
- **Grüne Linie**: Zeigt die gefahrene Strecke von Ried nach Baindlkirch
- **Durchgehender Pfad**: Folgt dem Radweg zwischen den Orten
- Klick auf die Linie zeigt Routeninformationen

### ⚠️ Problemerkennung
- **Farbige Marker**: Zeigen erkannte Probleme auf der Strecke
  - 🔴 **Rot**: Schlaglöcher
  - 🟠 **Orange**: Risse
  - 🟡 **Gelb**: Flickstellen
  - 🟢 **Grün**: Bodenwellen
  - 🟤 **Braun**: Schotter

### 🎯 Marker-Features
- **Pulsierender Effekt**: Probleme sind durch Animation deutlich sichtbar
- **Hover-Info**: Zeigt beim Überfahren mit der Maus Typ und Konfidenz
- **Detaillierte Popup-Karte**: Klick auf Marker zeigt:
  - 🎯 Erkennungs-Konfidenz
  - 🕐 Uhrzeit der Erkennung
  - ⚡ Geschwindigkeit zum Zeitpunkt
  - 📍 Exakte GPS-Koordinaten
  - 📷 Bild-ID (simuliert)

### 📊 Statistik-Box
Zeigt oben rechts:
- Gesamte Streckenlänge
- Anzahl erkannter Probleme
- Aufschlüsselung nach Problemtyp

---

## Route anpassen

Willst du eine andere Route testen? Bearbeite `demo.py`:

```python
def generate_route_waypoints():
    """Eigene Wegpunkte definieren"""
    return [
        (48.2905, 11.0434),   # Start
        (48.2920, 11.0450),   # Wegpunkt 1
        # ... weitere Wegpunkte
        (48.3065, 11.0625),   # Ziel
    ]
```

---

## Echte Daten verwenden

Um das System mit **echten Hardware-Daten** zu nutzen:

1. **Edge-System einrichten** (siehe `SETUP.md`)
   - Jetson Orin Nano mit Kamera
   - GPS-Modul (Ublox NEO-M8U)
   - YOLOv8-Modell trainieren

2. **Cloud-Backend starten**
   ```bash
   docker-compose up
   ```

3. **Edge-System starten**
   ```bash
   cd edge
   python main.py
   ```

4. **Web-Interface öffnen**
   ```
   http://localhost/
   ```

---

## Tipps

### Problem: Seite lädt nicht
- ✅ Stelle sicher, dass der Server läuft: `python -m http.server 8080`
- ✅ Öffne die Seite über `http://localhost:8080/...`, nicht direkt via Datei-Explorer

### Problem: Keine Route sichtbar
- ✅ Prüfe, ob `demo_ride.geojson` existiert
- ✅ Führe `python demo.py` erneut aus
- ✅ Öffne die Browser-Konsole (F12) für Fehlerdetails

### Eigene GeoJSON-Datei laden
Klicke auf **"📂 GeoJSON laden"** und wähle eine eigene `.geojson`-Datei

---

## Nächste Schritte

1. **Modell trainieren**: Siehe `training/train.py`
2. **Hardware aufbauen**: Siehe `SETUP.md`
3. **System testen**: Siehe `test_system.py`
4. **Cloud deployen**: Docker Compose in `docker-compose.yml`

---

**Viel Erfolg mit deinem Bike Surface AI Projekt! 🚴‍♂️🛣️**
