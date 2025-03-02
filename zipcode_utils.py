import math
import zipcodes

def haversine_distance(lat1, lon1, lat2, lon2):
    """
    Calculate the great circle distance between two points 
    on the earth (specified in decimal degrees)
    """
    # Convert decimal degrees to radians
    lat1, lon1, lat2, lon2 = map(math.radians, [float(lat1), float(lon1), float(lat2), float(lon2)])
    
    # Haversine formula
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    r = 3956  # Radius of earth in miles
    return c * r

def distance_between_zips(zip1, zip2):
    """Calculate distance between two ZIP codes using Haversine formula"""
    # Get ZIP code information
    zip1_info = zipcodes.matching(zip1)
    zip2_info = zipcodes.matching(zip2)
    
    # Check if both ZIP codes exist
    if not zip1_info or not zip2_info:
        return None
        
    # Get the first match (should be exact)
    zip1_info = zip1_info[0]
    zip2_info = zip2_info[0]
    
    # Extract latitude and longitude
    try:
        lat1, lon1 = zip1_info['lat'], zip1_info['long']
        lat2, lon2 = zip2_info['lat'], zip2_info['long']
        
        # Calculate distance
        return haversine_distance(lat1, lon1, lat2, lon2)
    except (KeyError, ValueError):
        return None

def is_valid_zipcode(zipcode):
    """Check if a ZIP code exists in the database"""
    return zipcodes.is_real(zipcode)

def get_zipcode_info(zipcode):
    """Get complete information for a ZIP code"""
    matches = zipcodes.matching(zipcode)
    if matches:
        return matches[0]
    return None

def format_location(zipcode):
    """Format location as City, State"""
    matches = zipcodes.matching(zipcode)
    if matches:
        info = matches[0]
        return f"{info['city']}, {info['state']}"
    return None

def get_location_info(zipcode):
    """Get formatted location (City, State) for a ZIP code"""
    info = get_zipcode_info(zipcode)
    if info:
        return f"{info['city']}, {info['state']}"
    return None