from decimal import Decimal
from django.db.models import F


def update_property_prices():
    properties = Property.objects.all()

    for prop in properties:
        if prop.listing_type == "rent":
            base_price = Decimal(5000)  # Base rent price
            price = base_price + (prop.bedrooms * 15000) + (prop.bathrooms * 7500)
        else:  # Sale
            base_price = Decimal(500000)  # Base sale price
            price = base_price + (prop.bedrooms * 1000000) + (prop.bathrooms * 500000)

        # Square footage adjustment
        if prop.square_feet > 2500:
            price *= Decimal(1.2)  # 20% increase
        elif prop.square_feet >= 1000:
            price *= Decimal(1.1)  # 10% increase

        # Location factor adjustment
        city_factor = {
            "Nairobi": 1.3,  # 30% increase
            "Mombasa": 1.2,  # 20% increase
        }
        price *= Decimal(city_factor.get(prop.city, 1))  # Default 1 (no change)

        # Round price to nearest 1000
        price = round(price, -3)

        # Update property price
        prop.price = price
        prop.save()

    print("Property prices updated successfully.")


# Run the update function
update_property_prices()
