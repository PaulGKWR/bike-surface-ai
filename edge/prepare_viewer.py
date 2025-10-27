#!/usr/bin/env python3
"""
Prepare Web Viewer - Exportiert Inference-Daten für die Web-App
Kopiert Bilder und GeoJSON in einen Ordner der direkt mit viewer.html genutzt werden kann
"""

import sys
import shutil
import json
from pathlib import Path
from datetime import datetime

def prepare_viewer_data(session_dir: str, output_dir: str = "viewer_data"):
    """
    Bereite Daten für Web-Viewer vor
    
    Args:
        session_dir: Pfad zum Inference-Session-Verzeichnis
        output_dir: Ziel-Verzeichnis für Web-Viewer
    """
    session_path = Path(session_dir)
    output_path = Path(output_dir)
    
    if not session_path.exists():
        print(f"❌ Session nicht gefunden: {session_dir}")
        return False
    
    print(f"📦 Bereite Viewer-Daten vor...")
    print(f"   Quelle: {session_path}")
    print(f"   Ziel: {output_path}\n")
    
    # Erstelle Output-Verzeichnis
    output_path.mkdir(parents=True, exist_ok=True)
    images_output = output_path / "images"
    images_output.mkdir(exist_ok=True)
    
    # 1. Prüfe ob grouped GeoJSON existiert
    grouped_geojson = session_path / "damages_grouped.geojson"
    
    if not grouped_geojson.exists():
        print("⚠️  damages_grouped.geojson nicht gefunden")
        print("   Führe Gruppierung aus...\n")
        
        # Führe Gruppierung aus
        import subprocess
        result = subprocess.run(
            ['python3', 'group_damages.py', str(session_path)],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            print(f"❌ Gruppierung fehlgeschlagen: {result.stderr}")
            return False
        
        print(result.stdout)
    
    # 2. Kopiere GeoJSON
    print("📄 Kopiere GeoJSON...")
    shutil.copy(grouped_geojson, output_path / "damages_grouped.geojson")
    print(f"   ✓ {grouped_geojson.name}")
    
    # 3. Lade GeoJSON um Bild-Liste zu bekommen
    with open(grouped_geojson) as f:
        geojson = json.load(f)
    
    # 4. Sammle alle benötigten Bilder
    images_to_copy = set()
    for feature in geojson['features']:
        for img in feature['properties'].get('images', []):
            filename = img.get('filename', '')
            if filename:
                images_to_copy.add(filename)
    
    # 5. Kopiere Bilder
    print(f"\n📸 Kopiere {len(images_to_copy)} Bilder...")
    images_source = session_path / "images"
    
    if not images_source.exists():
        print(f"❌ Bilder-Verzeichnis nicht gefunden: {images_source}")
        return False
    
    copied = 0
    missing = 0
    
    for img_filename in images_to_copy:
        src = images_source / img_filename
        dst = images_output / img_filename
        
        if src.exists():
            shutil.copy(src, dst)
            copied += 1
        else:
            print(f"   ⚠️  Bild nicht gefunden: {img_filename}")
            missing += 1
    
    print(f"   ✓ {copied} Bilder kopiert")
    if missing > 0:
        print(f"   ⚠️  {missing} Bilder fehlen")
    
    # 6. Kopiere viewer.html wenn nicht vorhanden
    viewer_html = output_path / "viewer.html"
    if not viewer_html.exists():
        source_viewer = Path(__file__).parent.parent / "viewer.html"
        if source_viewer.exists():
            print(f"\n📄 Kopiere viewer.html...")
            shutil.copy(source_viewer, viewer_html)
            print(f"   ✓ viewer.html")
    
    # 7. Erstelle README
    readme_path = output_path / "README.txt"
    with open(readme_path, 'w') as f:
        f.write("=== Bike Surface AI - Web Viewer ===\n\n")
        f.write(f"Generiert: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Session: {session_path.name}\n\n")
        f.write("Anleitung:\n")
        f.write("1. Öffne 'viewer.html' in einem Browser\n")
        f.write("2. Die Karte wird automatisch geladen\n")
        f.write("3. Klicke auf Marker um Details + Bilder zu sehen\n")
        f.write("4. Nutze Pfeiltasten oder Buttons zum Durchklicken\n\n")
        f.write(f"Statistik:\n")
        f.write(f"- Schadens-Gruppen: {geojson['metadata']['total_groups']}\n")
        f.write(f"- Gesamt-Bilder: {geojson['metadata']['total_images']}\n")
        f.write(f"- Gruppierungs-Distanz: {geojson['metadata']['grouping_distance_m']}m\n")
    
    # 8. Zusammenfassung
    print(f"\n" + "="*60)
    print("✅ EXPORT ERFOLGREICH")
    print("="*60)
    print(f"Output-Verzeichnis: {output_path.absolute()}")
    print(f"\nInhalt:")
    print(f"  📄 damages_grouped.geojson")
    print(f"  📄 viewer.html")
    print(f"  📁 images/ ({copied} Dateien)")
    print(f"  📄 README.txt")
    print(f"\n🌐 ZUM ÖFFNEN:")
    print(f"  Doppelklick auf: {viewer_html.absolute()}")
    print(f"\nODER auf Windows-PC:")
    print(f"  1. Kopiere Ordner '{output_path.name}' auf Windows")
    print(f"  2. Öffne viewer.html im Browser")
    print("="*60)
    
    return True


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Bereite Inference-Daten für Web-Viewer vor'
    )
    parser.add_argument(
        'session_dir',
        help='Pfad zum Inference-Session-Verzeichnis'
    )
    parser.add_argument(
        '-o', '--output',
        default='viewer_data',
        help='Output-Verzeichnis (default: viewer_data)'
    )
    
    args = parser.parse_args()
    
    success = prepare_viewer_data(args.session_dir, args.output)
    sys.exit(0 if success else 1)
