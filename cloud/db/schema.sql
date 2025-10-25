-- Database Schema for Bike Surface AI
-- PostgreSQL with PostGIS extension for geographic data

-- Enable PostGIS extension for geographic data
CREATE EXTENSION IF NOT EXISTS postgis;

-- Rides table to group detection sessions
CREATE TABLE IF NOT EXISTS rides (
    id SERIAL PRIMARY KEY,
    start_time TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    end_time TIMESTAMP WITH TIME ZONE,
    device_id VARCHAR(100),
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Detections table to store individual surface/damage detections
CREATE TABLE IF NOT EXISTS detections (
    id SERIAL PRIMARY KEY,
    ride_id INTEGER NOT NULL REFERENCES rides(id) ON DELETE CASCADE,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    altitude DOUBLE PRECISION,
    speed DOUBLE PRECISION,
    detection_data JSONB NOT NULL, -- Store YOLO detection results
    location GEOGRAPHY(POINT, 4326), -- PostGIS geography column
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT valid_latitude CHECK (latitude >= -90 AND latitude <= 90),
    CONSTRAINT valid_longitude CHECK (longitude >= -180 AND longitude <= 180)
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_detections_location ON detections USING GIST (location);
CREATE INDEX IF NOT EXISTS idx_detections_ride_id ON detections (ride_id);
CREATE INDEX IF NOT EXISTS idx_detections_timestamp ON detections (timestamp);
CREATE INDEX IF NOT EXISTS idx_detections_data ON detections USING GIN (detection_data);
CREATE INDEX IF NOT EXISTS idx_rides_start_time ON rides (start_time);
CREATE INDEX IF NOT EXISTS idx_rides_device_id ON rides (device_id);

-- Trigger to automatically populate geography column from lat/lon
CREATE OR REPLACE FUNCTION update_detection_location()
RETURNS TRIGGER AS $$
BEGIN
    NEW.location = ST_SetSRID(ST_MakePoint(NEW.longitude, NEW.latitude), 4326)::geography;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_detection_location
    BEFORE INSERT OR UPDATE OF latitude, longitude ON detections
    FOR EACH ROW
    EXECUTE FUNCTION update_detection_location();

-- Trigger to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_rides_updated_at
    BEFORE UPDATE ON rides
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Surface types lookup table
CREATE TABLE IF NOT EXISTS surface_types (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    color_hex VARCHAR(7), -- For map visualization
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Insert default surface types
INSERT INTO surface_types (name, description, color_hex) VALUES
('asphalt', 'Standard asphalt road surface', '#333333'),
('concrete', 'Concrete pavement', '#888888'),
('gravel', 'Gravel or unpaved surface', '#8B4513'),
('cobblestone', 'Cobblestone or brick surface', '#CD853F'),
('dirt', 'Dirt or earth surface', '#DEB887')
ON CONFLICT (name) DO NOTHING;

-- Damage types lookup table
CREATE TABLE IF NOT EXISTS damage_types (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    severity_scale INTEGER DEFAULT 1 CHECK (severity_scale >= 1 AND severity_scale <= 5),
    color_hex VARCHAR(7), -- For map visualization
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Insert default damage types
INSERT INTO damage_types (name, description, severity_scale, color_hex) VALUES
('pothole', 'Hole or depression in surface', 4, '#FF0000'),
('crack', 'Surface cracking', 2, '#FFA500'),
('patch', 'Repair patch or different material', 1, '#FFFF00'),
('bump', 'Raised area or speed bump', 2, '#00FF00'),
('debris', 'Loose debris or obstacles', 3, '#FF1493')
ON CONFLICT (name) DO NOTHING;

-- View for aggregated statistics
CREATE OR REPLACE VIEW ride_statistics AS
SELECT 
    r.id as ride_id,
    r.start_time,
    r.end_time,
    r.device_id,
    COUNT(d.id) as total_detections,
    MIN(d.timestamp) as first_detection,
    MAX(d.timestamp) as last_detection,
    EXTRACT(EPOCH FROM (MAX(d.timestamp) - MIN(d.timestamp))) as duration_seconds,
    ST_MakeLine(d.location::geometry ORDER BY d.timestamp) as route_line
FROM rides r
LEFT JOIN detections d ON r.id = d.ride_id
GROUP BY r.id, r.start_time, r.end_time, r.device_id;

-- Function to get nearby detections
CREATE OR REPLACE FUNCTION get_nearby_detections(
    target_lat DOUBLE PRECISION,
    target_lon DOUBLE PRECISION,
    radius_meters DOUBLE PRECISION DEFAULT 100
)
RETURNS TABLE (
    detection_id INTEGER,
    distance_meters DOUBLE PRECISION,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    detection_data JSONB,
    timestamp TIMESTAMP WITH TIME ZONE
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        d.id,
        ST_Distance(
            d.location,
            ST_SetSRID(ST_MakePoint(target_lon, target_lat), 4326)::geography
        ) as distance,
        d.latitude,
        d.longitude,
        d.detection_data,
        d.timestamp
    FROM detections d
    WHERE ST_DWithin(
        d.location,
        ST_SetSRID(ST_MakePoint(target_lon, target_lat), 4326)::geography,
        radius_meters
    )
    ORDER BY distance;
END;
$$ LANGUAGE plpgsql;

-- Comments for documentation
COMMENT ON TABLE rides IS 'Stores information about individual bike rides/sessions';
COMMENT ON TABLE detections IS 'Stores individual surface and damage detections with geolocation';
COMMENT ON TABLE surface_types IS 'Lookup table for surface type classifications';
COMMENT ON TABLE damage_types IS 'Lookup table for damage type classifications';
COMMENT ON COLUMN detections.detection_data IS 'JSONB column storing YOLO detection results including class, confidence, and bounding box';
COMMENT ON COLUMN detections.location IS 'PostGIS geography point for spatial queries';
