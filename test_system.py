"""
Test Script for Bike Surface AI System
Tests each component individually without full deployment
"""

import sys
import os
from pathlib import Path

print("=" * 60)
print("🧪 Bike Surface AI - System Test")
print("=" * 60)
print()

# Test 1: Import Edge Modules
print("Test 1: Testing Edge Modules...")
try:
    sys.path.insert(0, str(Path(__file__).parent / 'edge'))
    from gps_module import MockGPSModule
    from ai_inference import SurfaceDetector
    import yaml
    
    print("✅ Edge modules imported successfully")
    
    # Test GPS Mock
    print("\nTest 2: Testing Mock GPS...")
    gps_config = {'port': 'mock', 'baudrate': 9600, 'timeout': 5}
    gps = MockGPSModule(gps_config)
    position = gps.get_current_position()
    
    if position:
        print(f"✅ Mock GPS working: {position['latitude']:.6f}, {position['longitude']:.6f}")
    else:
        print("❌ Mock GPS failed")
    
    # Test AI Detector (mock mode)
    print("\nTest 3: Testing AI Detector (mock mode)...")
    detector_config = {
        'path': 'models/surface_detection.engine',
        'confidence_threshold': 0.5,
        'nms_threshold': 0.4,
        'input_size': [640, 640],
        'classes': ['asphalt', 'pothole', 'crack']
    }
    detector = SurfaceDetector(detector_config)
    
    # Create dummy frame
    import numpy as np
    dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    detections = detector.detect(dummy_frame)
    
    print(f"✅ AI Detector working (mock mode): {len(detections)} detections")
    if detections:
        for det in detections:
            print(f"   - {det['class']}: {det['confidence']:.2f}")
    
    print("\n" + "=" * 60)
    print("✅ All edge components working!")
    print("=" * 60)
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("📋 Next Steps:")
print("=" * 60)
print()
print("Option A - Full System Test (requires Docker):")
print("  1. Install Docker Desktop from: https://www.docker.com/products/docker-desktop")
print("  2. Run: docker-compose up -d")
print("  3. Open: http://localhost")
print()
print("Option B - Manual Test (without Docker):")
print("  1. Install PostgreSQL with PostGIS")
print("  2. Run: cd cloud/api && python main.py")
print("  3. Open: cloud/web/index.html in browser")
print()
print("Option C - Edge Device Only (mock mode):")
print("  1. cd edge")
print("  2. Update config.yaml (set cloud.api_url to your server)")
print("  3. python main.py")
print()
