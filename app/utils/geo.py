from math import radians, cos, sin, asin, sqrt
from typing import Tuple

def calculate_distance(point1: Tuple[float, float], point2: Tuple[float, float]) -> float:
    """
    Calculate distance between two geographic points using Haversine formula
    Returns distance in miles
    
    Args:
        point1: (latitude, longitude)
        point2: (latitude, longitude)
    """
    lat1, lon1 = point1
    lat2, lon2 = point2
    
    # Convert to radians
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    
    # Haversine formula
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    
    # Radius of earth in miles
    r = 3956
    
    return c * r

def calculate_eta(distance_miles: float, average_speed_mph: float = 35) -> int:
    """
    Calculate estimated time of arrival in minutes
    
    Args:
        distance_miles: Distance to travel
        average_speed_mph: Average speed (default 35 mph for city driving)
    
    Returns:
        ETA in minutes
    """
    if distance_miles <= 0:
        return 0
    
    hours = distance_miles / average_speed_mph
    minutes = int(hours * 60)
    
    return max(1, minutes)  # Minimum 1 minute

def format_point_for_db(lat: float, lng: float) -> str:
    """
    Format geographic point for database insertion
    Returns WKT (Well-Known Text) format
    """
    return f"POINT({lng} {lat})"

def parse_point_from_db(point_str: str) -> Tuple[float, float]:
    """
    Parse geographic point from database
    Expects format: "POINT(lng lat)"
    Returns: (latitude, longitude)
    """
    # Remove "POINT(" and ")"
    coords = point_str.replace("POINT(", "").replace(")", "")
    lng, lat = map(float, coords.split())
    return (lat, lng)

def is_within_service_area(
    point: Tuple[float, float],
    center: Tuple[float, float],
    radius_miles: float
) -> bool:
    """
    Check if a point is within service area
    
    Args:
        point: (latitude, longitude) to check
        center: (latitude, longitude) of service area center
        radius_miles: Service area radius in miles
    
    Returns:
        True if point is within service area
    """
    distance = calculate_distance(point, center)
    return distance <= radius_miles

def get_bounds(
    center: Tuple[float, float],
    radius_miles: float
) -> dict:
    """
    Get bounding box for a circle around a center point
    Useful for map displays
    
    Returns:
        Dict with north, south, east, west bounds
    """
    # Approximate: 1 degree latitude ≈ 69 miles
    # Longitude varies by latitude
    lat, lng = center
    
    lat_delta = radius_miles / 69.0
    lng_delta = radius_miles / (69.0 * cos(radians(lat)))
    
    return {
        "north": lat + lat_delta,
        "south": lat - lat_delta,
        "east": lng + lng_delta,
        "west": lng - lng_delta
    }
