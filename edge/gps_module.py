"""
GPS Module for Ublox NEO-M8U
Handles GPS data acquisition and parsing for the Bike Surface AI system.
"""

import serial
import pynmea2
import logging
from typing import Optional, Dict, Any
from datetime import datetime
import time

logger = logging.getLogger(__name__)


class GPSModule:
    """Interface for Ublox NEO-M8U GPS module"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize GPS module
        
        Args:
            config: GPS configuration dictionary containing port, baudrate, timeout
        """
        self.port = config.get('port', '/dev/ttyACM0')
        self.baudrate = config.get('baudrate', 9600)
        self.timeout = config.get('timeout', 5)
        self.serial_connection = None
        self.last_valid_position = None
        self.connect()
    
    def connect(self):
        """Establish serial connection to GPS module"""
        try:
            self.serial_connection = serial.Serial(
                self.port,
                baudrate=self.baudrate,
                timeout=self.timeout
            )
            logger.info(f"Connected to GPS module on {self.port}")
        except serial.SerialException as e:
            logger.error(f"Failed to connect to GPS module: {e}")
            self.serial_connection = None
    
    def get_current_position(self) -> Optional[Dict[str, Any]]:
        """
        Get current GPS position
        
        Returns:
            Dictionary with latitude, longitude, altitude, speed, timestamp
            None if GPS fix is not available
        """
        if not self.serial_connection:
            logger.warning("GPS not connected")
            return self.last_valid_position
        
        try:
            # Read NMEA sentences until we get a valid GGA or RMC sentence
            for _ in range(10):  # Try up to 10 lines
                line = self.serial_connection.readline().decode('ascii', errors='replace').strip()
                
                if not line:
                    continue
                
                try:
                    msg = pynmea2.parse(line)
                    
                    # Parse GGA sentence (contains position and altitude)
                    if isinstance(msg, pynmea2.types.talker.GGA):
                        if msg.gps_qual > 0:  # Valid GPS fix
                            position = {
                                'latitude': msg.latitude,
                                'longitude': msg.longitude,
                                'altitude': msg.altitude if msg.altitude else 0.0,
                                'speed': 0.0,  # GGA doesn't have speed
                                'timestamp': datetime.utcnow().isoformat(),
                                'satellites': msg.num_sats,
                                'fix_quality': msg.gps_qual
                            }
                            self.last_valid_position = position
                            return position
                    
                    # Parse RMC sentence (contains position and speed)
                    elif isinstance(msg, pynmea2.types.talker.RMC):
                        if msg.status == 'A':  # Active/Valid
                            position = {
                                'latitude': msg.latitude,
                                'longitude': msg.longitude,
                                'altitude': 0.0,  # RMC doesn't have altitude
                                'speed': msg.spd_over_grnd if msg.spd_over_grnd else 0.0,
                                'timestamp': datetime.utcnow().isoformat(),
                                'satellites': 0,
                                'fix_quality': 1
                            }
                            self.last_valid_position = position
                            return position
                
                except pynmea2.ParseError:
                    continue
            
            logger.warning("No valid GPS fix obtained")
            return self.last_valid_position
        
        except Exception as e:
            logger.error(f"Error reading GPS data: {e}")
            return self.last_valid_position
    
    def wait_for_fix(self, timeout: int = 60) -> bool:
        """
        Wait for GPS to acquire a fix
        
        Args:
            timeout: Maximum time to wait in seconds
            
        Returns:
            True if fix acquired, False otherwise
        """
        start_time = time.time()
        logger.info("Waiting for GPS fix...")
        
        while time.time() - start_time < timeout:
            position = self.get_current_position()
            if position:
                logger.info(f"GPS fix acquired: {position['latitude']:.6f}, {position['longitude']:.6f}")
                return True
            time.sleep(1)
        
        logger.warning(f"GPS fix not acquired within {timeout} seconds")
        return False
    
    def close(self):
        """Close serial connection"""
        if self.serial_connection:
            self.serial_connection.close()
            logger.info("GPS connection closed")


class MockGPSModule(GPSModule):
    """Mock GPS module for testing without hardware"""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize mock GPS (no serial connection)"""
        self.port = config.get('port', 'mock')
        self.last_valid_position = None
        logger.info("Using mock GPS module")
    
    def connect(self):
        """Mock connection (always succeeds)"""
        pass
    
    def get_current_position(self) -> Optional[Dict[str, Any]]:
        """Return simulated GPS position"""
        import random
        
        # Simulate position around Berlin, Germany
        base_lat = 52.5200
        base_lon = 13.4050
        
        position = {
            'latitude': base_lat + random.uniform(-0.01, 0.01),
            'longitude': base_lon + random.uniform(-0.01, 0.01),
            'altitude': random.uniform(30, 50),
            'speed': random.uniform(0, 30),  # km/h
            'timestamp': datetime.utcnow().isoformat(),
            'satellites': random.randint(6, 12),
            'fix_quality': 1
        }
        
        self.last_valid_position = position
        return position
    
    def wait_for_fix(self, timeout: int = 60) -> bool:
        """Mock always has a fix"""
        logger.info("Mock GPS fix acquired immediately")
        return True
    
    def close(self):
        """Mock close (nothing to do)"""
        pass
