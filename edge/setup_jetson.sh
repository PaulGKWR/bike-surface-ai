#!/bin/bash
# Setup-Skript für Jetson Orin Nano - Bike Surface AI

set -e

echo "╔═══════════════════════════════════════════╗"
echo "║   Jetson Setup - Bike Surface AI         ║"
echo "╚═══════════════════════════════════════════╝"

# Farbcodes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "\n${YELLOW}1. Prüfe vorhandene Pakete...${NC}"
python3 -c "import tensorrt; print('✓ TensorRT:', tensorrt.__version__)"
python3 -c "import cv2; print('✓ OpenCV:', cv2.__version__)"
python3 -c "import numpy; print('✓ NumPy:', numpy.__version__)"

echo -e "\n${YELLOW}2. Installiere System-Pakete...${NC}"
sudo apt update
sudo apt install -y python3-pip python3-serial v4l-utils

echo -e "\n${YELLOW}3. Installiere Python-Pakete...${NC}"
pip3 install pyyaml requests pyserial pynmea2

echo -e "\n${YELLOW}4. Setze Berechtigungen für GPS und Kamera...${NC}"
sudo usermod -a -G dialout $USER
sudo usermod -a -G video $USER

echo -e "\n${YELLOW}5. Erstelle Desktop-Verknüpfungen...${NC}"
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

cat > ~/Desktop/Datensammlung.desktop <<EOL
[Desktop Entry]
Version=1.0
Type=Application
Name=Bike Surface - Datensammlung
Comment=GPS + Kamera Aufnahme für Training
Exec=bash -c 'cd ${SCRIPT_DIR} && ./start_collection.sh; exec bash'
Icon=camera-photo
Terminal=true
Categories=Application;
EOL

cat > ~/Desktop/Inferenz-Modus.desktop <<EOL
[Desktop Entry]
Version=1.0
Type=Application
Name=Bike Surface - Inferenz
Comment=Schadenerkennung mit trainiertem Modell
Exec=bash -c 'cd ${SCRIPT_DIR} && ./start_inference.sh; exec bash'
Icon=find-location
Terminal=true
Categories=Application;
EOL

chmod +x ~/Desktop/Datensammlung.desktop
chmod +x ~/Desktop/Inferenz-Modus.desktop
chmod +x ${SCRIPT_DIR}/start_collection.sh
chmod +x ${SCRIPT_DIR}/start_inference.sh

echo -e "\n${GREEN}╔═══════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║         Setup erfolgreich! ✓              ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════╝${NC}"

echo -e "\n${YELLOW}Hardware-Test durchführen:${NC}"
echo "  python3 ${SCRIPT_DIR}/test_hardware.py"

echo -e "\n${YELLOW}WICHTIG:${NC}"
echo "  Bitte melden Sie sich ab und wieder an, damit"
echo "  die Gruppen-Berechtigungen (dialout, video) aktiv werden."

echo -e "\n${GREEN}Danach können Sie die Desktop-Icons verwenden!${NC}"
