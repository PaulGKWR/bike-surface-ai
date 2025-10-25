# Edge device startup script
# Make executable: chmod +x start_edge.sh

#!/bin/bash

echo "Starting Bike Surface AI Edge System..."

# Navigate to edge directory
cd "$(dirname "$0")"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
else
    source venv/bin/activate
fi

# Check if GPS device exists
if [ ! -e "/dev/ttyACM0" ]; then
    echo "Warning: GPS device not found at /dev/ttyACM0"
    echo "Using mock GPS mode"
fi

# Check if camera exists
if [ ! -e "/dev/video0" ]; then
    echo "Warning: Camera not found at /dev/video0"
fi

# Check if model exists
if [ ! -f "models/surface_detection.engine" ] && [ ! -f "models/surface_detection.onnx" ]; then
    echo "Warning: No model found. Running in mock detection mode."
fi

# Run the edge system
echo "Starting edge system..."
python3 main.py

deactivate
