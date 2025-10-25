/**
 * Bike Surface AI - Frontend JavaScript
 * Handles map visualization, data loading, and user interactions
 */

// Configuration
const API_BASE_URL = 'http://localhost:8000';  // Change to your API URL
const DEFAULT_MAP_CENTER = [52.5200, 13.4050];  // Berlin, Germany
const DEFAULT_ZOOM = 13;

// Global variables
let map;
let markersLayer;
let routeLayer;
let currentRideData = null;

// Color mapping for detection types
const DETECTION_COLORS = {
    // Damages
    'pothole': '#FF0000',
    'crack': '#FFA500',
    'patch': '#FFFF00',
    'bump': '#00FF00',
    'debris': '#FF1493',
    // Surfaces
    'asphalt': '#333333',
    'concrete': '#888888',
    'gravel': '#8B4513',
    'cobblestone': '#CD853F',
    'dirt': '#DEB887'
};

/**
 * Initialize the map
 */
function initMap() {
    // Create map instance
    map = L.map('map').setView(DEFAULT_MAP_CENTER, DEFAULT_ZOOM);
    
    // Add tile layer (OpenStreetMap)
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors',
        maxZoom: 19
    }).addTo(map);
    
    // Create layer groups
    markersLayer = L.layerGroup().addTo(map);
    routeLayer = L.layerGroup().addTo(map);
    
    console.log('Map initialized');
}

/**
 * Load rides from API
 */
async function loadRides() {
    const loadingIndicator = document.getElementById('loading-indicator');
    const refreshBtn = document.getElementById('refresh-btn');
    
    try {
        loadingIndicator.style.display = 'inline';
        refreshBtn.disabled = true;
        
        const response = await fetch(`${API_BASE_URL}/rides?limit=50`);
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const rides = await response.json();
        console.log(`Loaded ${rides.length} rides`);
        
        // Update ride selector
        updateRideSelector(rides);
        
        // Load statistics
        loadStats();
        
        // If there are rides, load the first one
        if (rides.length > 0) {
            currentRideData = rides;
            displayRide();
        }
        
    } catch (error) {
        console.error('Error loading rides:', error);
        alert('Failed to load rides. Make sure the API is running.');
    } finally {
        loadingIndicator.style.display = 'none';
        refreshBtn.disabled = false;
    }
}

/**
 * Load statistics from API
 */
async function loadStats() {
    try {
        const response = await fetch(`${API_BASE_URL}/stats`);
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const stats = await response.json();
        
        // Update header statistics
        document.getElementById('total-rides').textContent = stats.total_rides;
        document.getElementById('total-detections').textContent = stats.total_detections;
        
        console.log('Statistics loaded:', stats);
        
    } catch (error) {
        console.error('Error loading stats:', error);
    }
}

/**
 * Update ride selector dropdown
 */
function updateRideSelector(rides) {
    const select = document.getElementById('ride-select');
    
    // Clear existing options except first
    select.innerHTML = '<option value="">Select a ride...</option>';
    
    // Add ride options
    rides.forEach((ride, index) => {
        const option = document.createElement('option');
        option.value = index;
        
        const date = new Date(ride.start_time);
        const formattedDate = date.toLocaleString();
        
        option.textContent = `Ride ${ride.ride_id} - ${formattedDate} (${ride.total_detections} detections)`;
        select.appendChild(option);
    });
}

/**
 * Display selected ride on map
 */
function displayRide() {
    const select = document.getElementById('ride-select');
    const selectedIndex = select.value;
    
    if (!selectedIndex || !currentRideData) {
        return;
    }
    
    const ride = currentRideData[selectedIndex];
    console.log('Displaying ride:', ride.ride_id);
    
    // Clear existing markers and routes
    clearMap();
    
    // Display ride information
    displayRideInfo(ride);
    
    // Add markers for each detection
    const features = ride.geojson.features;
    
    if (features.length === 0) {
        alert('No detections found for this ride');
        return;
    }
    
    const bounds = [];
    
    features.forEach((feature, index) => {
        const coords = feature.geometry.coordinates;
        const props = feature.properties;
        
        // Add to bounds
        bounds.push([coords[1], coords[0]]);
        
        // Create marker for each detection
        const detections = props.detections;
        
        detections.forEach(detection => {
            const marker = createDetectionMarker(
                coords[1],
                coords[0],
                detection,
                props
            );
            marker.addTo(markersLayer);
        });
    });
    
    // Draw route line
    if (bounds.length > 1) {
        const routeLine = L.polyline(bounds, {
            color: '#0066CC',
            weight: 3,
            opacity: 0.6
        }).addTo(routeLayer);
    }
    
    // Fit map to bounds
    if (bounds.length > 0) {
        map.fitBounds(bounds, { padding: [50, 50] });
    }
}

