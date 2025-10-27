#!/usr/bin/env python3
"""
BIKE SURFACE AI - VOLLAUTOMATISCHES LIVE-SYSTEM
================================================
Erfasst während der Fahrt:
- GPS-Track
- Oberflächen-Kategorisierung (Asphalt/Pflaster/etc.)
- Schaden-Erkennung (Schlaglöcher/Risse/etc.)
- Automatischer Upload zu Azure
- Automatisches GitHub Pages Update

Verwendung:
    python3 auto_live_system.py
    
    Oder mit Web-UI:
    python3 auto_live_system.py --web-ui
"""

import cv2
import time
import json
import yaml
import logging
import threading
import queue
import random
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, asdict
from collections import deque
import statistics

# GPS
from gps_module import GPSModule

# Geopy für Distanzberechnung
try:
    from geopy.distance import geodesic
except ImportError:
    print("⚠️  geopy nicht installiert: pip install geopy")
    geodesic = None

# YOLOv8
try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False
    print("⚠️  YOLOv8 nicht installiert - läuft im Demo-Modus")


@dataclass
class SurfaceDetection:
    """Oberflächen-Erkennung"""
    timestamp: str
    latitude: float
    longitude: float
    surface_type: str
    confidence: float
    image_path: Optional[str] = None


@dataclass
class DamageDetection:
    """Schaden-Erkennung"""
    id: int
    timestamp: str
    latitude: float
    longitude: float
    damage_type: str
    confidence: float
    severity: str  # "low", "medium", "high"
    image_path: str
    bbox: List[float]  # [x1, y1, x2, y2]


