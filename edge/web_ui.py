#!/usr/bin/env python3
"""
Web-UI für Bike Surface AI - Flask Server
Stabil und ohne GUI-Probleme
"""

from flask import Flask, render_template, jsonify, request, Response, send_from_directory
import subprocess
import json
import time
from pathlib import Path
from datetime import datetime
import signal
import os
import cv2
import threading

app = Flask(__name__)

# Kamera für Live-Stream
camera_lock = threading.Lock()
camera = None
last_capture_frame = None
capture_flash = False

# Global State
state = {
    'is_running': False,
    'process': None,
    'start_time': None,
    'output_dir': None,
    'stats': {'images': 0, 'distance': 0}
}

# Auto live system process (when started from web UI)
auto_process = None
auto_lock = threading.Lock()
demo_mode = False  # Start in production mode by default

# Global GPS module to maintain satellite count cache
gps_module = None
gps_last_position = None


@app.route('/')
def index():
    """Haupt-Seite"""
    return render_template('index.html')

@app.route('/api/status')
def get_status():
    """Status abrufen"""
    status = {
        'is_running': state['is_running'],
        'start_time': state['start_time'],
        'output_dir': str(state['output_dir']) if state['output_dir'] else None,
        'stats': state['stats']
    }
    
    # Zähle Bilder wenn läuft
    if state['is_running'] and state['output_dir']:
        images_dir = Path(state['output_dir']) / 'images'
        if images_dir.exists():
            state['stats']['images'] = len(list(images_dir.glob('*.jpg')))
    
    # Berechne Laufzeit
    if state['start_time']:
        elapsed = int(time.time() - state['start_time'])
        status['runtime'] = f"{elapsed//3600:02d}:{(elapsed%3600)//60:02d}:{elapsed%60:02d}"
    else:
        status['runtime'] = "00:00:00"
    
    return jsonify(status)

