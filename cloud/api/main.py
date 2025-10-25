"""
Cloud API for Bike Surface AI
FastAPI backend for receiving detection data and serving to frontend.
"""

from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import asyncpg
import json
from datetime import datetime
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Bike Surface AI API",
    description="API for road surface condition detection and mapping",
    version="1.0.0"
)

# CORS middleware for web frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database configuration
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:password@localhost:5432/bike_surface_db"
)

# Connection pool
db_pool = None


# Pydantic models
class Detection(BaseModel):
    timestamp: float = Field(..., description="Unix timestamp of detection")
    latitude: float = Field(..., ge=-90, le=90, description="Latitude coordinate")
    longitude: float = Field(..., ge=-180, le=180, description="Longitude coordinate")
    altitude: Optional[float] = Field(None, description="Altitude in meters")
    speed: Optional[float] = Field(None, description="Speed in km/h")
    detections: List[Dict[str, Any]] = Field(..., description="List of detected objects")


class UploadRequest(BaseModel):
    detections: List[Detection]
    device_id: Optional[str] = None


class RideResponse(BaseModel):
    ride_id: int
    start_time: datetime
    end_time: Optional[datetime]
    total_detections: int
    device_id: Optional[str]
    geojson: Dict[str, Any]


class StatsResponse(BaseModel):
    total_rides: int
    total_detections: int
    surface_types: Dict[str, int]
    damage_types: Dict[str, int]


# Database connection management
@app.on_event("startup")
async def startup():
    """Initialize database connection pool"""
    global db_pool
    try:
        db_pool = await asyncpg.create_pool(
            DATABASE_URL,
            min_size=5,
            max_size=20
        )
        logger.info("Database connection pool created")
        
        # Test connection
        async with db_pool.acquire() as conn:
            version = await conn.fetchval("SELECT version()")
            logger.info(f"Connected to database: {version}")
    
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")
        raise


@app.on_event("shutdown")
async def shutdown():
    """Close database connection pool"""
    global db_pool
    if db_pool:
        await db_pool.close()
        logger.info("Database connection pool closed")


async def get_db_connection():
    """Get database connection from pool"""
    async with db_pool.acquire() as connection:
        yield connection


# API Endpoints
@app.get("/")
async def root():
    """API root endpoint"""
    return {
        "name": "Bike Surface AI API",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "upload": "/upload",
            "rides": "/rides",
            "ride_detail": "/rides/{ride_id}",
            "stats": "/stats",
            "health": "/health"
        }
    }


