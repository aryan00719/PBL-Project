import requests
from app import City, Site, Hotel, db, app   # also import app and Hotel

# Wikipedia API
def fetch_wikipedia_details(place_name):
    try:
        url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{place_name.replace(' ', '_')}"
        resp = requests.get(url, headers={"User-Agent": "TravelMapBot/1.0"})
        data = resp.json()
        return {
            "description": data.get("extract", "No description available"),
            "image_url": data.get("thumbnail", {}).get("source")
        }
    except:
        return {"description": "No description", "image_url": None}

# OpenStreetMap API
def fetch_coordinates(place_name):
    url = "https://nominatim.openstreetmap.org/search"
    params = {"q": place_name, "format": "json", "limit": 1}
    headers = {"User-Agent": "TravelMapBot/1.0"}
    try:
        resp = requests.get(url, params=params, headers=headers).json()
        if resp:
            return float(resp[0]["lat"]), float(resp[0]["lon"])
    except:
        pass
    return None, None

# Insert site
def add_site(city_name, state, region, site_name, category="General", ticket_price=None, best_time=None):
    city = City.query.filter_by(name=city_name).first()
    if not city:
        city = City(name=city_name, state=state, region=region)
        db.session.add(city)
        db.session.commit()
    
    existing_site = Site.query.filter_by(name=site_name, city_id=city.id).first()
    if existing_site:
        print(f"⚠️ Skipping {site_name} in {city_name} (already exists)")
        return
    
    wiki = fetch_wikipedia_details(site_name)
    lat, lon = fetch_coordinates(site_name + ", " + city_name)
    
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
    print(f"✅ Added {site_name} in {city_name}")

# Insert hotel
def add_hotel(city_name, name, lat=None, lon=None, rating=None, price_range=None, image_url=None):
    city = City.query.filter_by(name=city_name).first()
    if not city:
        print(f"⚠️ City {city_name} not found. Cannot add hotel {name}.")
        return

    existing_hotel = Hotel.query.filter_by(name=name, city_id=city.id).first()
    if existing_hotel:
        print(f"⚠️ Skipping {name} hotel in {city_name} (already exists)")
        return

    if lat is None or lon is None:
        lat, lon = fetch_coordinates(name + ", " + city_name)
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
    print(f"✅ Added hotel {name} in {city_name}")

if __name__ == "__main__":
    with app.app_context():  # ✅ important
        # Check if both Site and Hotel tables are populated before inserting
        if Site.query.first() is not None and Hotel.query.first() is not None:
            print("⚠️ Database already populated with sites and hotels. Skipping insertions.")
        else:
            add_site("Mysore", "Karnataka", "South India", "Mysore Palace", "Palace", ticket_price=70, best_time="Oct–Mar")
            add_site("Mysore", "Karnataka", "South India", "Brindavan Gardens", "Garden")
            add_site("Mysore", "Karnataka", "South India", "Chamundi Hill", "Temple")
            add_site("Ooty", "Tamil Nadu", "South India", "Ooty Lake", "Lake")
            add_site("Ooty", "Tamil Nadu", "South India", "Botanical Garden", "Park")

            # Add sample hotels for Mysore
            add_hotel("Mysore", "Radisson Blu Plaza Hotel Mysore", rating=4.5, price_range="$$$")
            add_hotel("Mysore", "Royal Orchid Metropole Hotel", rating=4.0, price_range="$$")

            # Add sample hotels for Ooty
            add_hotel("Ooty", "Savoy Hotel", rating=4.2, price_range="$$$")
            add_hotel("Ooty", "Sterling Ooty Elk Hill", rating=4.0, price_range="$$")

            # Add sample hotels for Jaipur
            # Ensure city is added first if not present
            if not City.query.filter_by(name="Jaipur").first():
                city_jaipur = City(name="Jaipur", state="Rajasthan", region="North India")
                db.session.add(city_jaipur)
                db.session.commit()
            add_hotel("Jaipur", "Taj Jai Mahal Palace", rating=4.7, price_range="$$$$")
            add_hotel("Jaipur", "ITC Rajputana", rating=4.3, price_range="$$$")

            # Add sample hotels for Delhi
            if not City.query.filter_by(name="Delhi").first():
                city_delhi = City(name="Delhi", state="Delhi", region="North India")
                db.session.add(city_delhi)
                db.session.commit()
            add_hotel("Delhi", "The Leela Palace New Delhi", rating=4.8, price_range="$$$$")
            add_hotel("Delhi", "Taj Mahal Hotel", rating=4.6, price_range="$$$$")