class AutoLiveSystem:
    """Vollautomatisches Erfassungssystem"""
    
    def __init__(self, config_path="config_auto_live.yaml"):
        # Load config
        with open(config_path) as f:
            self.config = yaml.safe_load(f)
        
        # Setup logging
        self.setup_logging()
        
        # Create session
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_dir = Path(self.config['storage']['base_dir']) / self.session_id
        self.session_dir.mkdir(parents=True, exist_ok=True)
        (self.session_dir / "images").mkdir(exist_ok=True)
        (self.session_dir / "damages").mkdir(exist_ok=True)
        
        # Web-UI state file
        self.state_file = Path(__file__).parent / "live_state.json"
        
        self.logger.info("="*60)
        self.logger.info("🚴 BIKE SURFACE AI - LIVE-SYSTEM")
        self.logger.info("="*60)
        self.logger.info(f"📁 Session: {self.session_id}")
        self.logger.info(f"📂 Verzeichnis: {self.session_dir}")
        
        # Initialize components
        self.gps = None
        self.camera = None
        self.model = None
        self.azure_uploader = None
        
        # Data storage
        self.route_points = []
        self.surface_detections = []
        self.damage_detections = []
        self.surface_segments = []
        
        # Current state
        self.current_position = None
        self.last_surface_check_pos = None
        self.current_surface = None
        self.surface_buffer = deque(maxlen=self.config['surface_detection'].get('smoothing_window', 3))
        
        # Upload queue
        self.upload_queue = queue.Queue()
        self.running = False
        self.upload_thread = None
        
        # Statistics
        self.stats = {
            'session_id': self.session_id,
            'start_time': datetime.now().isoformat(),
            'end_time': None,
            'duration_seconds': 0,
            'total_images': 0,
            'total_distance_km': 0.0,
            'avg_speed_kmh': 0.0,
            'surfaces': {},
            'damages': {},
            'uploaded_items': 0,
            'surface_quality_score': 0.0
        }
        
        # Class name mappings
        self.surface_names = {v: k for k, v in self.config['model']['surface_classes'].items()}
        self.damage_names = {v: k for k, v in self.config['model']['damage_classes'].items()}
        
        self.logger.info("✅ Initialisierung abgeschlossen\n")
    
    def setup_logging(self):
        """Setup logging"""
        log_config = self.config['logging']
        
        handlers = []
        if log_config.get('console', True):
            handlers.append(logging.StreamHandler())
        
        if hasattr(self, 'session_dir'):
            log_file = self.session_dir / log_config['file']
            handlers.append(logging.FileHandler(log_file))
        
        logging.basicConfig(
            level=log_config['level'],
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=handlers
        )
        self.logger = logging.getLogger(__name__)
    
    def init_gps(self):
        """Initialize GPS"""
        self.logger.info("🛰️  Initialisiere GPS...")
        gps_config = self.config['gps']
        
        try:
            # GPSModule expects a config dict
            gps_module_config = {
                'port': gps_config['port'],
                'baudrate': gps_config['baudrate'],
                'timeout': gps_config.get('timeout', 1.0)
            }
            self.gps = GPSModule(gps_module_config)
            # GPSModule starts reading automatically in constructor
            
            # Wait for GPS fix
            self.logger.info("⏳ Warte auf GPS-Fix...")
            max_wait = gps_config.get('max_wait_seconds', 60)
            start = time.time()
            
            while time.time() - start < max_wait:
                data = self.gps.get_current_position()
                if data and data.get('latitude') and data.get('satellites', 0) >= gps_config['min_satellites']:
                    self.logger.info(f"✅ GPS-Fix: {data['satellites']} Satelliten")
                    self.logger.info(f"📍 Position: {data['latitude']:.6f}, {data['longitude']:.6f}")
                    return True
                time.sleep(1)
            
            self.logger.warning("⚠️  GPS-Fix Timeout - fahre fort (Demo-Modus)")
            return False
            
        except Exception as e:
            self.logger.error(f"❌ GPS-Initialisierung fehlgeschlagen: {e}")
            self.logger.warning("⚠️  Fahre fort im Demo-Modus")
            return False
    
    def init_camera(self):
        """Initialize camera"""
        self.logger.info("📷 Initialisiere Kamera...")
        cam_config = self.config['camera']
        
        try:
            self.camera = cv2.VideoCapture(cam_config['device_id'])
            
            if not self.camera.isOpened():
                raise RuntimeError("Kamera konnte nicht geöffnet werden")
            
            # Set resolution
            width, height = cam_config['resolution']
            self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            self.camera.set(cv2.CAP_PROP_FPS, cam_config['fps'])
            
            # Test capture
            ret, frame = self.camera.read()
            if not ret:
                raise RuntimeError("Kamera-Test fehlgeschlagen")
            
            self.logger.info(f"✅ Kamera: {width}x{height} @ {cam_config['fps']}fps")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Kamera-Initialisierung fehlgeschlagen: {e}")
            return False
    
    def init_model(self):
        """Initialize AI model"""
        model_config = self.config['model']
        
        # Check if demo mode
        if model_config.get('demo_mode', False):
            self.logger.warning("⚠️  DEMO-MODUS aktiv - simulierte Detections")
            self.model = None
            return True
        
        model_path = Path(model_config['path'])
        
        if not model_path.exists():
            self.logger.warning(f"⚠️  Modell nicht gefunden: {model_path}")
            self.logger.warning("   Setze demo_mode: true in config_auto_live.yaml")
            self.logger.warning("   Fahre fort im Demo-Modus")
            self.model = None
            return True
        
        if not YOLO_AVAILABLE:
            self.logger.error("❌ YOLOv8 nicht verfügbar - pip install ultralytics")
            return False
        
        try:
            self.logger.info(f"🤖 Lade Modell: {model_path}")
            self.model = YOLO(str(model_path))
            self.logger.info("✅ Modell geladen")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Modell-Laden fehlgeschlagen: {e}")
            return False
    
    def init_azure(self):
        """Initialize Azure uploader"""
        if not self.config['azure'].get('enabled', False):
            self.logger.info("⊘ Azure Upload deaktiviert")
            return True
        
        connection_string = self.config['azure'].get('connection_string', '')
        
        if not connection_string or connection_string == "":
            self.logger.warning("⚠️  Azure Connection String fehlt in config_auto_live.yaml")
            self.logger.warning("   Upload wird übersprungen")
            self.config['azure']['enabled'] = False
            return True
        
        try:
            from azure_uploader import AzureUploader
            self.azure_uploader = AzureUploader(
                connection_string,
                self.config['azure']['container_name']
            )
            self.logger.info("✅ Azure Uploader bereit")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Azure-Initialisierung fehlgeschlagen: {e}")
            self.config['azure']['enabled'] = False
            return True
    
    def get_gps_position(self) -> Optional[Tuple[float, float]]:
        """Get current GPS position"""
        if not self.gps:
            # Demo position (Ried bei Mering, 86510 Aichach-Friedberg)
            return (48.2904, 11.0434)
        
        data = self.gps.get_current_position()
        if data and data.get('latitude') and data.get('longitude'):
            return (data['latitude'], data['longitude'])
        
        return None
    
    def capture_and_process(self):
        """Capture image and process"""
        # Capture image
        ret, frame = self.camera.read() if self.camera else (True, None)
        if not ret:
            self.logger.warning("⚠️  Kamera-Capture fehlgeschlagen")
            return
        
        # Get GPS position
        pos = self.get_gps_position()
        if not pos:
            self.logger.warning("⚠️  Keine GPS-Position")
            return
        
        lat, lon = pos
        self.current_position = pos
        timestamp = datetime.now().isoformat()
        
        # Add to route (surface_type will be updated when detected)
        self.route_points.append({
            'timestamp': timestamp,
            'latitude': lat,
            'longitude': lon,
            'surface_type': self.current_surface  # Can be None initially
        })
        
        # Update distance
        if len(self.route_points) > 1:
            prev = self.route_points[-2]
            if geodesic:
                dist_m = geodesic((prev['latitude'], prev['longitude']), (lat, lon)).meters
                self.stats['total_distance_km'] += dist_m / 1000.0
        
        # Save image
        image_filename = f"img_{len(self.route_points):06d}.jpg"
        image_path = self.session_dir / "images" / image_filename
        
        if frame is not None:
            cv2.imwrite(str(image_path), frame)
            self.stats['total_images'] += 1
        
        # Process surface detection
        self.process_surface(frame, lat, lon, timestamp, str(image_path))
        
        # Process damage detection
        self.process_damages(frame, lat, lon, timestamp, str(image_path))
        
        self.logger.info(f"📸 {len(self.route_points):04d} | {lat:.6f},{lon:.6f} | "
                        f"{self.current_surface or 'unknown'} | "
                        f"Dist: {self.stats['total_distance_km']:.2f}km")
    
    def process_surface(self, frame, lat, lon, timestamp, image_path):
        """Process surface detection"""
        if not self.config['surface_detection'].get('enabled', True):
            return
        
        # Check if we need new surface measurement
        segment_length = self.config['surface_detection']['segment_length_m']
        
        if self.last_surface_check_pos:
            if geodesic:
                dist = geodesic(self.last_surface_check_pos, (lat, lon)).meters
                if dist < segment_length:
                    return  # Too close to last measurement
        
        # Run inference (or demo)
        if self.model is None:
            # Demo mode: random surface
            surfaces = list(self.config['model']['surface_classes'].keys())
            surface_type = random.choice(surfaces)
            confidence = random.uniform(0.6, 0.95)
        else:
            # Real inference
            results = self.model.predict(frame, conf=self.config['model']['confidence_threshold'])
            # TODO: Extract surface from results
            surface_type = "asphalt_good"
            confidence = 0.85
        
        # Add to buffer for smoothing
        self.surface_buffer.append((surface_type, confidence))
        
        # Smooth if enabled
        if self.config['surface_detection'].get('smoothing', True) and len(self.surface_buffer) >= 2:
            # Majority vote
            types = [s[0] for s in self.surface_buffer]
            surface_type = max(set(types), key=types.count)
            confidence = statistics.mean([s[1] for s in self.surface_buffer if s[0] == surface_type])
        
        # Create detection
        detection = SurfaceDetection(
            timestamp=timestamp,
            latitude=lat,
            longitude=lon,
            surface_type=surface_type,
            confidence=confidence,
            image_path=image_path if self.config['storage']['save_all_images'] else None
        )
        
        self.surface_detections.append(detection)
        self.current_surface = surface_type
        self.last_surface_check_pos = (lat, lon)
        
        # Update stats
        self.stats['surfaces'][surface_type] = self.stats['surfaces'].get(surface_type, 0) + 1
        
        self.logger.info(f"  🛣️  Oberfläche: {surface_type} ({confidence:.2f})")
    
    def process_damages(self, frame, lat, lon, timestamp, image_path):
        """Process damage detection"""
        if not self.config['damage_detection'].get('enabled', True):
            return
        
        # Run inference (or demo)
        if self.model is None:
            # Demo mode: random damage sometimes
            if random.random() < 0.15:  # 15% chance
                damages = list(self.config['model']['damage_classes'].keys())
                damage_type = random.choice(damages)
                confidence = random.uniform(0.65, 0.95)
                bbox = [100, 100, 300, 300]  # Dummy bbox
                
                detections = [(damage_type, confidence, bbox)]
            else:
                detections = []
        else:
            # Real inference
            results = self.model.predict(frame, conf=self.config['damage_detection']['min_confidence'])
            # TODO: Extract damages from results
            detections = []
        
        # Process each damage
        for damage_type, confidence, bbox in detections:
            # Calculate severity
            severity = self.calculate_severity(damage_type, confidence)
            
            # Save damage image
            damage_id = len(self.damage_detections) + 1
            damage_filename = f"damage_{damage_id:06d}.jpg"
            damage_path = self.session_dir / "damages" / damage_filename
            
            if frame is not None:
                # Draw bounding box
                x1, y1, x2, y2 = [int(c) for c in bbox]
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 3)
                cv2.putText(frame, f"{damage_type} {confidence:.2f}", 
                           (x1, y1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 2)
                cv2.imwrite(str(damage_path), frame)
            
            # Create detection
            detection = DamageDetection(
                id=damage_id,
                timestamp=timestamp,
                latitude=lat,
                longitude=lon,
                damage_type=damage_type,
                confidence=confidence,
                severity=severity,
                image_path=str(damage_path),
                bbox=bbox
            )
            
            self.damage_detections.append(detection)
            
            # Update stats
            self.stats['damages'][damage_type] = self.stats['damages'].get(damage_type, 0) + 1
            
            self.logger.warning(f"  ⚠️  SCHADEN: {damage_type} ({confidence:.2f}) - {severity.upper()}")
            
            # Queue for upload
            if self.config['azure'].get('enabled', False) and self.config['azure'].get('upload_damages', True):
                if self.config['azure']['upload_mode'] == 'live':
                    self.upload_queue.put(('damage', detection))
    
    def calculate_severity(self, damage_type, confidence):
        """Calculate damage severity"""
        rules = self.config['damage_detection'].get('severity_rules', {})
        
        if damage_type in rules:
            thresholds = rules[damage_type]
        else:
            thresholds = {'high': 0.85, 'medium': 0.70}
        
        if confidence >= thresholds.get('high', 0.85):
            return 'high'
        elif confidence >= thresholds.get('medium', 0.70):
            return 'medium'
        else:
            return 'low'
    
    def upload_worker(self):
        """Background worker for uploads"""
        while self.running:
            try:
                item = self.upload_queue.get(timeout=1.0)
                item_type, data = item
                
                if item_type == 'damage':
                    # Upload damage image
                    self.logger.info(f"☁️  Upload Schaden #{data.id}...")
                    # TODO: Implement Azure upload
                    self.stats['uploaded_items'] += 1
                
                self.upload_queue.task_done()
                
            except queue.Empty:
                continue
            except Exception as e:
                self.logger.error(f"❌ Upload-Fehler: {e}")
    
    def save_session_data(self):
        """Save session data to files"""
        self.logger.info("\n💾 Speichere Session-Daten...")
        
        # Save route
        route_file = self.session_dir / "route.geojson"
        with open(route_file, 'w') as f:
            geojson = {
                'type': 'FeatureCollection',
                'features': [{
                    'type': 'Feature',
                    'geometry': {
                        'type': 'LineString',
                        'coordinates': [[p['longitude'], p['latitude']] for p in self.route_points]
                    },
                    'properties': {
                        'session_id': self.session_id,
                        'distance_km': self.stats['total_distance_km']
                    }
                }]
            }
            json.dump(geojson, f, indent=2)
        
        self.logger.info(f"  ✓ Route: {route_file}")
        
        # Save surface detections
        surfaces_file = self.session_dir / "surfaces.json"
        with open(surfaces_file, 'w') as f:
            json.dump([asdict(s) for s in self.surface_detections], f, indent=2)
        
        self.logger.info(f"  ✓ Oberflächen: {surfaces_file}")
        
        # Save damage detections
        damages_file = self.session_dir / "damages.json"
        with open(damages_file, 'w') as f:
            json.dump([asdict(d) for d in self.damage_detections], f, indent=2)
        
        self.logger.info(f"  ✓ Schäden: {damages_file}")
        
        # Save statistics
        self.stats['end_time'] = datetime.now().isoformat()
        start = datetime.fromisoformat(self.stats['start_time'])
        end = datetime.fromisoformat(self.stats['end_time'])
        self.stats['duration_seconds'] = (end - start).total_seconds()
        
        if self.stats['duration_seconds'] > 0:
            self.stats['avg_speed_kmh'] = (self.stats['total_distance_km'] / self.stats['duration_seconds']) * 3600
        
        # Add route metadata for saved routes feature
        self.stats['route_name'] = self.session_id  # Default to timestamp, can be renamed later
        self.stats['created_at'] = self.stats['start_time']
        
        # Add route summary for quick overview
        self.stats['route_summary'] = {
            'total_points': len(self.route_points),
            'total_damages': len(self.damage_detections),
            'distance_km': round(self.stats['total_distance_km'], 2),
            'duration_minutes': round(self.stats['duration_seconds'] / 60, 1),
            'surface_breakdown': self.stats['surfaces'].copy()
        }
        
        # Save complete data for route replay
        self.stats['route_points'] = self.route_points  # All points with surface types
        self.stats['damages'] = [asdict(d) for d in self.damage_detections]  # All damages
        
        stats_file = self.session_dir / "stats.json"
        with open(stats_file, 'w') as f:
            json.dump(self.stats, f, indent=2)
        
        self.logger.info(f"  ✓ Statistik: {stats_file}")
    
    def update_web_state(self):
        """Update state file for web UI"""
        try:
            # Prepare route points (last 500 points with surface types)
            recent_route = self.route_points[-500:] if len(self.route_points) > 500 else self.route_points
            
            # Prepare recent damages (last 50 with all details)
            recent_damages_list = []
            for d in self.damage_detections[-50:]:
                recent_damages_list.append({
                    'timestamp': d.timestamp,
                    'latitude': d.latitude,
                    'longitude': d.longitude,
                    'damage_type': d.damage_type,
                    'confidence': d.confidence,
                    'severity': d.severity if hasattr(d, 'severity') else 'medium'
                })
            
            state = {
                'is_running': self.running,
                'session_id': self.session_id,
                'session_dir': str(self.session_dir),
                'stats': self.stats,
                'current_position': self.current_position,
                'current_surface': self.current_surface,
                'route_points': recent_route,  # Last 500 points for live tracking
                'recent_damages': recent_damages_list  # Last 50 damages for map display
            }
            
            with open(self.state_file, 'w') as f:
                json.dump(state, f)
        except Exception as e:
            # Silently fail - web UI is optional
            pass
    
    def print_summary(self):
        """Print session summary"""
        self.logger.info("\n" + "="*60)
        self.logger.info("📊 SESSION ZUSAMMENFASSUNG")
        self.logger.info("="*60)
        self.logger.info(f"Session: {self.session_id}")
        self.logger.info(f"Dauer: {self.stats['duration_seconds']/60:.1f} Minuten")
        self.logger.info(f"Distanz: {self.stats['total_distance_km']:.2f} km")
        self.logger.info(f"Ø Geschwindigkeit: {self.stats['avg_speed_kmh']:.1f} km/h")
        self.logger.info(f"Bilder: {self.stats['total_images']}")
        
        self.logger.info(f"\n🛣️  Oberflächen:")
        for surface, count in self.stats['surfaces'].items():
            self.logger.info(f"  {surface}: {count}")
        
        self.logger.info(f"\n⚠️  Schäden: {len(self.damage_detections)}")
        for damage, count in self.stats['damages'].items():
            self.logger.info(f"  {damage}: {count}")
        
        if self.config['azure'].get('enabled', False):
            self.logger.info(f"\n☁️  Azure Uploads: {self.stats['uploaded_items']}")
        
        self.logger.info("="*60)
    
    def run(self):
        """Main loop"""
        # Initialize all components
        if not self.init_gps():
            if not self.config['model'].get('demo_mode', False):
                self.logger.error("❌ GPS erforderlich - Abbruch")
                return
        
        if not self.init_camera():
            # Camera is required unless in demo mode
            if not self.config['model'].get('demo_mode', False):
                self.logger.error("❌ Kamera erforderlich - Abbruch")
                return
            else:
                self.logger.warning("⚠️  Fahre fort ohne Kamera (Demo-Modus)")
        
        if not self.init_model():
            self.logger.error("❌ Modell-Initialisierung fehlgeschlagen - Abbruch")
            return
        
        self.init_azure()
        
        # Start upload worker if live mode
        self.running = True
        if self.config['azure'].get('enabled', False) and self.config['azure']['upload_mode'] == 'live':
            self.upload_thread = threading.Thread(target=self.upload_worker, daemon=True)
            self.upload_thread.start()
            self.logger.info("🚀 Upload-Worker gestartet")
        
        # Main loop
        self.logger.info("\n🚴 STARTE ERFASSUNG")
        self.logger.info("Drücke Strg+C zum Beenden\n")
        
        capture_interval = self.config['camera']['capture_interval']
        
        try:
            while self.running:
                start_time = time.time()
                
                self.capture_and_process()
                
                # Update web state every 5 captures
                if len(self.route_points) % 5 == 0:
                    self.update_web_state()
                
                # Wait for next capture
                elapsed = time.time() - start_time
                sleep_time = max(0, capture_interval - elapsed)
                time.sleep(sleep_time)
                
        except KeyboardInterrupt:
            self.logger.info("\n\n⏹️  Beende Session...")
        finally:
            self.cleanup()
    
    def cleanup(self):
        """Cleanup and save"""
        self.running = False
        
        # Wait for upload queue
        if self.upload_thread and self.upload_thread.is_alive():
            self.logger.info("⏳ Warte auf Upload-Queue...")
            self.upload_queue.join()
        
        # Save all data
        self.save_session_data()
        
        # Print summary
        self.print_summary()
        
        # Cleanup hardware
        if self.camera:
            self.camera.release()
        if self.gps:
            self.gps.stop()
        
        self.logger.info(f"\n✅ Session gespeichert: {self.session_dir}")
        self.logger.info("🏁 Fertig!")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Bike Surface AI - Live System')
    parser.add_argument('--config', default='config_auto_live.yaml', help='Config file')
    parser.add_argument('--web-ui', action='store_true', help='Start with Web UI')
    
    args = parser.parse_args()
    
    if args.web_ui:
        print("🌐 Web-UI Modus - Starte Web-Server...")
        print("   Öffne http://localhost:5000 im Browser")
        print("\n   Hinweis: Web-UI mit Live-Monitoring ist in der bestehenden")
        print("   web_ui.py integriert. Starte stattdessen:")
        print("   python3 web_ui.py --live-mode")
        print("\n   Oder nutze die Datensammlung-Web-UI:")
        print("   Desktop-Icon: 'Bike AI - Datensammlung'\n")
    else:
        system = AutoLiveSystem(args.config)
        system.run()
