#!/usr/bin/env python3
"""
Damage Grouping - Gruppiert nahe beieinander liegende Schäden
Mehrere Bilder vom gleichen Schaden werden zusammengefasst
"""

import json
import math
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Tuple

def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Berechne Distanz zwischen zwei GPS-Punkten in Metern (Haversine)
    """
    R = 6371000  # Erdradius in Metern
    
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    
    a = math.sin(delta_phi/2)**2 + \
        math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    
    return R * c

class DamageGrouper:
    """Gruppiert Schäden nach GPS-Nähe"""
    
    def __init__(self, max_distance: float = 1.0):
        """
        Args:
            max_distance: Maximale Distanz in Metern für Gruppierung (default: 1m)
        """
        self.max_distance = max_distance
        self.groups = []
    
    def group_detections(self, detections: List[Dict]) -> List[Dict]:
        """
        Gruppiere Detections die nah beieinander liegen
        
        Args:
            detections: Liste von Detection-Objekten mit GPS-Daten
            
        Returns:
            Liste von Gruppen, jede Gruppe enthält mehrere Detections
        """
        if not detections:
            return []
        
        # Sortiere nach Zeitstempel
        sorted_detections = sorted(
            detections, 
            key=lambda d: d.get('timestamp', '')
        )
        
        groups = []
        
        for detection in sorted_detections:
            gps = detection.get('gps', {})
            
            if not gps.get('latitude') or not gps.get('longitude'):
                continue
            
            lat = gps['latitude']
            lon = gps['longitude']
            damage_type = detection.get('detection', {}).get('class', 'unknown')
            
            # Finde passende Gruppe
            found_group = False
            
            for group in groups:
                # Prüfe ob Schaden zur Gruppe passt
                group_center = group['center']
                distance = calculate_distance(
                    lat, lon,
                    group_center['lat'], group_center['lon']
                )
                
                # Gleicher Schadenstyp UND innerhalb max_distance?
                if (distance <= self.max_distance and 
                    group['damage_type'] == damage_type):
                    
                    # Füge zu Gruppe hinzu
                    group['detections'].append(detection)
                    
                    # Aktualisiere Zentrum (Durchschnitt)
                    self._update_group_center(group)
                    
                    found_group = True
                    break
            
            if not found_group:
                # Neue Gruppe erstellen
                groups.append({
                    'id': len(groups) + 1,
                    'damage_type': damage_type,
                    'center': {
                        'lat': lat,
                        'lon': lon
                    },
                    'detections': [detection],
                    'created': detection.get('timestamp')
                })
        
        # Sortiere Detections in jeder Gruppe nach Zeitstempel
        for group in groups:
            group['detections'] = sorted(
                group['detections'],
                key=lambda d: d.get('timestamp', '')
            )
            
            # Füge Statistiken hinzu
            group['image_count'] = len(group['detections'])
            group['avg_confidence'] = sum(
                d.get('detection', {}).get('confidence', 0) 
                for d in group['detections']
            ) / len(group['detections'])
            
            # Beste Confidence finden
            group['best_confidence'] = max(
                d.get('detection', {}).get('confidence', 0) 
                for d in group['detections']
            )
            
            # Zeitspanne
            if group['detections']:
                first = group['detections'][0].get('timestamp', '')
                last = group['detections'][-1].get('timestamp', '')
                group['first_seen'] = first
                group['last_seen'] = last
        
        return groups
    
    def _update_group_center(self, group: Dict):
        """Aktualisiere Gruppen-Zentrum als Durchschnitt aller Punkte"""
        detections = group['detections']
        
        total_lat = sum(d['gps']['latitude'] for d in detections if d.get('gps'))
        total_lon = sum(d['gps']['longitude'] for d in detections if d.get('gps'))
        count = len([d for d in detections if d.get('gps')])
        
        if count > 0:
            group['center']['lat'] = total_lat / count
            group['center']['lon'] = total_lon / count
    
    def export_grouped_geojson(self, groups: List[Dict], output_path: str):
        """
        Exportiere gruppierte Schäden als GeoJSON
        
        Args:
            groups: Liste von Schadens-Gruppen
            output_path: Pfad zur Ausgabe-Datei
        """
        features = []
        
        for group in groups:
            # Sammle alle Bild-URLs
            images = []
            for det in group['detections']:
                img_info = {
                    'url': det.get('image_url', ''),
                    'filename': det.get('image', ''),
                    'timestamp': det.get('timestamp', ''),
                    'confidence': det.get('detection', {}).get('confidence', 0)
                }
                images.append(img_info)
            
            feature = {
                'type': 'Feature',
                'geometry': {
                    'type': 'Point',
                    'coordinates': [
                        group['center']['lon'],
                        group['center']['lat']
                    ]
                },
                'properties': {
                    'id': group['id'],
                    'damage_type': group['damage_type'],
                    'image_count': group['image_count'],
                    'images': images,  # Alle Bilder des Schadens
                    'avg_confidence': round(group['avg_confidence'], 3),
                    'best_confidence': round(group['best_confidence'], 3),
                    'first_seen': group['first_seen'],
                    'last_seen': group['last_seen'],
                    'severity': self._calculate_severity(group)
                }
            }
            features.append(feature)
        
        geojson = {
            'type': 'FeatureCollection',
            'metadata': {
                'generated': datetime.now().isoformat(),
                'total_groups': len(groups),
                'total_images': sum(g['image_count'] for g in groups),
                'grouping_distance_m': self.max_distance
            },
            'features': features
        }
        
        with open(output_path, 'w') as f:
            json.dump(geojson, f, indent=2)
        
        print(f"✅ GeoJSON exportiert: {output_path}")
        print(f"   Gruppen: {len(groups)}")
        print(f"   Gesamt-Bilder: {sum(g['image_count'] for g in groups)}")
    
    def _calculate_severity(self, group: Dict) -> str:
        """Berechne Schweregrad basierend auf Typ und Confidence"""
        damage_type = group['damage_type'].lower()
        confidence = group['best_confidence']
        
        # Mehr Bilder = höhere Sicherheit = höherer Schweregrad
        image_factor = min(group['image_count'] / 3, 1.0)  # Max bei 3+ Bildern
        
        if damage_type == 'pothole':
            if confidence > 0.8 or image_factor > 0.7:
                return 'high'
            elif confidence > 0.6:
                return 'medium'
            else:
                return 'low'
        
        elif damage_type == 'crack':
            if confidence > 0.75 and image_factor > 0.5:
                return 'medium'
            else:
                return 'low'
        
        else:
            return 'low'


def process_session(session_dir: str, max_distance: float = 1.0, output_dir: str = None):
    """
    Verarbeite eine Inference-Session und gruppiere Schäden
    
    Args:
        session_dir: Pfad zum Session-Verzeichnis
        max_distance: Maximale Distanz für Gruppierung (Meter)
        output_dir: Ausgabe-Verzeichnis (optional)
    """
    session_path = Path(session_dir)
    
    if not session_path.exists():
        print(f"❌ Session nicht gefunden: {session_dir}")
        return
    
    print(f"📂 Verarbeite Session: {session_path.name}")
    print(f"📏 Gruppierungs-Distanz: {max_distance}m\n")
    
    # Lade Detections
    detections_file = session_path / "detections.json"
    if not detections_file.exists():
        print(f"❌ Keine detections.json gefunden")
        return
    
    with open(detections_file) as f:
        data = json.load(f)
    
    detections = data.get('detections', [])
    print(f"📊 Gefunden: {len(detections)} Detections")
    
    # Gruppiere
    grouper = DamageGrouper(max_distance=max_distance)
    groups = grouper.group_detections(detections)
    
    print(f"🔗 Gruppiert in: {groups} Schaden-Gruppen\n")
    
    # Zeige Gruppen-Details
    for group in groups:
        print(f"Gruppe #{group['id']}: {group['damage_type']}")
        print(f"  📸 Bilder: {group['image_count']}")
        print(f"  🎯 Confidence: {group['avg_confidence']:.2f} (best: {group['best_confidence']:.2f})")
        print(f"  📍 Position: {group['center']['lat']:.6f}, {group['center']['lon']:.6f}")
        print(f"  ⚠️  Schweregrad: {group.get('severity', 'unknown')}")
        print()
    
    # Exportiere
    if output_dir is None:
        output_dir = session_path
    else:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
    
    output_file = output_dir / "damages_grouped.geojson"
    grouper.export_grouped_geojson(groups, str(output_file))
    
    print(f"\n✅ Fertig! Ausgabe: {output_file}")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python3 group_damages.py <session_dir> [max_distance_m]")
        print("\nBeispiel:")
        print("  python3 group_damages.py inference_results/20251027_134729")
        print("  python3 group_damages.py inference_results/20251027_134729 1.5")
        sys.exit(1)
    
    session_dir = sys.argv[1]
    max_distance = float(sys.argv[2]) if len(sys.argv) > 2 else 1.0
    
    process_session(session_dir, max_distance)
