"""
Main Edge System for Bike Surface AI
Runs on Jetson Orin Nano - captures camera frames, runs AI inference, 
collects GPS data, and sends detections to cloud.
"""

import asyncio
import json
import time
import yaml
import logging
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime
from logging.handlers import RotatingFileHandler

import cv2
import requests

from ai_inference import SurfaceDetector
from gps_module import GPSModule, MockGPSModule

# Configure logging
def setup_logging(config: Dict[str, Any]):
    """Setup logging configuration"""
    log_config = config.get('logging', {})
    log_level = getattr(logging, log_config.get('level', 'INFO'))
    log_file = log_config.get('file', 'edge_system.log')
    max_bytes = log_config.get('max_bytes', 10485760)
    backup_count = log_config.get('backup_count', 3)
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # File handler with rotation
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=max_bytes,
        backupCount=backup_count
    )
    file_handler.setFormatter(formatter)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)


logger = logging.getLogger(__name__)


class BikeEdgeSystem:
    """Main edge system coordinator"""
    
    def __init__(self, config_path: str = "config.yaml"):
        """
        Initialize edge system
        
        Args:
            config_path: Path to YAML configuration file
        """
        self.config = self.load_config(config_path)
        setup_logging(self.config)
        
        logger.info("Initializing Bike Surface AI Edge System")
        
        # Initialize components
        self.detector = SurfaceDetector(self.config['model'])
        
        # Try real GPS first, fallback to mock
        try:
            self.gps = GPSModule(self.config['gps'])
            if not self.gps.wait_for_fix(timeout=30):
                logger.warning("GPS fix not acquired, using mock GPS")
                self.gps = MockGPSModule(self.config['gps'])
        except Exception as e:
            logger.error(f"Failed to initialize GPS: {e}. Using mock GPS")
            self.gps = MockGPSModule(self.config['gps'])
        
        self.camera = None
        self.session_data = []
        self.ride_id = None
        self.running = False
        
        # Create backup directory
        backup_dir = Path(self.config['storage']['backup_dir'])
        backup_dir.mkdir(exist_ok=True)
        
        logger.info("Edge system initialized successfully")
    
    def load_config(self, config_path: str) -> Dict[str, Any]:
        """Load configuration from YAML file"""
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    
    async def start_session(self):
        """Start a new detection session"""
        logger.info("=" * 60)
        logger.info("Starting new detection session")
        logger.info("=" * 60)
        
        # Initialize camera
        camera_config = self.config['camera']
        self.camera = cv2.VideoCapture(camera_config['device_id'])
        
        if not self.camera.isOpened():
            logger.error("Failed to open camera")
            return
        
        # Set camera properties
        self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, camera_config['resolution'][0])
        self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, camera_config['resolution'][1])
        self.camera.set(cv2.CAP_PROP_FPS, camera_config['fps'])
        
        logger.info(f"Camera opened: {camera_config['resolution'][0]}x{camera_config['resolution'][1]} @ {camera_config['fps']} FPS")
        
        self.session_data = []
        self.running = True
        
        # Calculate frame interval based on FPS
        frame_interval = 1.0 / camera_config['fps']
        
        # Upload task runs in background
        upload_task = asyncio.create_task(self.periodic_upload())
        
        try:
            frame_count = 0
            last_frame_time = time.time()
            
            while self.running:
                current_time = time.time()
                
                # Maintain target FPS
                if current_time - last_frame_time < frame_interval:
                    await asyncio.sleep(0.01)
                    continue
                
                last_frame_time = current_time
                
                # Capture frame
                ret, frame = self.camera.read()
                if not ret:
                    logger.warning("Failed to capture frame")
                    await asyncio.sleep(0.1)
                    continue
                
                frame_count += 1
                
                # Get GPS coordinates
                gps_data = self.gps.get_current_position()
                if not gps_data:
                    logger.warning("No GPS data available")
                    await asyncio.sleep(0.1)
                    continue
                
                # Run AI inference
                detections = self.detector.detect(frame)
                
                if detections:
                    logger.info(f"Frame {frame_count}: Detected {len(detections)} objects at ({gps_data['latitude']:.6f}, {gps_data['longitude']:.6f})")
                    for det in detections:
                        logger.info(f"  - {det['class']}: {det['confidence']:.2f}")
                
                # Create detection record
                detection_record = {
                    "timestamp": current_time,
                    "latitude": gps_data['latitude'],
                    "longitude": gps_data['longitude'],
                    "altitude": gps_data.get('altitude', 0.0),
                    "speed": gps_data.get('speed', 0.0),
                    "detections": detections
                }
                
                self.session_data.append(detection_record)
                
                # Optional: Display frame with detections (for debugging)
                # annotated_frame = self.detector.visualize_detections(frame, detections)
                # cv2.imshow('Bike Surface AI', annotated_frame)
                # if cv2.waitKey(1) & 0xFF == ord('q'):
                #     break
                
                await asyncio.sleep(0.01)
        
        except KeyboardInterrupt:
            logger.info("Session stopped by user (Ctrl+C)")
        except Exception as e:
            logger.error(f"Error during session: {e}", exc_info=True)
        finally:
            self.running = False
            upload_task.cancel()
            try:
                await upload_task
            except asyncio.CancelledError:
                pass
            await self.cleanup()
    
    async def periodic_upload(self):
        """Periodically upload data to cloud"""
        upload_interval = self.config['cloud']['upload_interval']
        batch_size = self.config['cloud']['batch_size']
        
        while self.running:
            try:
                await asyncio.sleep(upload_interval)
                
                # Upload if we have enough data
                if len(self.session_data) >= batch_size:
                    await self.upload_to_cloud()
            
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in periodic upload: {e}")
    
    async def upload_to_cloud(self):
        """Upload detection data to cloud API"""
        if not self.session_data:
            return
        
        data_to_upload = self.session_data.copy()
        
        try:
            cloud_config = self.config['cloud']
            response = requests.post(
                f"{cloud_config['api_url']}/upload",
                json={"detections": data_to_upload},
                timeout=cloud_config['timeout']
            )
            response.raise_for_status()
            
            result = response.json()
            self.ride_id = result.get('ride_id')
            
            logger.info(f"✓ Uploaded {len(data_to_upload)} detections to cloud (Ride ID: {self.ride_id})")
            
            # Clear uploaded data
            self.session_data = [d for d in self.session_data if d not in data_to_upload]
        
        except requests.exceptions.ConnectionError:
            logger.error("Failed to connect to cloud API - saving locally")
            self.save_local_backup(data_to_upload)
        except requests.exceptions.Timeout:
            logger.error("Cloud API request timed out - saving locally")
            self.save_local_backup(data_to_upload)
        except Exception as e:
            logger.error(f"Failed to upload data: {e} - saving locally")
            self.save_local_backup(data_to_upload)
    
    def save_local_backup(self, data: List[Dict[str, Any]] = None):
        """Save data locally as GeoJSON backup"""
        if data is None:
            data = self.session_data
        
        if not data:
            return
        
        backup_dir = Path(self.config['storage']['backup_dir'])
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = backup_dir / f"backup_{timestamp}.geojson"
        
        geojson_data = self.convert_to_geojson(data)
        
        with open(backup_file, 'w') as f:
            json.dump(geojson_data, f, indent=2)
        
        logger.info(f"💾 Saved backup to {backup_file}")
        
        # Clean up old backups
        self.cleanup_old_backups()
    
    def cleanup_old_backups(self):
        """Remove old backup files to save space"""
        backup_dir = Path(self.config['storage']['backup_dir'])
        max_files = self.config['storage']['max_backup_files']
        
        backup_files = sorted(backup_dir.glob("backup_*.geojson"), key=lambda p: p.stat().st_mtime)
        
        if len(backup_files) > max_files:
            for old_file in backup_files[:-max_files]:
                old_file.unlink()
                logger.info(f"Deleted old backup: {old_file}")
    
    def convert_to_geojson(self, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Convert detection data to GeoJSON format"""
        features = []
        
        for record in data:
            feature = {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [record['longitude'], record['latitude']]
                },
                "properties": {
                    "timestamp": record['timestamp'],
                    "detections": record['detections'],
                    "altitude": record.get('altitude', 0.0),
                    "speed": record.get('speed', 0.0)
                }
            }
            features.append(feature)
        
        return {
            "type": "FeatureCollection",
            "features": features,
            "metadata": {
                "generated": datetime.now().isoformat(),
                "total_features": len(features)
            }
        }
    
    async def cleanup(self):
        """Cleanup resources"""
        logger.info("Cleaning up resources...")
        
        # Release camera
        if self.camera:
            self.camera.release()
            cv2.destroyAllWindows()
        
        # Upload remaining data
        if self.session_data:
            logger.info(f"Uploading final {len(self.session_data)} detections...")
            await self.upload_to_cloud()
            
            # Save any remaining data locally as backup
            if self.session_data:
                self.save_local_backup()
        
        # Close GPS
        self.gps.close()
        
        logger.info("Cleanup complete")
        logger.info("=" * 60)


async def main():
    """Main entry point"""
    try:
        system = BikeEdgeSystem()
        await system.start_session()
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        return 1
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
