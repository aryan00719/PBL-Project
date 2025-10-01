import requests
from app import City, Site, db, app   # also import app

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

if __name__ == "__main__":
    with app.app_context():  # ✅ important
        add_site("Mysore", "Karnataka", "South India", "Mysore Palace", "Palace", ticket_price=70, best_time="Oct–Mar")
        add_site("Mysore", "Karnataka", "South India", "Brindavan Gardens", "Garden")
        add_site("Mysore", "Karnataka", "South India", "Chamundi Hill", "Temple")
        add_site("Ooty", "Tamil Nadu", "South India", "Ooty Lake", "Lake")
        add_site("Ooty", "Tamil Nadu", "South India", "Botanical Garden", "Park")