/**
 * Create a marker for a detection
 */
function createDetectionMarker(lat, lon, detection, properties) {
    const detectionClass = detection.class;
    const confidence = detection.confidence;
    const color = DETECTION_COLORS[detectionClass] || '#999999';
    
    // Create custom icon
    const icon = L.divIcon({
        className: 'custom-marker',
        html: `<div style="background-color: ${color}; width: 12px; height: 12px; border-radius: 50%; border: 2px solid white;"></div>`,
        iconSize: [16, 16],
        iconAnchor: [8, 8]
    });
    
    const marker = L.marker([lat, lon], { icon: icon });
    
    // Create popup content
    const popupContent = `
        <div class="detection-popup">
            <h4>${detectionClass}</h4>
            <p><strong>Confidence:</strong> ${(confidence * 100).toFixed(1)}%</p>
            <p><strong>Location:</strong> ${lat.toFixed(6)}, ${lon.toFixed(6)}</p>
            <p><strong>Time:</strong> ${new Date(properties.timestamp * 1000).toLocaleString()}</p>
            ${properties.speed ? `<p><strong>Speed:</strong> ${properties.speed.toFixed(1)} km/h</p>` : ''}
            ${properties.altitude ? `<p><strong>Altitude:</strong> ${properties.altitude.toFixed(1)} m</p>` : ''}
        </div>
    `;
    
    marker.bindPopup(popupContent);
    
    // Add click event to show details
    marker.on('click', () => {
        displayDetectionDetails(detection, properties);
    });
    
    return marker;
}

/**
 * Display ride information in info panel
 */
function displayRideInfo(ride) {
    const rideInfoDiv = document.getElementById('ride-info');
    
    const startTime = new Date(ride.start_time);
    const endTime = ride.end_time ? new Date(ride.end_time) : null;
    
    let duration = 'Ongoing';
    if (endTime) {
        const durationMs = endTime - startTime;
        const minutes = Math.floor(durationMs / 60000);
        duration = `${minutes} minutes`;
    }
    
    rideInfoDiv.innerHTML = `
        <div class="info-item">
            <strong>Ride ID:</strong> ${ride.ride_id}
        </div>
        <div class="info-item">
            <strong>Start Time:</strong> ${startTime.toLocaleString()}
        </div>
        ${endTime ? `<div class="info-item"><strong>End Time:</strong> ${endTime.toLocaleString()}</div>` : ''}
        <div class="info-item">
            <strong>Duration:</strong> ${duration}
        </div>
        <div class="info-item">
            <strong>Total Detections:</strong> ${ride.total_detections}
        </div>
        ${ride.device_id ? `<div class="info-item"><strong>Device:</strong> ${ride.device_id}</div>` : ''}
    `;
}

/**
 * Display detection details in info panel
 */
function displayDetectionDetails(detection, properties) {
    const detailsDiv = document.getElementById('detection-details');
    
    const timestamp = new Date(properties.timestamp * 1000);
    
    detailsDiv.innerHTML = `
        <div class="info-item">
            <strong>Type:</strong> ${detection.class}
        </div>
        <div class="info-item">
            <strong>Confidence:</strong> ${(detection.confidence * 100).toFixed(1)}%
        </div>
        <div class="info-item">
            <strong>Time:</strong> ${timestamp.toLocaleString()}
        </div>
        ${properties.speed ? `<div class="info-item"><strong>Speed:</strong> ${properties.speed.toFixed(1)} km/h</div>` : ''}
        ${properties.altitude ? `<div class="info-item"><strong>Altitude:</strong> ${properties.altitude.toFixed(1)} m</div>` : ''}
        <div class="info-item">
            <strong>Bounding Box:</strong> 
            ${detection.bbox ? detection.bbox.map(v => v.toFixed(0)).join(', ') : 'N/A'}
        </div>
    `;
}

/**
 * Clear all markers and routes from map
 */
function clearMap() {
    markersLayer.clearLayers();
    routeLayer.clearLayers();
    
    // Clear detection details
    const detailsDiv = document.getElementById('detection-details');
    detailsDiv.innerHTML = '<p class="info-placeholder">Click on a marker to view detection details</p>';
    
    console.log('Map cleared');
}

/**
 * Toggle legend panel visibility
 */
function toggleLegend() {
    const legendPanel = document.getElementById('legend-panel');
    legendPanel.classList.toggle('hidden');
}

/**
 * Initialize the application
 */
function init() {
    console.log('Initializing Bike Surface AI frontend...');
    
    // Initialize map
    initMap();
    
    // Load initial data
    loadRides();
    
    // Set up auto-refresh (every 30 seconds)
    setInterval(loadRides, 30000);
    
    console.log('Application initialized');
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init();
}
