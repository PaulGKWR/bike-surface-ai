# 🚴 Bike Surface AI

A proof-of-concept system for detecting and mapping road and bicycle path surface conditions using computer vision and GPS. The system runs on an NVIDIA Jetson Orin Nano with a camera and GPS sensor, classifies surface types and detects damages, then visualizes the results on an interactive map.

## 🎯 Features

- **Real-time Surface Detection**: Identify different surface types (asphalt good/poor, cobblestone, gravel, paved, unpaved)
- **Damage Detection**: Detect road damages (potholes, cracks, patches, bumps, debris)
- **GPS Geotagging**: Every detection is tagged with precise GPS coordinates
- **Training Data Collection**: Web UI for capturing training images with GPS metadata
- **Live Inference Monitoring**: Real-time map visualization with color-coded routes and damage markers
- **Demo Mode**: Test system functionality with synthetic data without hardware
- **Edge Computing**: AI inference runs directly on Jetson Nano with YOLOv8/TensorRT
- **Interactive Web Interface**: Responsive Flask-based UI with Leaflet.js mapping

## 📁 Project Structure

```
bike-surface-ai/
├── edge/                      # Edge device code (Jetson Nano)
│   ├── web_ui.py             # Flask web server (training + live UI)
│   ├── simple_capture.py     # Training data collection
│   ├── auto_live_system.py   # Live inference system
│   ├── ai_inference.py       # YOLOv8/TensorRT inference
│   ├── gps_module.py         # GPS data acquisition
│   ├── config*.yaml          # Configuration files
│   ├── requirements.txt      # Python dependencies
│   ├── setup_jetson.sh       # Jetson setup script
│   ├── start_webui.sh        # Web UI launcher
│   ├── templates/            # Web UI templates
│   │   ├── index.html        # Training data collection UI
│   │   └── live_inference.html # Live monitoring UI
│   ├── data_collection/      # Training sessions (gitignored)
│   └── live_sessions/        # Live inference sessions (gitignored)
│
├── cloud/                     # Cloud backend and frontend (optional)
│   ├── api/                  # FastAPI backend
│   ├── db/                   # Database schema
│   ├── web/                  # Frontend web interface
│   └── nginx/                # Nginx configuration
│
├── training/                  # AI model training
│   ├── train.py              # YOLOv8 training script
│   ├── export_onnx.py        # Export model to ONNX
│   ├── convert_tensorrt.py   # Convert to TensorRT
│   └── yolov8_config.yaml    # Training configuration
│
├── ARCHITECTURE.md            # System architecture documentation
├── QUICKSTART.md              # Quick start guide
├── docker-compose.yml         # Docker orchestration (cloud)
└── README.md                 # This file
```

## 🛠️ Technology Stack

- **Edge Computing**: Python 3, OpenCV, YOLOv8, TensorRT, CUDA
- **GPS**: Ublox NEO-M8U, pyserial, pynmea2
- **Backend**: FastAPI, asyncpg, PostgreSQL, PostGIS
- **Frontend**: HTML5, JavaScript, Leaflet.js
- **Deployment**: Docker, Docker Compose, Nginx
- **Hardware**: NVIDIA Jetson Orin Nano, USB Camera, GPS module

## 🚀 Quick Start

See [QUICKSTART.md](QUICKSTART.md) for a fast setup guide or [ARCHITECTURE.md](ARCHITECTURE.md) for detailed system documentation.

### Prerequisites

- **For Edge Device**: NVIDIA Jetson Nano with JetPack 4.6+ or Jetson Orin Nano with JetPack 5.x/6.x
- **Hardware**: USB Camera (e.g., Logitech C920), GPS Module (e.g., Navilock 62756)
- **For Training**: Python 3.8+, CUDA-capable GPU (optional)

### 1. Clone Repository

```bash
git clone https://github.com/yourusername/bike-surface-ai.git
cd bike-surface-ai
```

### 2. Setup Edge Device (Jetson Nano)

```bash
cd edge

# Install dependencies
pip3 install -r requirements.txt

# Edit configuration
nano config_collection.yaml  # For training data collection
nano config_auto_live.yaml   # For live inference

# Start web UI
./start_webui.sh
# Or manually: python3 web_ui.py
```

The web interface will be available at `http://<jetson-ip>:5000`

### 3. Collect Training Data

1. Open browser: `http://<jetson-ip>:5000`
2. Click "Start Capture" to begin collecting images
3. Images are saved every 2 seconds with GPS coordinates
4. Click "Stop Capture" when done
5. Sessions saved to `data_collection/TIMESTAMP/`

### 4. Run Live Inference

1. Navigate to Live page in web UI
2. Toggle "Demo Mode" for testing (no hardware needed)
3. Click "Start Live System" to begin inference
4. View real-time route with color-coded surface types
5. Damage markers appear automatically

### 5. Optional: Setup Cloud Backend

```bash
# Copy environment variables template
cp .env.example .env

# Edit .env with your database password
nano .env

# Start all services (database, API, web)
docker-compose up -d
```

Cloud interface available at `http://localhost`

## 📊 Training Custom Model

### 1. Prepare Dataset

Organize your dataset in YOLO format:

```
datasets/surface_dataset/
├── images/
│   ├── train/
│   ├── val/
│   └── test/
└── labels/
    ├── train/
    ├── val/
    └── test/
```

Each image should have a corresponding `.txt` label file with format:
```
<class_id> <x_center> <y_center> <width> <height>
```

### 2. Train Model

```bash
cd training

# Edit training configuration
nano yolov8_config.yaml

# Start training
python train.py
```

Training will save models to `runs/detect/bike_surface_v1/`

