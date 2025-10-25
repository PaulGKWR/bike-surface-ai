# 🚴 Bike Surface AI

A proof-of-concept system for detecting and mapping road and bicycle path surface conditions using computer vision and GPS. The system runs on an NVIDIA Jetson Orin Nano with a camera and GPS sensor, classifies surface types and detects damages, then visualizes the results on an interactive map.

## 🎯 Features

- **Real-time Surface Detection**: Identify different surface types (asphalt, concrete, gravel, cobblestone)
- **Damage Detection**: Detect road damages (potholes, cracks, patches, bumps, debris)
- **GPS Geotagging**: Every detection is tagged with precise GPS coordinates
- **Cloud Storage**: Data is stored in PostgreSQL with PostGIS for geographic queries
- **Interactive Map**: Web-based visualization using Leaflet.js
- **Edge Computing**: AI inference runs directly on Jetson Orin Nano with TensorRT optimization

## 📁 Project Structure

```
bike-surface-ai/
├── edge/                      # Edge device code (Jetson Orin Nano)
│   ├── main.py               # Main application entry point
│   ├── ai_inference.py       # YOLOv8/TensorRT inference
│   ├── gps_module.py         # GPS data acquisition
│   ├── config.yaml           # Edge device configuration
│   └── requirements.txt      # Python dependencies
│
├── cloud/                     # Cloud backend and frontend
│   ├── api/                  # FastAPI backend
│   │   ├── main.py          # API endpoints
│   │   ├── requirements.txt # Backend dependencies
│   │   ├── Dockerfile       # Container configuration
│   │   └── Procfile         # Deployment configuration
│   │
│   ├── db/                   # Database schema
│   │   └── schema.sql       # PostgreSQL + PostGIS schema
│   │
│   ├── web/                  # Frontend web interface
│   │   ├── index.html       # Main HTML page
│   │   ├── script.js        # JavaScript logic
│   │   └── style.css        # Styling
│   │
│   └── nginx/                # Nginx configuration
│       └── nginx.conf
│
├── training/                  # AI model training
│   ├── train.py              # YOLOv8 training script
│   ├── export_onnx.py        # Export model to ONNX
│   ├── convert_tensorrt.py   # Convert to TensorRT
│   └── yolov8_config.yaml    # Training configuration
│
├── docker-compose.yml         # Docker orchestration
├── .env.example              # Environment variables template
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

### Prerequisites

- **For Edge Device**: NVIDIA Jetson Orin Nano with JetPack 5.x or 6.x
- **For Cloud**: Docker and Docker Compose installed
- **For Training**: Python 3.8+, CUDA-capable GPU (optional)

### 1. Clone Repository

```bash
git clone https://github.com/yourusername/bike-surface-ai.git
cd bike-surface-ai
```

### 2. Setup Cloud Infrastructure

```bash
# Copy environment variables template
cp .env.example .env

# Edit .env with your database password
nano .env

# Start all services (database, API, web)
docker-compose up -d

# Check if services are running
docker-compose ps

# View logs
docker-compose logs -f
```

The web interface will be available at `http://localhost`
The API will be available at `http://localhost:8000`

### 3. Setup Edge Device (Jetson Orin Nano)

```bash
# Navigate to edge directory
cd edge

# Install Python dependencies
pip3 install -r requirements.txt

# Edit configuration
nano config.yaml
# Update cloud.api_url with your server URL
# Update gps.port with your GPS device port

# Run the edge system
python3 main.py
```

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
