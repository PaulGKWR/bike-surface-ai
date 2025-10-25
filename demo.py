"""
Simple Demo - Bike Surface AI
Demonstrates route visualization from Ried to Baindlkirch with problem detection
"""

import json
from datetime import datetime
import random

print("=" * 60)
print("🚴 Bike Surface AI - Route Demo (Ried → Baindlkirch)")
print("=" * 60)
print()

def generate_route_waypoints():
    """Generate realistic waypoints for bike path along Kreisstraße AIC15 from Ried to Baindlkirch"""
    # Diese Koordinaten folgen der tatsächlichen Kreisstraße AIC15
    return [
        (48.2905, 11.0434),   # Start: Ried Ortsmitte
        (48.2915, 11.0425),   # Ausfahrt Ried Richtung Westen
        (48.2928, 11.0415),   # Weiter westlich
        (48.2945, 11.0408),   # Kreisstraße AIC15 nach Nordwesten
        (48.2962, 11.0402),   # Folgt AIC15 nordwestlich
        (48.2980, 11.0398),   # Weiter auf AIC15
        (48.2998, 11.0395),   # Mittlerer Abschnitt AIC15
        (48.3015, 11.0392),   # AIC15 verläuft weiter nordwestlich
        (48.3032, 11.0390),   # Kurve auf AIC15
        (48.3048, 11.0388),   # Annäherung Baindlkirch
        (48.3062, 11.0387),   # Ortseingang Baindlkirch
        (48.3075, 11.0386),   # Baindlkirch Ortsmitte
    ]

def interpolate_route(waypoints, points_per_segment=12):
    """Create smooth route by interpolating between waypoints"""
    route = []
    for i in range(len(waypoints) - 1):
        lat1, lon1 = waypoints[i]
        lat2, lon2 = waypoints[i + 1]
        
        for j in range(points_per_segment):
            t = j / points_per_segment
            lat = lat1 + (lat2 - lat1) * t
            lon = lon1 + (lon2 - lon1) * t
            route.append((lat, lon))
    
    route.append(waypoints[-1])
    return route

# Generate route
print("📍 Generating route from Ried to Baindlkirch...")
waypoints = generate_route_waypoints()
route_points = interpolate_route(waypoints)
print(f"   Route has {len(route_points)} points")
print()

# Simulate detection data
print("📊 Simulating Detection Data...")
print()

# Problem types (excluding "asphalt" which means good road)
problem_types = ['pothole', 'crack', 'patch', 'bump', 'gravel']
num_problems = 8  # Number of problems to detect along route

# Select random indices for problems
problem_indices = sorted(random.sample(range(len(route_points)), num_problems))

detections = []
detection_features = []  # For problem markers
route_coordinates = []   # For route line

start_time = datetime.now().timestamp()

for i, (lat, lon) in enumerate(route_points):
    is_problem = i in problem_indices
    
    # Add to route coordinates
    route_coordinates.append([lon, lat])
    
    if is_problem:
        # Create problem detection
        problem_class = random.choice(problem_types)
        confidence = random.uniform(0.65, 0.95)
        speed = random.uniform(10, 25)
        
        # Generate color-coded placeholder image URL
        color_map = {
            'pothole': 'FF0000',
            'crack': 'FFA500',
            'patch': 'FFFF00',
            'bump': '00FF00',
            'gravel': '8B4513'
        }
        bg_color = color_map.get(problem_class, '999999')
        image_url = f"https://placehold.co/400x300/{bg_color}/FFFFFF/png?text={problem_class.upper()}"
        
        detection = {
            'timestamp': start_time + i * 3,  # 3 seconds per point
            'latitude': lat,
            'longitude': lon,
            'altitude': random.uniform(420, 440),
            'speed': speed,
            'detections': [{
                'class': problem_class,
                'confidence': confidence,
                'bbox': [
                    random.randint(100, 300),
                    random.randint(100, 300),
                    random.randint(400, 600),
                    random.randint(400, 600)
                ],
                'image_url': image_url
            }]
        }
        detections.append(detection)
        
        # Create GeoJSON feature for problem marker
        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [lon, lat]
            },
            "properties": {
                "timestamp": detection['timestamp'],
                "time_formatted": datetime.fromtimestamp(detection['timestamp']).strftime('%H:%M:%S'),
                "detections": detection['detections'],
                "speed": speed,
                "problem_type": problem_class
            }
        }
        detection_features.append(feature)
        
        # Print detection
        print(f"⚠️  Problem {len(detections)}:")
        print(f"   Location: {lat:.6f}, {lon:.6f}")
        print(f"   Type: {problem_class}")
        print(f"   Confidence: {confidence:.1%}")
        print(f"   Speed: {speed:.1f} km/h")
        print()

# Create route LineString feature
route_feature = {
    "type": "Feature",
    "geometry": {
        "type": "LineString",
        "coordinates": route_coordinates
    },
    "properties": {
        "name": "Route: Ried → Baindlkirch",
        "distance_km": len(route_points) * 0.015,  # Rough estimate
        "status": "good" if len(detections) < 5 else "needs_attention"
    }
}

# Create GeoJSON with both route and problem markers
geojson = {
    "type": "FeatureCollection",
    "features": [route_feature] + detection_features
}

# Save to file
output_file = "demo_ride.geojson"
with open(output_file, 'w') as f:
    json.dump(geojson, f, indent=2)

print("=" * 60)
print(f"✅ Generated route with {len(detections)} problems detected")
print(f"💾 Saved to: {output_file}")
print("=" * 60)
print()

# Statistics
detection_types = {}
for det in detections:
    for d in det['detections']:
        class_name = d['class']
        detection_types[class_name] = detection_types.get(class_name, 0) + 1

print("📈 Detection Statistics:")
for class_name, count in sorted(detection_types.items(), key=lambda x: x[1], reverse=True):
    print(f"  {class_name}: {count}")

print()
print("=" * 60)
print("🗺️  Open demo_viewer.html to see the route!")
print("=" * 60)