@app.route('/api/start', methods=['POST'])
def start_capture():
    """Starte Datensammlung"""
    if state['is_running']:
        return jsonify({'error': 'Already running'}), 400
    
    try:
        # WICHTIG: Kamera freigeben damit simple_capture.py sie nutzen kann!
        global camera
        with camera_lock:
            if camera is not None:
                camera.release()
                camera = None
        
        # Erstelle Output-Dir
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = Path(__file__).parent / f"data_collection/{timestamp}"
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "images").mkdir(exist_ok=True)
        
        state['output_dir'] = output_dir
        
        # Starte simple_capture.py
        script_path = Path(__file__).parent / "simple_capture.py"
        
        state['process'] = subprocess.Popen(
            ['python3', str(script_path), str(output_dir)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,  # Alle Logs zu stdout
            bufsize=1,
            universal_newlines=True
        )
        
        state['is_running'] = True
        state['start_time'] = time.time()
        state['stats'] = {'images': 0, 'distance': 0}
        
        return jsonify({'success': True, 'output_dir': str(output_dir)})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/stop', methods=['POST'])
def stop_capture():
    """Stoppe Datensammlung"""
    if not state['is_running']:
        return jsonify({'error': 'Not running'}), 400
    
    try:
        # Beende Prozess
        if state['process'] and state['process'].poll() is None:
            state['process'].send_signal(signal.SIGINT)
            try:
                state['process'].wait(timeout=5)
            except subprocess.TimeoutExpired:
                state['process'].kill()
                state['process'].wait()
        
        # Zähle finale Bilder
        if state['output_dir']:
            images_dir = Path(state['output_dir']) / 'images'
            if images_dir.exists():
                state['stats']['images'] = len(list(images_dir.glob('*.jpg')))
        
        result = {
            'success': True,
            'images': state['stats']['images'],
            'output_dir': str(state['output_dir'])
        }
        
        # Reset State WICHTIG!
        state['is_running'] = False
        state['process'] = None
        state['start_time'] = None
        
        # Kamera wieder für Stream öffnen (mit kurzer Verzögerung)
        time.sleep(0.5)
        
        return jsonify(result)
        
    except Exception as e:
        state['is_running'] = False
        state['process'] = None
        state['start_time'] = None
        return jsonify({'error': str(e)}), 500

@app.route('/api/sessions')
def get_sessions():
    """Liste alle Aufnahme-Sessions"""
    data_dir = Path(__file__).parent / "data_collection"
    
    if not data_dir.exists():
        return jsonify([])
    
    sessions = []
    for session_dir in sorted(data_dir.iterdir(), reverse=True):
        if session_dir.is_dir():
            images_dir = session_dir / "images"
            image_count = len(list(images_dir.glob('*.jpg'))) if images_dir.exists() else 0
            
            # Berechne Ordnergröße
            folder_size = sum(f.stat().st_size for f in session_dir.rglob('*') if f.is_file())
            folder_size_mb = folder_size / (1024 * 1024)
            
            metadata_file = session_dir / "metadata.json"
            metadata = {}
            if metadata_file.exists():
                with open(metadata_file) as f:
                    metadata = json.load(f)
            
            sessions.append({
                'name': session_dir.name,
                'images': image_count,
                'size_mb': round(folder_size_mb, 2),
                'path': str(session_dir),
                'metadata': metadata
            })
    
    return jsonify(sessions)

def get_camera():
    """Hole oder erstelle Kamera-Instanz - NICHT während Capture!"""
    global camera
    
    # Während Capture: Keine Kamera öffnen!
    if state['is_running']:
        return None
    
    with camera_lock:
        if camera is None or not camera.isOpened():
            camera = cv2.VideoCapture(0)
            camera.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
            camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
            camera.set(cv2.CAP_PROP_FPS, 10)
        return camera

def generate_frames():
    """Generiere MJPEG Stream"""
    global capture_flash
    
    while True:
        try:
            # Wenn Capture läuft, zeige Placeholder
            if state['is_running']:
                # Schwarzes Bild mit Text
                import numpy as np
                placeholder = np.zeros((360, 640, 3), dtype=np.uint8)
                cv2.putText(placeholder, 'AUFNAHME LAEUFT', (150, 180), 
                           cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                cv2.putText(placeholder, 'Kamera wird genutzt', (180, 220), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
                
                ret, buffer = cv2.imencode('.jpg', placeholder, [cv2.IMWRITE_JPEG_QUALITY, 85])
                frame_bytes = buffer.tobytes()
                
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
                
                time.sleep(0.5)
                continue
            
            cam = get_camera()
            if cam is None:
                time.sleep(0.5)
                continue
                
            success, frame = cam.read()
            
            if not success:
                time.sleep(0.1)
                continue
            
            # Resize für Stream (640x360 für Performance)
            stream_frame = cv2.resize(frame, (640, 360))
            
            # Roter Rahmen bei Capture
            if capture_flash:
                cv2.rectangle(stream_frame, (0, 0), (639, 359), (0, 0, 255), 10)
                capture_flash = False
            
            # Encode als JPEG
            ret, buffer = cv2.imencode('.jpg', stream_frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            frame_bytes = buffer.tobytes()
            
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
            
            time.sleep(0.05)  # ~20 FPS
            
        except Exception as e:
            print(f"Stream error: {e}")
            time.sleep(1)

@app.route('/video_feed')
def video_feed():
    """Video-Stream Endpoint"""
    return Response(generate_frames(),
                   mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/api/capture_flash', methods=['POST'])
def trigger_capture_flash():
    """Trigger für roten Rahmen"""
    global capture_flash
    capture_flash = True
    return jsonify({'success': True})

@app.route('/api/latest_images')
def get_latest_images():
    """Hole die letzten 5 aufgenommenen Bilder"""
    if not state['output_dir']:
        return jsonify([])
    
    images_dir = Path(state['output_dir']) / 'images'
    if not images_dir.exists():
        return jsonify([])
    
    # Hole letzte 5 Bilder
    images = sorted(images_dir.glob('*.jpg'), key=lambda p: p.stat().st_mtime, reverse=True)[:5]
    
    result = []
    for img in images:
        result.append({
            'name': img.name,
            'path': str(img.relative_to(Path(__file__).parent)),
            'size': img.stat().st_size,
            'time': img.stat().st_mtime
        })
    
    return jsonify(result)

@app.route('/image/<path:filepath>')
def serve_image(filepath):
    """Serve Bild-Datei"""
    from flask import send_file
    full_path = Path(__file__).parent / filepath
    if full_path.exists() and full_path.suffix == '.jpg':
        return send_file(full_path, mimetype='image/jpeg')
    return "Not found", 404

@app.route('/api/open_folder', methods=['POST'])
def open_folder():
    """Öffne Ordner im Dateimanager"""
    import subprocess
    data = request.get_json()
    folder_path = data.get('path')
    
    if not folder_path or not Path(folder_path).exists():
        return jsonify({'error': 'Invalid path'}), 400
    
    try:
        # Linux: xdg-open öffnet Dateimanager
        subprocess.Popen(['xdg-open', folder_path])
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/live/status')
def live_status():
    """Get live inference status (from auto_live_system.py via live_state.json)"""
    live_state_file = Path(__file__).parent / 'live_state.json'
    
    # Try to read live state from auto_live_system.py
    if live_state_file.exists():
        try:
            with open(live_state_file, 'r') as f:
                state_data = json.load(f)
                return jsonify(state_data)
        except Exception as e:
            print(f"Fehler beim Lesen von live_state.json: {e}")
    
    # Return demo state when no live session
    demo_state = {
        'is_running': False,
        'demo_mode': True,
        'session_id': 'Demo-Modus',
        'session_dir': None,
        'stats': {
            'total_images': 0,
            'total_distance_km': 0.0,
            'avg_speed_kmh': 0.0,
            'surfaces': {},
            'damages': {},
            'duration_seconds': 0
        },
        'current_position': None,  # Will be filled with GPS data if available
        'current_surface': None,
        'recent_damages': [],
        'route_points': []
    }
    
    # Respect demo_mode flag if no live_state.json
    demo_state['demo_mode'] = demo_mode
    
    # If in production mode (not demo), try to get current GPS position
    if not demo_mode:
        global gps_module, gps_last_position
        if gps_module:
            position = gps_module.get_current_position()
            if position and position.get('latitude') and position.get('latitude') != 0:
                demo_state['current_position'] = [position['latitude'], position['longitude']]
            elif gps_last_position:
                demo_state['current_position'] = [gps_last_position['latitude'], gps_last_position['longitude']]
    
    return jsonify(demo_state)


@app.route('/live')
def live_page():
    """Serve the live inference page"""
    return render_template('live_inference.html')


@app.route('/routes')
def routes_page():
    """Serve the saved routes page"""
    return render_template('routes.html')


@app.route('/api/live/start', methods=['POST'])
def live_start():
    """Start auto_live_system.py as a subprocess"""
    global auto_process
    with auto_lock:
        if auto_process and auto_process.poll() is None:
            return jsonify({'error': 'already_running'}), 400
        try:
            script = Path(__file__).parent / 'auto_live_system.py'
            auto_process = subprocess.Popen(['python3', str(script)])
            return jsonify({'status': 'started', 'pid': auto_process.pid})
        except Exception as e:
            return jsonify({'error': str(e)}), 500


@app.route('/api/live/stop', methods=['POST'])
def live_stop():
    """Stop the auto_live_system subprocess"""
    global auto_process
    with auto_lock:
        if not auto_process or auto_process.poll() is not None:
            return jsonify({'error': 'not_running'}), 400
        try:
            auto_process.send_signal(signal.SIGINT)
            try:
                auto_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                auto_process.kill()
                auto_process.wait()
            pid = auto_process.pid
            auto_process = None
            
            # Clean up live_state.json after stopping
            live_state_file = Path(__file__).parent / 'live_state.json'
            if live_state_file.exists():
                try:
                    live_state_file.unlink()
                    print("live_state.json gelöscht nach Stop")
                except Exception as e:
                    print(f"Fehler beim Löschen von live_state.json: {e}")
            
            return jsonify({'status': 'stopped', 'pid': pid})
        except Exception as e:
            return jsonify({'error': str(e)}), 500


@app.route('/api/live/demo', methods=['POST'])
def live_demo_toggle():
    """Toggle demo mode for live UI (affects /api/live/status when no live process)"""
    global demo_mode
    data = request.get_json() or {}
    demo = data.get('demo')
    if demo is None:
        return jsonify({'error': 'missing demo param'}), 400
    demo_mode = bool(demo)
    return jsonify({'demo_mode': demo_mode})


@app.route('/api/demo/gpx-route')
def get_gpx_route():
    """Load and parse GPX file for demo route"""
    import xml.etree.ElementTree as ET
    import random
    
    gpx_file = os.path.join(os.path.dirname(__file__), 'demo_route', 'Tour14.gpx')
    
    try:
        tree = ET.parse(gpx_file)
        root = tree.getroot()
        
        # Extract namespace
        ns = {'gpx': 'http://www.topografix.com/GPX/1/1'}
        
        # Extract all track points
        route_points = []
        
        for trkpt in root.findall('.//gpx:trkpt', ns):
            lat = float(trkpt.get('lat'))
            lon = float(trkpt.get('lon'))
            
            route_points.append({
                'latitude': lat,
                'longitude': lon,
                'surface_type': 'asphalt'  # Will be assigned in segments
            })
        
        # Assign surface types in realistic segments
        # Most of route is asphalt, one section (~middle third) is unpaved/gravel
        total_points = len(route_points)
        gravel_start = int(total_points * 0.4)  # Start gravel section at 40%
        gravel_end = int(total_points * 0.6)    # End at 60% (Sirchenried-AIC15 section)
        
        for i in range(len(route_points)):
            if gravel_start <= i < gravel_end:
                route_points[i]['surface_type'] = 'unpaved'  # Schotter/gravel section
            else:
                route_points[i]['surface_type'] = 'asphalt'  # Default asphalt
        
        # Generate some demo damages along the route
        damages = []
        damage_types = ['pothole', 'crack_longitudinal', 'crack_transverse']
        severities = ['high', 'medium', 'low']
        image_paths = ['/damages/Schlagloch.jpg', '/damages/Risse.jpg', 
                      '/damages/Risse1.jpg', '/damages/Schlagloch 2.jpg']
        
        # Place damages at specific intervals
        num_damages = min(6, len(route_points) // 100)  # ~6 damages
        damage_indices = [i * (len(route_points) // (num_damages + 1)) for i in range(1, num_damages + 1)]
        
        for idx in damage_indices:
            if idx < len(route_points):
                point = route_points[idx]
                damages.append({
                    'latitude': point['latitude'],
                    'longitude': point['longitude'],
                    'damage_type': random.choice(damage_types),
                    'severity': random.choice(severities),
                    'confidence': round(random.uniform(0.75, 0.95), 2),
                    'timestamp': '2025-10-27T12:00:00',
                    'image_path': random.choice(image_paths)
                })
        
        return jsonify({
            'route_points': route_points,
            'damages': damages,
            'route_name': 'Rundwanderung Baindlkirch',
            'total_points': len(route_points)
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/gps/current')
def gps_current():
    """Get current GPS position from connected GPS module"""
    try:
        # Try to import and read GPS (quick check only)
        from gps_module import GPSModule
        
        gps_config = {
            'port': '/dev/ttyACM0',
            'baudrate': 9600,
            'timeout': 1.0
        }
        
        gps = GPSModule(gps_config)
        
        # Quick read without waiting
        position = gps.get_current_position()
        gps.close()
        
        if position and position.get('latitude') is not None:
            return jsonify({
                'latitude': position['latitude'],
                'longitude': position['longitude'],
                'altitude': position.get('altitude'),
                'satellites': position.get('satellites'),
                'fix': True
            })
        else:
            return jsonify({
                'latitude': None,
                'longitude': None,
                'fix': False
            })
    except Exception as e:
        print(f"GPS Error: {e}")
        return jsonify({
            'latitude': None,
            'longitude': None,
            'fix': False,
            'error': str(e)
        })


@app.route('/api/hardware/status')
def hardware_status():
    """Get hardware status for GPS and Camera"""
    global gps_module, gps_last_position
    
    status = {
        'gps': {
            'connected': False,
            'latitude': None,
            'longitude': None,
            'satellites': 0
        },
        'camera': {
            'available': False,
            'busy': False
        }
    }
    
    # Check GPS - use persistent GPS module to maintain satellite count cache
    try:
        from gps_module import GPSModule
        
        # Initialize GPS module if not exists
        if gps_module is None:
            gps_config = {
                'port': '/dev/ttyACM0',
                'baudrate': 9600,
                'timeout': 1.0
            }
            gps_module = GPSModule(gps_config)
        
        # Try to get position - may need multiple attempts to get fresh data
        position = None
        for attempt in range(3):
            position = gps_module.get_current_position()
            if position and position.get('latitude') is not None and position.get('latitude') != 0:
                break
        
        if position and position.get('latitude') is not None and position.get('latitude') != 0:
            status['gps']['connected'] = True
            status['gps']['latitude'] = position['latitude']
            status['gps']['longitude'] = position['longitude']
            # Ensure satellites is always an integer
            try:
                status['gps']['satellites'] = int(position.get('satellites', 0))
            except (ValueError, TypeError):
                status['gps']['satellites'] = 0
            # Cache last valid position
            gps_last_position = {
                'latitude': status['gps']['latitude'],
                'longitude': status['gps']['longitude'],
                'satellites': status['gps']['satellites']
            }
        elif position and position.get('satellites', 0) > 0:
            # GPS module connected but no fix yet
            status['gps']['connected'] = True
            try:
                status['gps']['satellites'] = int(position.get('satellites', 0))
            except (ValueError, TypeError):
                status['gps']['satellites'] = 0
        else:
            # No GPS data at all - but use cached position if available
            if gps_last_position:
                status['gps']['connected'] = True
                status['gps']['latitude'] = gps_last_position['latitude']
                status['gps']['longitude'] = gps_last_position['longitude']
                status['gps']['satellites'] = gps_last_position['satellites']
            else:
                status['gps']['connected'] = False
    except Exception as e:
        print(f"GPS check error: {e}")
        # Use cached position if available
        if gps_last_position:
            status['gps']['connected'] = True
            status['gps']['latitude'] = gps_last_position['latitude']
            status['gps']['longitude'] = gps_last_position['longitude']
            status['gps']['satellites'] = gps_last_position['satellites']
        else:
            status['gps']['connected'] = False
    
    # Check Camera
    # First check if camera is already in use by our processes
    camera_in_use = False
    if state.get('is_running'):
        camera_in_use = True
    
    with auto_lock:
        if auto_process and auto_process.poll() is None:
            camera_in_use = True
    
    if camera_in_use:
        status['camera']['available'] = True
        status['camera']['busy'] = True
        status['camera']['device'] = '/dev/video0'
    else:
        # Check for video devices and get info
        try:
            import os
            import subprocess
            
            # Check which video devices exist
            video_devices = []
            for i in range(4):
                device = f'/dev/video{i}'
                if os.path.exists(device):
                    video_devices.append(device)
            
            if video_devices:
                status['camera']['available'] = True
                status['camera']['busy'] = False
                status['camera']['device'] = video_devices[0]
                
                # Try to get camera name
                try:
                    result = subprocess.run(['v4l2-ctl', '--device', video_devices[0], '--info'], 
                                          capture_output=True, text=True, timeout=2)
                    if result.returncode == 0:
                        for line in result.stdout.split('\n'):
                            if 'Card type' in line:
                                status['camera']['name'] = line.split(':')[1].strip()
                                break
                except:
                    pass
            else:
                status['camera']['available'] = False
        except Exception as e:
            print(f"Camera check error: {e}")
            status['camera']['available'] = False
    
    return jsonify(status)


@app.route('/api/gps/last_known')
def gps_last_known():
    """Get last known GPS position (for map centering)"""
    global gps_last_position
    
    if gps_last_position:
        return jsonify(gps_last_position)
    else:
        # Default to Ried bei Mering
        return jsonify({
            'latitude': 48.2904,
            'longitude': 11.0434,
            'satellites': 0
        })


# ============================================
# SAVED ROUTES API
# ============================================

@app.route('/api/sessions/list')
def sessions_list():
    """List all saved sessions/routes"""
    try:
        base_dir = Path(__file__).parent / "live_sessions"
        
        if not base_dir.exists():
            return jsonify({'sessions': []})
        
        sessions = []
        for session_dir in base_dir.iterdir():
            if session_dir.is_dir():
                stats_file = session_dir / "stats.json"
                if stats_file.exists():
                    try:
                        with open(stats_file, 'r') as f:
                            stats = json.load(f)
                        
                        # Extract summary info
                        route_summary = stats.get('route_summary', {})
                        sessions.append({
                            'session_id': stats.get('session_id', session_dir.name),
                            'route_name': stats.get('route_name', session_dir.name),
                            'created_at': stats.get('created_at', stats.get('start_time', '')),
                            'distance_km': route_summary.get('distance_km', 0),
                            'duration_minutes': route_summary.get('duration_minutes', 0),
                            'damage_count': route_summary.get('total_damages', 0),
                            'total_images': stats.get('total_images', 0)
                        })
                    except Exception as e:
                        print(f"Error loading session {session_dir.name}: {e}")
                        continue
        
        # Sort by created_at descending (newest first)
        sessions.sort(key=lambda x: x['created_at'], reverse=True)
        
        return jsonify({'sessions': sessions})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/sessions/<session_id>')
def session_detail(session_id):
    """Get detailed session data for display on map"""
    try:
        base_dir = Path(__file__).parent / "live_sessions"
        session_dir = base_dir / session_id
        stats_file = session_dir / "stats.json"
        
        if not stats_file.exists():
            return jsonify({'error': 'Session not found'}), 404
        
        with open(stats_file, 'r') as f:
            stats = json.load(f)
        
        return jsonify({
            'session_id': session_id,
            'route_name': stats.get('route_name', session_id),
            'created_at': stats.get('created_at', ''),
            'route_points': stats.get('route_points', []),
            'damages': stats.get('damages', []),
            'stats': stats.get('route_summary', {}),
            'surface_breakdown': stats.get('surfaces', {})
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/sessions/rename', methods=['POST'])
def session_rename():
    """Rename a saved route"""
    try:
        data = request.json
        session_id = data.get('session_id')
        new_name = data.get('new_name', '').strip()
        
        if not session_id or not new_name:
            return jsonify({'success': False, 'message': 'Missing parameters'}), 400
        
        base_dir = Path(__file__).parent / "live_sessions"
        session_dir = base_dir / session_id
        stats_file = session_dir / "stats.json"
        
        if not stats_file.exists():
            return jsonify({'success': False, 'message': 'Session not found'}), 404
        
        # Load stats
        with open(stats_file, 'r') as f:
            stats = json.load(f)
        
        # Update route name
        stats['route_name'] = new_name
        
        # Save back
        with open(stats_file, 'w') as f:
            json.dump(stats, f, indent=2)
        
        return jsonify({'success': True})
    
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/sessions/delete', methods=['POST'])
def session_delete():
    """Delete a saved route"""
    try:
        import shutil
        
        data = request.json
        session_id = data.get('session_id')
        
        if not session_id:
            return jsonify({'success': False, 'message': 'Missing session_id'}), 400
        
        base_dir = Path(__file__).parent / "live_sessions"
        session_dir = base_dir / session_id
        
        if not session_dir.exists():
            return jsonify({'success': False, 'message': 'Session not found'}), 404
        
        # Delete entire session directory
        shutil.rmtree(session_dir)
        
        return jsonify({'success': True})
    
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


# ============================================
# STATIC FILES
# ============================================

@app.route('/static/<path:filename>')
def serve_static(filename):
    """Serve static files (demo images, etc.)"""
    static_dir = Path(__file__).parent / 'static'
    return send_from_directory(static_dir, filename)


@app.route('/damages/<path:filename>')
def serve_damage_image(filename):
    """Serve damage images from damages folder"""
    damages_dir = Path(__file__).parent / 'damages'
    return send_from_directory(damages_dir, filename)


@app.route('/surfaces/<path:filename>')
def serve_surface_image(filename):
    """Serve surface images from surfaces folder"""
    surfaces_dir = Path(__file__).parent / 'surfaces'
    return send_from_directory(surfaces_dir, filename)


@app.route('/routes/<path:filename>')
def serve_route_image(filename):
    """Serve route images from routes folder"""
    routes_dir = Path(__file__).parent / 'routes'
    return send_from_directory(routes_dir, filename)


if __name__ == '__main__':
    # Erstelle templates-Verzeichnis
    templates_dir = Path(__file__).parent / 'templates'
    templates_dir.mkdir(exist_ok=True)
    
    print("="*60)
    print("🚴 Bike Surface AI - Web Interface")
    print("="*60)
    print("\nÖffne im Browser:")
    print("  http://localhost:5000")
    print("\nZum Beenden: Strg+C")
    print("="*60)
    
    app.run(host='0.0.0.0', port=5000, debug=False)
