#!/usr/bin/env python3
"""
GitHub Pages Auto-Update
=========================
Generiert GeoJSON aus Session-Daten und committed automatisch zu GitHub Pages

Features:
- Strecken als LineString (farbcodiert nach Oberfläche)
- Schäden als Marker mit Bildern
- Gruppierung naher Schäden
- Automatischer Git Commit & Push
"""

import json
import yaml
import subprocess
from pathlib import Path
from typing import List, Dict
from datetime import datetime
import shutil
from collections import defaultdict

# Geopy für Distanzberechnung
try:
    from geopy.distance import geodesic
except ImportError:
    print("⚠️  geopy nicht installiert: pip install geopy")
    geodesic = None


class GitHubPagesUpdater:
    """GitHub Pages Updater"""
    
    def __init__(self, config_path="config_auto_live.yaml"):
        with open(config_path) as f:
            self.config = yaml.safe_load(f)
        
        self.gh_config = self.config['github']
        self.repo_path = Path(self.gh_config['repo_path'])
        self.data_dir = self.repo_path / self.gh_config['geojson']['output_dir']
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self.images_dir = self.repo_path / "docs" / "images"
        self.images_dir.mkdir(parents=True, exist_ok=True)
    
    def process_session(self, session_dir: Path):
        """Process single session"""
        print(f"\n📦 Verarbeite Session: {session_dir.name}")
        
        # Load session data
        route_file = session_dir / "route.geojson"
        surfaces_file = session_dir / "surfaces.json"
        damages_file = session_dir / "damages.json"
        
        if not all([f.exists() for f in [route_file, surfaces_file, damages_file]]):
            print(f"⚠️  Unvollständige Session - überspringe")
            return False
        
        with open(route_file) as f:
            route = json.load(f)
        
        with open(surfaces_file) as f:
            surfaces = json.load(f)
        
        with open(damages_file) as f:
            damages = json.load(f)
        
        print(f"  📍 Route: {len(route['features'][0]['geometry']['coordinates'])} Punkte")
        print(f"  🛣️  Oberflächen: {len(surfaces)}")
        print(f"  ⚠️  Schäden: {len(damages)}")
        
        # Generate GeoJSON files
        self.generate_route_geojson(session_dir.name, route, surfaces)
        self.generate_damages_geojson(session_dir.name, damages)
        
        # Copy damage images
        self.copy_damage_images(session_dir, damages)
        
        return True
    
    def generate_route_geojson(self, session_id, route, surfaces):
        """Generate route GeoJSON with surface segments"""
        features = []
        
        if not self.gh_config['geojson'].get('route_segments', True):
            # Simple full route
            features.append({
                'type': 'Feature',
                'geometry': route['features'][0]['geometry'],
                'properties': {
                    'session_id': session_id,
                    'type': 'route'
                }
            })
        else:
            # Segmented by surface type
            segments = self.segment_by_surface(route['features'][0]['geometry']['coordinates'], surfaces)
            
            for i, segment in enumerate(segments):
                features.append({
                    'type': 'Feature',
                    'geometry': {
                        'type': 'LineString',
                        'coordinates': segment['coordinates']
                    },
                    'properties': {
                        'session_id': session_id,
                        'segment_id': i,
                        'surface_type': segment['surface_type'],
                        'confidence': segment.get('confidence', 0.0),
                        'color': self.get_surface_color(segment['surface_type'])
                    }
                })
        
        # Save
        output_file = self.data_dir / f"route_{session_id}.geojson"
        geojson = {
            'type': 'FeatureCollection',
            'metadata': {
                'session_id': session_id,
                'generated': datetime.now().isoformat(),
                'segments': len(features)
            },
            'features': features
        }
        
        with open(output_file, 'w') as f:
            json.dump(geojson, f, indent=2)
        
        print(f"  ✓ Route GeoJSON: {output_file}")
        return output_file
    
    def segment_by_surface(self, coordinates, surfaces):
        """Segment route by surface type changes"""
        if not surfaces:
            return [{
                'coordinates': coordinates,
                'surface_type': 'unknown',
                'confidence': 0.0
            }]
        
        segments = []
        current_segment = {
            'coordinates': [],
            'surface_type': surfaces[0]['surface_type'],
            'confidence': surfaces[0]['confidence']
        }
        
        surface_idx = 0
        
        for coord in coordinates:
            lon, lat = coord
            
            # Check if we passed to next surface detection
            if surface_idx < len(surfaces) - 1:
                next_surface = surfaces[surface_idx + 1]
                # Simple distance check
                if geodesic and geodesic((lat, lon), 
                                        (next_surface['latitude'], next_surface['longitude'])).meters < 5:
                    # Save current segment
                    if current_segment['coordinates']:
                        segments.append(current_segment)
                    
                    # Start new segment
                    surface_idx += 1
                    current_segment = {
                        'coordinates': [coord],
                        'surface_type': next_surface['surface_type'],
                        'confidence': next_surface['confidence']
                    }
                    continue
            
            current_segment['coordinates'].append(coord)
        
        # Add last segment
        if current_segment['coordinates']:
            segments.append(current_segment)
        
        return segments
    
    def generate_damages_geojson(self, session_id, damages):
        """Generate damages GeoJSON with grouping"""
        # Group nearby damages
        grouped = self.group_damages(damages)
        
        features = []
        for group_id, group in enumerate(grouped, 1):
            # Calculate center
            avg_lat = sum(d['latitude'] for d in group) / len(group)
            avg_lon = sum(d['longitude'] for d in group) / len(group)
            
            # Get damage type (most common in group)
            damage_types = [d['damage_type'] for d in group]
            damage_type = max(set(damage_types), key=damage_types.count)
            
            # Severities
            severities = [d['severity'] for d in group]
            severity = 'high' if 'high' in severities else ('medium' if 'medium' in severities else 'low')
            
            # Images
            images = []
            for d in group:
                img_path = Path(d['image_path'])
                images.append({
                    'filename': img_path.name,
                    'url': f"images/{session_id}/{img_path.name}",
                    'timestamp': d['timestamp'],
                    'confidence': d['confidence']
                })
            
            features.append({
                'type': 'Feature',
                'geometry': {
                    'type': 'Point',
                    'coordinates': [avg_lon, avg_lat]
                },
                'properties': {
                    'id': group_id,
                    'session_id': session_id,
                    'damage_type': damage_type,
                    'severity': severity,
                    'image_count': len(images),
                    'images': images,
                    'avg_confidence': sum(d['confidence'] for d in group) / len(group),
                    'best_confidence': max(d['confidence'] for d in group),
                    'first_seen': min(d['timestamp'] for d in group),
                    'last_seen': max(d['timestamp'] for d in group)
                }
            })
        
        # Save
        output_file = self.data_dir / f"damages_{session_id}.geojson"
        geojson = {
            'type': 'FeatureCollection',
            'metadata': {
                'session_id': session_id,
                'generated': datetime.now().isoformat(),
                'total_groups': len(features),
                'total_images': sum(len(f['properties']['images']) for f in features),
                'grouping_distance_m': self.gh_config['geojson'].get('group_radius_m', 1.0)
            },
            'features': features
        }
        
        with open(output_file, 'w') as f:
            json.dump(geojson, f, indent=2)
        
        print(f"  ✓ Damages GeoJSON: {output_file}")
        return output_file
    
    def group_damages(self, damages):
        """Group damages within radius"""
        if not damages or not geodesic:
            return [[d] for d in damages]
        
        radius_m = self.gh_config['geojson'].get('group_radius_m', 1.0)
        groups = []
        used = set()
        
        for i, damage in enumerate(damages):
            if i in used:
                continue
            
            group = [damage]
            used.add(i)
            
            # Find nearby damages
            for j, other in enumerate(damages):
                if j in used or i == j:
                    continue
                
                # Same damage type?
                if damage['damage_type'] != other['damage_type']:
                    continue
                
                # Within radius?
                dist = geodesic(
                    (damage['latitude'], damage['longitude']),
                    (other['latitude'], other['longitude'])
                ).meters
                
                if dist <= radius_m:
                    group.append(other)
                    used.add(j)
            
            groups.append(group)
        
        return groups
    
    def copy_damage_images(self, session_dir, damages):
        """Copy damage images to docs/images/"""
        session_images_dir = self.images_dir / session_dir.name
        session_images_dir.mkdir(exist_ok=True)
        
        copied = 0
        for damage in damages:
            src = Path(damage['image_path'])
            if src.exists():
                dst = session_images_dir / src.name
                shutil.copy(src, dst)
                copied += 1
        
        print(f"  ✓ Bilder kopiert: {copied}")
    
    def get_surface_color(self, surface_type):
        """Get color for surface type"""
        colors = {
            'asphalt_excellent': '#27ae60',
            'asphalt_good': '#2ecc71',
            'asphalt_fair': '#f39c12',
            'asphalt_poor': '#e74c3c',
            'concrete': '#95a5a6',
            'cobblestone': '#7f8c8d',
            'paving_stones': '#8e44ad',
            'gravel': '#d35400',
            'dirt': '#795548'
        }
        return colors.get(surface_type, '#3498db')
    
    def generate_index_geojson(self):
        """Generate master index of all sessions"""
        all_routes = list(self.data_dir.glob("route_*.geojson"))
        all_damages = list(self.data_dir.glob("damages_*.geojson"))
        
        index = {
            'sessions': [],
            'total_routes': len(all_routes),
            'total_damage_files': len(all_damages),
            'last_updated': datetime.now().isoformat()
        }
        
        for route_file in sorted(all_routes):
            session_id = route_file.stem.replace('route_', '')
            damage_file = self.data_dir / f"damages_{session_id}.geojson"
            
            with open(route_file) as f:
                route_data = json.load(f)
            
            session_info = {
                'id': session_id,
                'route_file': route_file.name,
                'damage_file': damage_file.name if damage_file.exists() else None,
                'segments': route_data['metadata'].get('segments', 0)
            }
            
            if damage_file.exists():
                with open(damage_file) as f:
                    damage_data = json.load(f)
                session_info['damages'] = damage_data['metadata']['total_groups']
                session_info['damage_images'] = damage_data['metadata']['total_images']
            
            index['sessions'].append(session_info)
        
        # Save index
        index_file = self.data_dir / "index.json"
        with open(index_file, 'w') as f:
            json.dump(index, f, indent=2)
        
        print(f"\n✓ Index erstellt: {index_file}")
        print(f"  Sessions: {len(index['sessions'])}")
    
    def git_commit_push(self, message=None):
        """Git commit and push changes"""
        if not self.gh_config.get('auto_commit', True):
            print("\n⊘ Auto-Commit deaktiviert")
            return
        
        message = message or f"Auto-Update: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        print(f"\n📤 Git Commit & Push...")
        print(f"   Message: {message}")
        
        try:
            # Configure git user
            subprocess.run(['git', 'config', 'user.name', self.gh_config.get('git_user', 'Bike Surface AI')], 
                          cwd=self.repo_path, check=True)
            subprocess.run(['git', 'config', 'user.email', self.gh_config.get('git_email', 'bike-ai@example.com')],
                          cwd=self.repo_path, check=True)
            
            # Add docs folder
            subprocess.run(['git', 'add', 'docs/'], cwd=self.repo_path, check=True)
            
            # Commit
            result = subprocess.run(['git', 'commit', '-m', message], 
                                   cwd=self.repo_path, capture_output=True, text=True)
            
            if result.returncode != 0:
                if "nothing to commit" in result.stdout:
                    print("  ⊘ Keine Änderungen zum Committen")
                    return
                else:
                    print(f"  ⚠️  Commit-Warnung: {result.stdout}")
            
            # Push
            branch = self.gh_config.get('branch', 'main')
            subprocess.run(['git', 'push', 'origin', branch], cwd=self.repo_path, check=True)
            
            print("  ✅ Erfolgreich gepusht!")
            
        except subprocess.CalledProcessError as e:
            print(f"  ❌ Git-Fehler: {e}")
            print(f"     Führe manuell aus: cd {self.repo_path} && git push")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='GitHub Pages Updater')
    parser.add_argument('session_dir', help='Session-Verzeichnis')
    parser.add_argument('--no-commit', action='store_true', help='Nicht committen')
    parser.add_argument('--config', default='config_auto_live.yaml', help='Config file')
    
    args = parser.parse_args()
    
    updater = GitHubPagesUpdater(args.config)
    
    session_path = Path(args.session_dir)
    if not session_path.exists():
        print(f"❌ Session nicht gefunden: {session_path}")
        return 1
    
    # Process session
    if updater.process_session(session_path):
        # Generate index
        updater.generate_index_geojson()
        
        # Git commit
        if not args.no_commit:
            updater.git_commit_push(f"Update: Session {session_path.name}")
        
        print("\n✅ Fertig!")
        return 0
    else:
        print("\n❌ Fehler beim Verarbeiten")
        return 1


if __name__ == "__main__":
    exit(main())
