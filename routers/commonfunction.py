import math

def calculate_distance(lat1, lon1, lat2, lon2):
    """
    Returns distance in kilometers between two lat/lon points.
    """
    R = 6371  # Earth radius in km
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
        * math.sin(d_lon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def calculate_delivery_fee(distance_km: float) -> float:
    """
    Calculates the delivery fee based on distance.
    - Base delivery fee: ₹20 for the first 1 km
    - ₹5 for each km after that
    """
    BASE_DELIVERY_FEE = 20
    FEE_PER_KM = 5

    # if distance <= 1 km, charge only base fee
    if distance_km <= 1:
        return BASE_DELIVERY_FEE

    # add extra for distance beyond 1 km
    extra_fee = (distance_km - 1) * FEE_PER_KM
    return round(BASE_DELIVERY_FEE + extra_fee, 2)