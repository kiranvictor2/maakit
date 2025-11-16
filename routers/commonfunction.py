from math import radians, sin, cos, sqrt, atan2

# --------------------------------
# DISTANCE CALCULATION
# --------------------------------
def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371  # Earth radius in KM
    d_lat = radians(lat2 - lat1)
    d_lon = radians(lon2 - lon1)

    a = sin(d_lat / 2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(d_lon / 2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return R * c


# --------------------------------
# DELIVERY FEE RULE
# --------------------------------
def calculate_delivery_fee(distance_km: float):
    if distance_km <= 1:
        return 30
    elif distance_km <= 3:
        return 40
    elif distance_km <= 5:
        return 50
    else:
        return 60


# --------------------------------
# PLATFORM FINANCIAL BREAKUP
# --------------------------------
def calculate_financials(subtotal: float, delivery_fee: float,
                         platform_fee_percent=20, gst_percent=0):
    """
    subtotal = food price
    delivery_fee = customer pays
    platform_fee_percent = commission (default 20%)
    gst_percent = GST on commission (default 0 for your example)
    """

    platform_commission = round((platform_fee_percent / 100) * subtotal, 2)
    gst_amount = round((gst_percent / 100) * platform_commission, 2)
    delivery_payout = round(delivery_fee, 2)  # 100% to delivery partner
    chef_payout = round(subtotal - platform_commission, 2)

    customer_total = round(subtotal + delivery_fee + gst_amount, 2)

    return {
        "billing_summary": {
            "subtotal": round(subtotal, 2),
            "delivery_fee": round(delivery_fee, 2),
            "platform_commission": platform_commission,
            "gst_on_commission": gst_amount,
            "delivery_payout": delivery_payout,
            "chef_payout": chef_payout,
            "grand_total": customer_total,
        },
        "cash_flows": {
            "customer_pays": {
                "food": round(subtotal, 2),
                "delivery": round(delivery_fee, 2),
                "total": customer_total,
            },
            "maakitchen_revenue": {
                "commission": platform_commission,
                "gst_collected": gst_amount,
                "total_revenue": round(platform_commission + gst_amount, 2),
            },
            "delivery_partner": {
                "payout": delivery_payout,
            },
            "chef": {
                "receives": chef_payout,
            },
        }
    }
