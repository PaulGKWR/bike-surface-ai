# Bike Surface AI - Setup Guide

This guide will walk you through setting up the Bike Surface AI system from scratch.

## Table of Contents

1. [Hardware Setup](#hardware-setup)
2. [Cloud Infrastructure Setup](#cloud-infrastructure-setup)
3. [Edge Device Setup](#edge-device-setup)
4. [Model Training](#model-training)
5. [Testing and Validation](#testing-and-validation)

---

## 1. Hardware Setup

### Required Components

- **NVIDIA Jetson Orin Nano** (8GB recommended)
- **USB Camera** (720p or higher, 30fps)
- **Ublox NEO-M8U GPS Module** (USB connection)
- **MicroSD Card** (64GB or larger, Class 10 or better)
- **Power Supply** (USB-C PD, 15W or higher)
- **WiFi Dongle** (optional, for connectivity)

### Jetson Orin Nano Setup

1. **Flash JetPack to SD Card**
   ```bash
   # Download NVIDIA SDK Manager
   # Flash JetPack 5.1 or later
   # Follow: https://developer.nvidia.com/embedded/jetpack
   ```

2. **Initial Boot and Configuration**
   ```bash
   # Connect display, keyboard, mouse
   # Complete Ubuntu setup wizard
   # Set username and password
   
   # Update system
   sudo apt update
   sudo apt upgrade -y
   ```

3. **Enable Maximum Performance**
   ```bash
   # Set to maximum power mode
   sudo nvpmodel -m 0
   
   # Set clock speeds to maximum
   sudo jetson_clocks
   
   # Verify settings
   sudo nvpmodel -q
   ```

### GPS Module Setup

1. **Connect GPS Module**
   - Plug Ublox NEO-M8U into USB port
   - Check connection:
     ```bash
     ls /dev/ttyACM*
     # Should show: /dev/ttyACM0 (or similar)
     ```

2. **Test GPS Reception**
   ```bash
   # Install GPS tools
   sudo apt install gpsd gpsd-clients
   
   # Start GPS daemon
   sudo gpsd /dev/ttyACM0 -F /var/run/gpsd.sock
   
   # Monitor GPS data
   cgps
   # Wait for satellites (may take 5-10 minutes outdoors)
   ```

### Camera Setup

1. **Connect Camera**
   - Plug USB camera into available port
   - Check detection:
     ```bash
     ls /dev/video*
     # Should show: /dev/video0
     ```

2. **Test Camera**
   ```bash
   # Install tools
   sudo apt install v4l-utils
   
   # List camera capabilities
   v4l2-ctl --list-devices
   v4l2-ctl -d /dev/video0 --list-formats-ext
   
   # Test capture
   gst-launch-1.0 v4l2src device=/dev/video0 ! xvimagesink
   ```

---

## 2. Cloud Infrastructure Setup

### Option A: Docker Compose (Recommended)

1. **Install Docker**
   ```bash
   # Install Docker
   curl -fsSL https://get.docker.com -o get-docker.sh
   sudo sh get-docker.sh
   
   # Add user to docker group
   sudo usermod -aG docker $USER
   
   # Install Docker Compose
   sudo apt install docker-compose-plugin
   
   # Verify installation
   docker --version
   docker compose version
   ```

2. **Clone Repository**
   ```bash
   git clone https://github.com/yourusername/bike-surface-ai.git
   cd bike-surface-ai
   ```

3. **Configure Environment**
   ```bash
   # Copy environment template
   cp .env.example .env
   
   # Edit configuration
   nano .env
   # Change DB_PASSWORD to a secure password
   # Update CLOUD_API_URL if needed
   ```

4. **Start Services**
   ```bash
   # Start all services
   docker compose up -d
   
   # Check status
   docker compose ps
   
   # View logs
   docker compose logs -f
   
   # Stop services
   docker compose down
   ```

5. **Initialize Database**
   ```bash
   # Database schema is automatically initialized
   # Verify by connecting to database
   docker compose exec database psql -U postgres -d bike_surface_db
   
   # List tables
   \dt
   
   # Exit
   \q
   ```

6. **Test API**
   ```bash
   # Check health endpoint
   curl http://localhost:8000/health
   
   # Should return: {"status":"healthy","database":"connected",...}
   ```

7. **Access Web Interface**
   - Open browser: `http://localhost`
   - You should see the Bike Surface AI map interface

### Option B: Manual Setup

If you prefer not to use Docker:

1. **Install PostgreSQL with PostGIS**
   ```bash
   sudo apt install postgresql postgresql-contrib postgis
   
   # Create database and user
   sudo -u postgres psql
   CREATE DATABASE bike_surface_db;
   CREATE USER bikeuser WITH PASSWORD 'yourpassword';
   GRANT ALL PRIVILEGES ON DATABASE bike_surface_db TO bikeuser;
   \q
   
   # Enable PostGIS and load schema
   psql -U bikeuser -d bike_surface_db < cloud/db/schema.sql
   ```

2. **Setup Python Backend**
   ```bash
   cd cloud/api
   
   # Create virtual environment
   python3 -m venv venv
   source venv/bin/activate
   
   # Install dependencies
   pip install -r requirements.txt
   
   # Set environment variable
   export DATABASE_URL="postgresql://bikeuser:yourpassword@localhost:5432/bike_surface_db"
   
   # Run API
   python main.py
   ```

3. **Setup Web Server**
   ```bash
   # Install nginx
   sudo apt install nginx
   
   # Copy web files
   sudo cp -r cloud/web/* /var/www/html/
   
   # Configure nginx
   sudo cp cloud/nginx/nginx.conf /etc/nginx/nginx.conf
   
   # Restart nginx
   sudo systemctl restart nginx
   ```

---

## 3. Edge Device Setup

### On Jetson Orin Nano:

1. **Clone Repository**
   ```bash
   cd ~
   git clone https://github.com/yourusername/bike-surface-ai.git
   cd bike-surface-ai/edge
   ```

2. **Install Dependencies**
   ```bash
   # Install Python dependencies
   pip3 install -r requirements.txt
   
   # Note: TensorRT and CUDA are pre-installed with JetPack
   ```

3. **Configure Edge System**
   ```bash
   # Edit configuration
   nano config.yaml
   
   # Update these settings:
   # - gps.port: "/dev/ttyACM0" (your GPS device)
   # - camera.device_id: 0 (your camera device)
   # - cloud.api_url: "http://your-server-ip:8000"
   ```

4. **Create Models Directory**
   ```bash
   mkdir -p models
   ```

5. **Test Without Model (Mock Mode)**
   ```bash
   # Run in mock mode (no real model needed)
   python3 main.py
   
   # Press Ctrl+C to stop
   ```

---

## 4. Model Training

### Prepare Dataset

1. **Collect Images**
   - Take photos of roads with various surfaces and damages
   - Minimum 100-200 images per class
   - Vary lighting, angles, and conditions

2. **Label Images**
   - Use labeling tools like [LabelImg](https://github.com/heartexlabs/labelImg) or [Roboflow](https://roboflow.com)
   - Export in YOLO format
   - Organize as shown in training documentation

3. **Setup Dataset Structure**
   ```bash
   cd training
   mkdir -p datasets/surface_dataset/images/{train,val,test}
   mkdir -p datasets/surface_dataset/labels/{train,val,test}
   
   # Copy your labeled images and labels into these directories
   ```

4. **Create Dataset Config**
   ```bash
   # Edit dataset configuration
   nano datasets/surface_dataset.yaml
   
   # Update paths to match your dataset location
   ```

### Train Model

```bash
cd training

# Edit training configuration
nano yolov8_config.yaml

# Start training (requires GPU)
python train.py

# Training will save to: runs/detect/bike_surface_v1/
```

### Export and Convert

```bash
# Export to ONNX
python export_onnx.py

# Copy ONNX to Jetson (from your training machine)
scp models/surface_detection_best.onnx jetson@jetson-ip:~/bike-surface-ai/training/models/

# On Jetson, convert to TensorRT
cd ~/bike-surface-ai/training
python convert_tensorrt.py

# Copy engine to edge directory
cp models/surface_detection.engine ../edge/models/
```

---

## 5. Testing and Validation

### Test Edge System

```bash
cd ~/bike-surface-ai/edge

# Run edge system
python3 main.py

# System should:
# 1. Initialize GPS and wait for fix
# 2. Open camera
# 3. Start detection loop
# 4. Upload data to cloud

# Monitor logs for errors
tail -f edge_system.log
```

### Test Full Pipeline

1. **Start Edge System**
   ```bash
   python3 main.py
   ```

2. **Go for a Test Ride**
   - Mount Jetson on bicycle
   - Ensure GPS has clear sky view
   - Camera should face road surface
   - Ride for 5-10 minutes

3. **Check Cloud Dashboard**
   - Open browser to web interface
   - Click "Refresh Data"
   - Select your ride
   - Verify detections on map

### Troubleshooting

See main README.md for detailed troubleshooting steps.

---

## Next Steps

- **Collect more training data** to improve model accuracy
- **Tune detection thresholds** in config.yaml
- **Set up automatic startup** with systemd
- **Configure cloud hosting** for remote access
- **Add authentication** for production use

## Support

For issues or questions, please open an issue on GitHub.