### 3. Export to ONNX

```bash
python export_onnx.py
```

### 4. Convert to TensorRT (on Jetson)

```bash
# Copy ONNX model to Jetson
scp models/surface_detection_best.onnx jetson@jetson-ip:~/bike-surface-ai/training/models/

# On Jetson, convert to TensorRT
python convert_tensorrt.py
```

### 5. Deploy Model

```bash
# Copy TensorRT engine to edge directory
cp models/surface_detection.engine ../edge/models/

# Update config.yaml with model path
nano ../edge/config.yaml
```

## 🗺️ Using the Web Interface

### Training Data Collection Page

1. Open `http://<jetson-ip>:5000` in browser
2. Camera preview shows live feed
3. Click "Start Capture" to begin session
4. Images captured every 2 seconds with GPS metadata
5. View session statistics (images, distance, duration)
6. Browse previous sessions in session list
7. Download GeoJSON route data

### Live Inference Page

1. Navigate to Live page from navbar
2. **Demo Mode**: Toggle on for testing without hardware
   - Generates synthetic circular route around Ried bei Mering
   - Simulates surface types and damages
   - Perfect for UI testing and demonstrations
3. **Real Mode**: Toggle off to use actual hardware
   - Shows current GPS position
   - Click "Start Live System" to begin
   - Real-time map updates every 2 seconds
4. **Map Features**:
   - Color-coded route segments by surface type:
     - 🟢 Green: Good asphalt
     - 🟡 Yellow: Medium asphalt
     - 🔴 Red: Poor asphalt
     - 🔵 Blue: Cobblestone
     - 🟠 Orange: Gravel/Unpaved
   - Damage markers with severity colors:
     - 🟠 Orange: Low severity
     - 🟡 Yellow: Medium severity
     - 🔴 Red: High severity
   - Legend showing all surface types
   - Real-time statistics (distance, speed, images)
5. Click markers to see detection details

### API Endpoints

The web UI provides several REST endpoints:

- `GET /api/status` - Training session status
- `GET /api/live/status` - Live inference status or demo data
- `POST /api/live/start` - Start live inference system
- `POST /api/live/stop` - Stop live inference system
- `POST /api/live/demo` - Toggle demo mode
- `GET /api/gps/current` - Get current GPS position

## 🗺️ Using the Cloud Web Interface (Optional)

If you've deployed the cloud backend:

1. Open web browser and navigate to `http://your-server-ip`
2. Click "Refresh Data" to load rides
3. Select a ride from the dropdown menu
4. View detections on the map
5. Click markers to see detailed information
6. Use legend to understand detection types

## 🔧 Configuration

### Edge Device (`edge/config.yaml`)

```yaml
model:
  path: "models/surface_detection.engine"
  confidence_threshold: 0.5
  
gps:
  port: "/dev/ttyACM0"
  baudrate: 9600
  
camera:
  device_id: 0
  resolution: [1280, 720]
  fps: 10
  
cloud:
  api_url: "http://your-server:8000"
  upload_interval: 30
```

### Cloud API (`.env`)

```bash
DATABASE_URL=postgresql://postgres:password@database:5432/bike_surface_db
API_HOST=0.0.0.0
API_PORT=8000
```

## 📡 API Endpoints

- `GET /` - API information
- `POST /upload` - Upload detections from edge device
- `GET /rides` - Get all rides with GeoJSON data
- `GET /rides/{ride_id}` - Get specific ride details
- `GET /stats` - Get overall statistics
- `GET /health` - Health check endpoint

## 🐛 Troubleshooting

### Edge Device Issues

**GPS not working:**
```bash
# Check GPS device
ls /dev/ttyACM*

# Test GPS connection
sudo apt-get install gpsd gpsd-clients
sudo gpsd /dev/ttyACM0 -F /var/run/gpsd.sock
cgps
```

**Camera not detected:**
```bash
# List video devices
v4l2-ctl --list-devices

# Test camera
gst-launch-1.0 v4l2src device=/dev/video0 ! xvimagesink
```

**TensorRT errors:**
```bash
# Check JetPack version
sudo apt-cache show nvidia-jetpack

# Verify CUDA installation
nvcc --version
```

### Cloud Issues

**Database connection failed:**
```bash
# Check database logs
docker-compose logs database

# Connect to database manually
docker-compose exec database psql -U postgres -d bike_surface_db
```

**API not responding:**
```bash
# Check API logs
docker-compose logs api

# Restart API service
docker-compose restart api
```

## 🔒 Security Considerations

For production deployment:

1. Change default database password in `.env`
2. Enable HTTPS with SSL certificates
3. Implement API authentication (JWT tokens)
4. Configure firewall rules
5. Use environment-specific configurations
6. Regular security updates

## 📈 Performance Optimization

### Jetson Orin Nano

- Use TensorRT FP16 for faster inference
- Adjust camera FPS based on processing capability
- Enable NVIDIA power mode: `sudo nvpmodel -m 0`
- Monitor with: `tegrastats`

### Cloud Backend

- Enable PostgreSQL connection pooling
- Add database indexes for frequent queries
- Use CDN for static assets
- Implement caching (Redis)

## 🤝 Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [Ultralytics YOLOv8](https://github.com/ultralytics/ultralytics) for object detection
- [FastAPI](https://fastapi.tiangolo.com/) for the backend framework
- [Leaflet.js](https://leafletjs.com/) for map visualization
- [PostGIS](https://postgis.net/) for spatial database support

## 📧 Contact

For questions or support, please open an issue on GitHub.

---

**Note**: This is a proof-of-concept system. For production use, additional testing, validation, and safety measures are required.