@app.post("/upload", response_model=Dict[str, Any])
async def upload_detections(request: UploadRequest):
    """
    Upload detection data from edge device
    
    Args:
        request: UploadRequest containing list of detections
        
    Returns:
        Success status, ride_id, and count of detections
    """
    if not request.detections:
        raise HTTPException(status_code=400, detail="No detections provided")
    
    async with db_pool.acquire() as conn:
        try:
            # Start transaction
            async with conn.transaction():
                # Create new ride or get latest active ride
                ride_id = await create_or_get_ride(conn, request.device_id)
                
                # Insert detections
                inserted_count = 0
                for detection in request.detections:
                    await conn.execute("""
                        INSERT INTO detections 
                        (ride_id, timestamp, latitude, longitude, altitude, speed, detection_data)
                        VALUES ($1, $2, $3, $4, $5, $6, $7)
                    """,
                        ride_id,
                        datetime.fromtimestamp(detection.timestamp),
                        detection.latitude,
                        detection.longitude,
                        detection.altitude,
                        detection.speed,
                        json.dumps(detection.detections)
                    )
                    inserted_count += 1
                
                logger.info(f"Inserted {inserted_count} detections for ride {ride_id}")
                
                return {
                    "status": "success",
                    "ride_id": ride_id,
                    "count": inserted_count,
                    "message": f"Successfully uploaded {inserted_count} detections"
                }
        
        except Exception as e:
            logger.error(f"Error uploading detections: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@app.get("/rides", response_model=List[RideResponse])
async def get_rides(
    limit: int = Query(10, ge=1, le=100, description="Maximum number of rides to return"),
    offset: int = Query(0, ge=0, description="Number of rides to skip")
):
    """
    Get all rides with their detection data as GeoJSON
    
    Args:
        limit: Maximum number of rides to return
        offset: Number of rides to skip
        
    Returns:
        List of rides with GeoJSON data
    """
    async with db_pool.acquire() as conn:
        try:
            rides = await conn.fetch("""
                SELECT 
                    r.id,
                    r.start_time,
                    r.end_time,
                    r.device_id,
                    COUNT(d.id) as total_detections,
                    COALESCE(
                        json_agg(
                            json_build_object(
                                'type', 'Feature',
                                'geometry', json_build_object(
                                    'type', 'Point',
                                    'coordinates', json_build_array(d.longitude, d.latitude)
                                ),
                                'properties', json_build_object(
                                    'timestamp', extract(epoch from d.timestamp),
                                    'detections', d.detection_data,
                                    'altitude', d.altitude,
                                    'speed', d.speed
                                )
                            ) ORDER BY d.timestamp
                        ) FILTER (WHERE d.id IS NOT NULL),
                        '[]'::json
                    ) as features
                FROM rides r
                LEFT JOIN detections d ON r.id = d.ride_id
                GROUP BY r.id, r.start_time, r.end_time, r.device_id
                ORDER BY r.start_time DESC
                LIMIT $1 OFFSET $2
            """, limit, offset)
            
            result = []
            for ride in rides:
                # Parse features from JSON
                features = ride['features'] if ride['features'] else []
                
                geojson = {
                    "type": "FeatureCollection",
                    "features": features
                }
                
                result.append(RideResponse(
                    ride_id=ride['id'],
                    start_time=ride['start_time'],
                    end_time=ride['end_time'],
                    total_detections=ride['total_detections'],
                    device_id=ride['device_id'],
                    geojson=geojson
                ))
            
            logger.info(f"Retrieved {len(result)} rides")
            return result
        
        except Exception as e:
            logger.error(f"Error retrieving rides: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@app.get("/rides/{ride_id}", response_model=RideResponse)
async def get_ride_detail(ride_id: int):
    """
    Get detailed information for a specific ride
    
    Args:
        ride_id: ID of the ride to retrieve
        
    Returns:
        Ride details with GeoJSON data
    """
    async with db_pool.acquire() as conn:
        try:
            ride = await conn.fetchrow("""
                SELECT 
                    r.id,
                    r.start_time,
                    r.end_time,
                    r.device_id,
                    COUNT(d.id) as total_detections,
                    COALESCE(
                        json_agg(
                            json_build_object(
                                'type', 'Feature',
                                'geometry', json_build_object(
                                    'type', 'Point',
                                    'coordinates', json_build_array(d.longitude, d.latitude)
                                ),
                                'properties', json_build_object(
                                    'timestamp', extract(epoch from d.timestamp),
                                    'detections', d.detection_data,
                                    'altitude', d.altitude,
                                    'speed', d.speed
                                )
                            ) ORDER BY d.timestamp
                        ) FILTER (WHERE d.id IS NOT NULL),
                        '[]'::json
                    ) as features
                FROM rides r
                LEFT JOIN detections d ON r.id = d.ride_id
                WHERE r.id = $1
                GROUP BY r.id, r.start_time, r.end_time, r.device_id
            """, ride_id)
            
            if not ride:
                raise HTTPException(status_code=404, detail=f"Ride {ride_id} not found")
            
            features = ride['features'] if ride['features'] else []
            
            geojson = {
                "type": "FeatureCollection",
                "features": features
            }
            
            return RideResponse(
                ride_id=ride['id'],
                start_time=ride['start_time'],
                end_time=ride['end_time'],
                total_detections=ride['total_detections'],
                device_id=ride['device_id'],
                geojson=geojson
            )
        
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error retrieving ride {ride_id}: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@app.get("/stats", response_model=StatsResponse)
async def get_stats():
    """
    Get overall statistics about rides and detections
    
    Returns:
        Statistics including total rides, detections, and type counts
    """
    async with db_pool.acquire() as conn:
        try:
            # Get total counts
            stats = await conn.fetchrow("""
                SELECT 
                    COUNT(DISTINCT r.id) as total_rides,
                    COUNT(d.id) as total_detections
                FROM rides r
                LEFT JOIN detections d ON r.id = d.ride_id
            """)
            
            # Get detection type counts
            detection_types = await conn.fetch("""
                SELECT 
                    jsonb_array_elements(d.detection_data::jsonb)->>'class' as class_name,
                    COUNT(*) as count
                FROM detections d
                WHERE d.detection_data IS NOT NULL
                GROUP BY class_name
                ORDER BY count DESC
            """)
            
            # Categorize into surface types and damage types
            surface_types = {}
            damage_types = {}
            
            surface_classes = {'asphalt', 'concrete', 'gravel', 'cobblestone', 'dirt'}
            
            for row in detection_types:
                class_name = row['class_name']
                count = row['count']
                
                if class_name in surface_classes:
                    surface_types[class_name] = count
                else:
                    damage_types[class_name] = count
            
            return StatsResponse(
                total_rides=stats['total_rides'],
                total_detections=stats['total_detections'],
                surface_types=surface_types,
                damage_types=damage_types
            )
        
        except Exception as e:
            logger.error(f"Error retrieving stats: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Check database connection
        async with db_pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        
        return {
            "status": "healthy",
            "database": "connected",
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "database": "disconnected",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }


async def create_or_get_ride(conn, device_id: Optional[str] = None) -> int:
    """
    Create a new ride or get the most recent active ride
    
    Args:
        conn: Database connection
        device_id: Optional device identifier
        
    Returns:
        Ride ID
    """
    # Check for recent active ride (within last hour)
    recent_ride = await conn.fetchrow("""
        SELECT id FROM rides 
        WHERE end_time IS NULL 
        AND start_time > NOW() - INTERVAL '1 hour'
        AND ($1::VARCHAR IS NULL OR device_id = $1)
        ORDER BY start_time DESC 
        LIMIT 1
    """, device_id)
    
    if recent_ride:
        return recent_ride['id']
    
    # Create new ride
    ride_id = await conn.fetchval("""
        INSERT INTO rides (start_time, device_id) 
        VALUES (NOW(), $1) 
        RETURNING id
    """, device_id)
    
    logger.info(f"Created new ride {ride_id} for device {device_id}")
    return ride_id


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
