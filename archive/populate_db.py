import requests
import time

from app import City, Site, Hotel, db, app


# =========================
# Wikipedia API
# =========================
def fetch_wikipedia_details(place_name):
    url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{place_name.replace(' ', '_')}"
    headers = {"User-Agent": "AI-Travel-Itinerary-Planner/1.0 (student project)"}

    try:
        resp = requests.get(url, headers=headers, timeout=10)

        if resp.status_code != 200:
            return {
                "description": "Description not available",
                "image_url": None
            }

        data = resp.json()
        return {
            "description": data.get("extract", "No description available"),
            "image_url": data.get("thumbnail", {}).get("source")
        }

    except Exception as e:
        print(f"⚠️ Wikipedia error for {place_name}: {e}")
        return {"description": "No description", "image_url": None}


# =========================
# OpenStreetMap (Nominatim)
# =========================
def fetch_coordinates(place_name):
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": place_name,
        "format": "json",
        "limit": 1
    }
    headers = {
        "User-Agent": "AI-Travel-Itinerary-Planner/1.0 (student project)"
    }

    try:
        time.sleep(1)  # 🚨 REQUIRED by Nominatim usage policy
        resp = requests.get(url, params=params, headers=headers, timeout=10)

        if resp.status_code != 200:
            print(f"⚠️ Nominatim failed for {place_name}")
            return None, None

        data = resp.json()
        if data:
            return float(data[0]["lat"]), float(data[0]["lon"])

    except Exception as e:
        print(f"❌ Geocoding error for {place_name}: {e}")

    return None, None


# =========================
# City helper
# =========================
def get_or_create_city(name, state, region):
    city = City.query.filter_by(name=name).first()
    if not city:
        city = City(name=name, state=state, region=region)
        db.session.add(city)
        db.session.commit()
        print(f"🏙️ Added city {name}")
    return city


# =========================
# Insert Site
# =========================
def add_site(city_name, state, region, site_name,
             category="General", ticket_price=None, best_time=None):

    city = get_or_create_city(city_name, state, region)

    existing_site = Site.query.filter_by(
        name=site_name, city_id=city.id
    ).first()

    if existing_site:
        print(f"⚠️ Skipping site {site_name} in {city_name} (already exists)")
        return

    wiki = fetch_wikipedia_details(site_name)
    lat, lon = fetch_coordinates(f"{site_name}, {city_name}")

    site = Site(
        name=site_name,
        city_id=city.id,
        category=category,
        description=wiki["description"],
        latitude=lat,
        longitude=lon,
        ticket_price=ticket_price,
        best_time_to_visit=best_time,
        image_url=wiki["image_url"]
    )

    db.session.add(site)
    db.session.commit()
    print(f"✅ Added site {site_name} in {city_name}")


# =========================
# Insert Hotel
# =========================
def add_hotel(city_name, name, lat=None, lon=None,
              rating=None, price_range=None, image_url=None):

    city = City.query.filter_by(name=city_name).first()
    if not city:
        print(f"⚠️ City {city_name} not found. Cannot add hotel {name}.")
        return

    existing_hotel = Hotel.query.filter_by(
        name=name, city_id=city.id
    ).first()

    if existing_hotel:
        print(f"⚠️ Skipping hotel {name} in {city_name} (already exists)")
        return

    if lat is None or lon is None:
        lat, lon = fetch_coordinates(f"{name}, {city_name}")

    if image_url is None:
        wiki = fetch_wikipedia_details(name)
        image_url = wiki.get("image_url")

    hotel = Hotel(
        name=name,
        city_id=city.id,
        latitude=lat,
        longitude=lon,
        rating=rating,
        price_range=price_range,
        image_url=image_url
    )

    db.session.add(hotel)
    db.session.commit()
    print(f"🏨 Added hotel {name} in {city_name}")


# =========================
# MAIN ENTRY
# =========================
if __name__ == "__main__":
    with app.app_context():
        print("ℹ️ Populating database (safe mode, duplicates skipped)\n")

        # -------- Mysore --------
        add_site("Mysore", "Karnataka", "South India",
                 "Mysore Palace", "Palace", ticket_price=70, best_time="Oct–Mar")
        add_site("Mysore", "Karnataka", "South India",
                 "Brindavan Gardens", "Garden")
        add_site("Mysore", "Karnataka", "South India",
                 "Chamundi Hill", "Temple")

        add_hotel("Mysore", "Radisson Blu Plaza Hotel Mysore",
                  rating=4.5, price_range="$$$")
        add_hotel("Mysore", "Royal Orchid Metropole Hotel",
                  rating=4.0, price_range="$$")

        # -------- Ooty --------
        add_site("Ooty", "Tamil Nadu", "South India",
                 "Ooty Lake", "Lake")
        add_site("Ooty", "Tamil Nadu", "South India",
                 "Botanical Garden", "Park")

        add_hotel("Ooty", "Savoy Hotel",
                  rating=4.2, price_range="$$$")
        add_hotel("Ooty", "Sterling Ooty Elk Hill",
                  rating=4.0, price_range="$$")

        # -------- Jaipur --------
        get_or_create_city("Jaipur", "Rajasthan", "North India")
        add_hotel("Jaipur", "Taj Jai Mahal Palace",
                  rating=4.7, price_range="$$$$")
        add_hotel("Jaipur", "ITC Rajputana",
                  rating=4.3, price_range="$$$")

        # -------- Delhi --------
        get_or_create_city("Delhi", "Delhi", "North India")
        add_hotel("Delhi", "The Leela Palace New Delhi",
                  rating=4.8, price_range="$$$$")
        add_hotel("Delhi", "Taj Mahal Hotel",
                  rating=4.6, price_range="$$$$")

        print("\n✅ Database population completed.")