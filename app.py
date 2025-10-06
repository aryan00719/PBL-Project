from flask import Flask, jsonify, request, send_from_directory, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
import osmnx as ox
import os
import networkx as nx
import time
from pathlib import Path
import logging
import re
from dotenv import load_dotenv
import json
import requests

load_dotenv()

import google.generativeai as genai

genai.configure(api_key=os.getenv('GEMINI_API_KEY'))

gemini_model = genai.GenerativeModel('gemini-2.5-pro')

# Global geocode cache
geocode_cache = {}

# Fallback: main landmark for each city if AI returns empty places
CITY_LANDMARK_FALLBACK = {
    "mysore": "Mysore Palace",
    "coonoor": "Sim's Park",
    "ooty": "Ooty Lake",
    "coimbatore": "Marudhamalai Temple",
    "delhi": "Red Fort",
    "jaipur": "Hawa Mahal"
}

def get_gemini_response(prompt, retries=2):
    for attempt in range(retries):
        try:
            response = gemini_model.generate_content([prompt])
            return response.text
        except Exception as e:
            logging.error(f"Gemini API error on attempt {attempt+1}: {e}")
            time.sleep(2)
    return '{"city": "unknown", "places": [], "food": []}'

def normalize_itinerary(itinerary_raw):
    normalized = []

    for day in itinerary_raw:
        activities = day.get('activities', [])

        # If activities are a string, split into list
        if isinstance(activities, str):
            activities = [act.strip() for act in activities.split('\n') if act.strip()]

        normalized.append({
            "day": day.get("day", "Day X"),
            "activities": activities
        })

    return normalized


def geocode_place(place_name):
    if place_name.lower() in geocode_cache:
        return geocode_cache[place_name.lower()]

    url = f"https://nominatim.openstreetmap.org/search"
    params = {
        'q': place_name,
        'format': 'json',
        'limit': 1
    }
    headers = {'User-Agent': 'TravelMapApp/1.0'}
    try:
        response = requests.get(url, params=params, headers=headers)
        data = response.json()
        if data:
            # Conditional override for known incorrect results
            if place_name.lower() == "the residency" and "malaysia" in data[0].get("display_name", "").lower():
                logging.warning(f"Overriding bad geocode for '{place_name}' from Malaysia to Lucknow coordinates")
                coords = {
                    "lat": 26.8605,
                    "lng": 80.9466
                }
                geocode_cache[place_name.lower()] = coords
                return coords
            # Additional override for suspicious Malaysia coordinates
            elif (
                abs(float(data[0]['lat']) - 5.4156) < 0.01 and 
                abs(float(data[0]['lon']) - 100.3072) < 0.01
            ):
                logging.warning(f"Overriding suspicious coordinates for '{place_name}' from Malaysia to Lucknow coordinates")
                coords = {
                    "lat": 26.8605,
                    "lng": 80.9466
                }
                geocode_cache[place_name.lower()] = coords
                return coords
            # Override for known bad coordinates
            known_overrides = {
                "dilkusha kothi": {"lat": 26.8381, "lng": 80.9910},
                "rumi darwaza": {"lat": 26.8696, "lng": 80.9134},
                "vijay chowk": {"lat": 28.6145, "lng": 77.2038}
            }
            if place_name.lower() in known_overrides:
                logging.warning(f"Using manual override for '{place_name}'")
                coords = known_overrides[place_name.lower()]
                geocode_cache[place_name.lower()] = coords
                return coords
            coords = {
                "lat": float(data[0]['lat']),
                "lng": float(data[0]['lon'])
            }
            geocode_cache[place_name.lower()] = coords  # Cache the result
            return coords
        else:
            # Override for known bad coordinates (fallback if geocoding returns nothing)
            known_overrides = {
                "dilkusha kothi": {"lat": 26.8381, "lng": 80.9910},
                "rumi darwaza": {"lat": 26.8696, "lng": 80.9134},
                "vijay chowk": {"lat": 28.6145, "lng": 77.2038}
            }
            if place_name.lower() in known_overrides:
                logging.warning(f"Using manual override for '{place_name}' (no geocode result)")
                coords = known_overrides[place_name.lower()]
                geocode_cache[place_name.lower()] = coords
                return coords
            logging.warning(f"No geocode result for '{place_name}'. Attempting fallback...")
            fallback_coords = fallback_geocode(place_name)
            if fallback_coords:
                logging.info(f"Fallback geocode successful for '{place_name}' -> {fallback_coords}")
                geocode_cache[place_name.lower()] = fallback_coords
                return fallback_coords
            return None
    except Exception as e:
        logging.error(f"Geocoding failed for {place_name}: {e}")
        # Attempt override on error
        known_overrides = {
            "dilkusha kothi": {"lat": 26.8381, "lng": 80.9910},
            "rumi darwaza": {"lat": 26.8696, "lng": 80.9134},
            "vijay chowk": {"lat": 28.6145, "lng": 77.2038}
        }
        if place_name.lower() in known_overrides:
            logging.warning(f"Using manual override for '{place_name}' (exception in geocode)")
            coords = known_overrides[place_name.lower()]
            geocode_cache[place_name.lower()] = coords
            return coords
        logging.warning(f"Exception during geocode for '{place_name}'. Attempting fallback...")
        fallback_coords = fallback_geocode(place_name)
        if fallback_coords:
            logging.info(f"Fallback geocode successful for '{place_name}' -> {fallback_coords}")
            geocode_cache[place_name.lower()] = fallback_coords
            return fallback_coords
        return None


# Wikipedia API integration for place details
def get_place_details(place_name, lat, lng, max_retries=3, backoff_factor=1.5):
    """
    Fetch a description and thumbnail for a place from Wikipedia API.
    Returns a dict with 'description' and 'thumbnail' keys.
    Adds retry logic with exponential backoff for network resilience.
    Includes a User-Agent header to avoid 403 errors.
    """
    WIKI_HEADERS = {'User-Agent': 'TravelMapApp/1.0'}
    def _request_with_retries(url, params=None, timeout=5):
        attempt = 0
        delay = 1.0
        while attempt < max_retries:
            try:
                resp = requests.get(url, params=params, timeout=timeout, headers=WIKI_HEADERS)
                resp.raise_for_status()
                return resp
            except Exception as e:
                attempt += 1
                if attempt == max_retries:
                    raise
                logging.warning(f"Wikipedia API request failed (attempt {attempt}/{max_retries}): {e}. Retrying in {delay:.1f}s...")
                time.sleep(delay)
                delay *= backoff_factor
        raise RuntimeError("Wikipedia API request failed after retries")

    try:
        # Step 1: Search for the most relevant Wikipedia page
        search_url = "https://en.wikipedia.org/w/api.php"
        search_params = {
            "action": "query",
            "list": "search",
            "srsearch": place_name,
            "format": "json",
            "srlimit": 1
        }
        search_resp = _request_with_retries(search_url, params=search_params, timeout=5)
        search_data = search_resp.json()
        if not search_data.get("query", {}).get("search"):
            return {"description": "No description available.", "thumbnail": None}
        page_title = search_data["query"]["search"][0]["title"]

        # Step 2: Get summary and thumbnail for the found page
        summary_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{page_title.replace(' ', '_')}"
        summary_resp = _request_with_retries(summary_url, timeout=5)
        if summary_resp.status_code != 200:
            return {"description": "No description available.", "thumbnail": None}
        summary_data = summary_resp.json()
        desc = summary_data.get("extract", "No description available.")
        thumb = summary_data.get("thumbnail", {}).get("source")
        return {"description": desc, "thumbnail": thumb}
    except Exception as e:
        logging.warning(f"Wikipedia API error for '{place_name}': {e}")
        return {"description": "No description available.", "thumbnail": None}


# Additional fallback logic for unresolved places
def fallback_geocode(place_name):
    # Try a few simplifications and known landmarks
    simplified_names = [
        place_name.lower().split(",")[0].strip(),
        re.sub(r"\s*-\s*", " ", place_name.lower()),
        place_name.lower().replace("temple", "").replace("park", "").strip()
    ]
    known_fallbacks = {
        "mumbai gateway": {"lat": 18.9220, "lng": 72.8347},
        "gateway of india": {"lat": 18.9219841, "lng": 72.8346543},
        "taj mahal": {"lat": 27.1751, "lng": 78.0421},
        "kerala backwaters": {"lat": 9.7655, "lng": 76.6413},
        "ooty lake": {"lat": 11.4125, "lng": 76.6935},
        "sim's park": {"lat": 11.3531, "lng": 76.8142},
        "mysore palace": {"lat": 12.3051, "lng": 76.6551},
        "marina beach": {"lat": 13.0500, "lng": 80.2824},
        "india gate": {"lat": 28.6129, "lng": 77.2295},
        "charminar": {"lat": 17.3616, "lng": 78.4747},
        "victoria memorial": {"lat": 22.5448, "lng": 88.3426},
        "amber fort": {"lat": 26.9855, "lng": 75.8513},
        "city palace": {"lat": 26.9262, "lng": 75.8238},
        "jal mahal": {"lat": 26.9539, "lng": 75.8466},
        "jantar mantar": {"lat": 26.9258, "lng": 75.8236},
        "albert hall museum": {"lat": 26.9118, "lng": 75.8195},
        "lodhi garden": {"lat": 28.5916, "lng": 77.2195},
        "connaught place": {"lat": 28.6315, "lng": 77.2167},
        "raj ghat": {"lat": 28.6400, "lng": 77.2495},
        "akshardham": {"lat": 28.6127, "lng": 77.2773},
        "akshardham temple": {"lat": 28.6127, "lng": 77.2773},
        "lotus temple": {"lat": 28.5535, "lng": 77.2588},
        "humayun's tomb": {"lat": 28.5933, "lng": 77.2507},
        "chandni chowk": {"lat": 28.6564, "lng": 77.2303},
        "red fort": {"lat": 28.6562, "lng": 77.2410},
        "qutub minar": {"lat": 28.5245, "lng": 77.1855},
        "sim s park": {"lat": 11.3531, "lng": 76.8142},
        "mysore": {"lat": 12.2958, "lng": 76.6394},
        "coimbatore": {"lat": 11.0168, "lng": 76.9558},
        "ooty": {"lat": 11.4064, "lng": 76.6932},
        "coonoor": {"lat": 11.3544, "lng": 76.7956},
        "marudhamalai": {"lat": 11.0840, "lng": 76.8565},
        "marudhamalai temple": {"lat": 11.0840, "lng": 76.8565},
        "jaipur": {"lat": 26.9124, "lng": 75.7873},
        "delhi": {"lat": 28.6139, "lng": 77.2090},
        "lucknow": {"lat": 26.8467, "lng": 80.9462},
        "the residency": {"lat": 26.8605, "lng": 80.9466},
    }
    # Try exact match first
    for name in simplified_names + [place_name.lower()]:
        if name in known_fallbacks:
            logging.info(f"Fallback matched '{place_name}' as '{name}'")
            return known_fallbacks[name]
    # Try further simplification: remove words like 'the', 'of', etc.
    further = re.sub(r'\b(the|of|in|at|on|to|a|an|temple|park|palace|museum|fort|gate|beach|lake|garden|chowk|bazaar)\b', '', place_name.lower())
    further = re.sub(r"\s+", " ", further).strip()
    if further in known_fallbacks:
        logging.info(f"Further fallback matched '{place_name}' as '{further}'")
        return known_fallbacks[further]
    logging.debug(f"No fallback match found for '{place_name}'")
    return None


import shutil

# In-memory cache for the street network graphs (per city)
graph_cache = {}
GRAPH_DIR = Path('graph_cache')
GRAPH_DIR.mkdir(exist_ok=True)

# Initialize Flask app
app = Flask(__name__, static_folder='static')
CORS(app)

# Require JSON body for POST requests
@app.before_request
def check_json():
    if request.method == 'POST' and not request.is_json:
        return jsonify({'error': 'Expected JSON body'}), 415

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///travel.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
from flask_migrate import Migrate
migrate = Migrate(app, db)

# Set up logging
logging.basicConfig(level=logging.INFO)

# Settings for OSMNX and graph caching
ox.settings.log_console = True
ox.settings.use_cache = True
CACHE_TIMEOUT = 86400  # 24 hours

# Food suggestions based on places
FOOD_SUGGESTIONS = {
    "Red Fort": ["Butter Chicken", "Kebabs", "Lassi"],
    "Qutub Minar": ["Chole Bhature", "Jalebi"],
    "Karim's": ["Mutton Burra", "Sheermal"],
    "Paranthe Wali Gali": ["Aloo Paratha", "Rabri"],
    "Adventure Island": ["Bhel Puri", "Pani Puri"],
    "F9 Go Karting": ["Masala Chai", "Samosa"]
}


class Trip(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    prompt = db.Column(db.String(500), nullable=False)
    city = db.Column(db.String(100))
    places = db.Column(db.Text)    # JSON string
    food = db.Column(db.Text)      # JSON string
    itinerary = db.Column(db.Text) # JSON string
    timestamp = db.Column(db.DateTime, default=db.func.current_timestamp())

    def to_dict(self):
        return {
            'prompt': self.prompt,
            'city': self.city,
            'places': json.loads(self.places or '[]'),
            'food': json.loads(self.food or '[]'),
            'itinerary': json.loads(self.itinerary or '[]'),
            'timestamp': self.timestamp.strftime('%Y-%m-%d %H:%M')
        }

# ------------------------
# City and Site models
class City(db.Model):
    __tablename__ = 'cities'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    state = db.Column(db.String(100))
    region = db.Column(db.String(100))   # e.g., South India
    description = db.Column(db.Text)

    sites = db.relationship('Site', backref='city', lazy=True)


class Site(db.Model):
    __tablename__ = 'sites'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(150), nullable=False)
    city_id = db.Column(db.Integer, db.ForeignKey('cities.id'), nullable=False)
    category = db.Column(db.String(50))   # Palace, Temple, Lake, etc.
    description = db.Column(db.Text)
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    opening_hours = db.Column(db.String(100))
    ticket_price = db.Column(db.Float)
    best_time_to_visit = db.Column(db.String(100))
    image_url = db.Column(db.String(250))

# Hotel model

class Hotel(db.Model):
    __tablename__ = 'hotels'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    city_id = db.Column(db.Integer, db.ForeignKey('cities.id'), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    rating = db.Column(db.Float)
    price_range = db.Column(db.String(50))
    image_url = db.Column(db.String(250))

    city = db.relationship('City', backref='hotels')

# Function to load or cache graph using in-memory cache (per city)
def get_cached_graph(city="Delhi, India"):
    city_key = city.lower().replace(",", "").replace(" ", "_")
    if city_key in graph_cache:
        logging.info(f"Reusing in-memory graph for {city}")
        return graph_cache[city_key]

    graphml_path = GRAPH_DIR / f"{city_key}.graphml"

    if graphml_path.exists():
        age = time.time() - graphml_path.stat().st_mtime
        if age < CACHE_TIMEOUT:
            logging.info(f"Using cached graph for {city}")
            G = ox.load_graphml(graphml_path)
            graph_cache[city_key] = G
            return G
        else:
            logging.info(f"Cached graph for {city} is stale. Updating...")

    logging.info(f"Downloading new graph for {city}...")
    try:
        G = ox.graph_from_place(city, network_type='drive')
    except Exception as e:
        logging.warning(f"⚠️ graph_from_place failed for '{city}': {e}")
        # Attempt fallback using geocoded point
        point = geocode_place(city)
        if point:
            logging.info(f"🧭 Falling back to graph_from_point around: {point}")
            G = ox.graph_from_point((point['lat'], point['lng']), dist=7000, network_type='drive')
        else:
            raise RuntimeError(f"Could not geocode fallback point for '{city}'")

    ox.save_graphml(G, graphml_path)
    graph_cache[city_key] = G
    return G

# Function to calculate the optimal route based on places
def calculate_optimal_path(places, city="Delhi, India"):
    seen_coords = set()
    unique_places = []
    for place in places:
        coord_pair = (round(place['lat'], 5), round(place['lng'], 5))
        if coord_pair not in seen_coords:
            seen_coords.add(coord_pair)
            unique_places.append(place)
        else:
            logging.warning(f"Duplicate coordinates detected, skipping place: {place['name']}")

    places = unique_places

    if len(places) < 2:
        logging.error("Not enough unique valid locations to build a route.")
        return [], []

    G = get_cached_graph(city)
    full_route = []
    path_instructions = []

    for i in range(len(places) - 1):
        origin = (places[i]['lat'], places[i]['lng'])
        destination = (places[i + 1]['lat'], places[i + 1]['lng'])

        # Log before nearest_nodes call
        logging.info(f"Processing route: From {origin} to {destination}")

        try:
            from osmnx.distance import nearest_nodes

            # Use already projected graph from cache
            G_proj = G

            # Find nearest nodes directly using WGS84 (lat/lng)
            orig_node = nearest_nodes(G_proj, X=origin[1], Y=origin[0])
            dest_node = nearest_nodes(G_proj, X=destination[1], Y=destination[0])

            # Log node info and check for identical nodes
            if orig_node == dest_node:
                logging.warning(f"Origin and destination nodes are identical for {origin} to {destination}. Possible coordinate issue.")
            else:
                logging.info(f"Origin node: {orig_node}, Destination node: {dest_node}")

            # Handle missing nodes explicitly
            if orig_node is None or dest_node is None:
                logging.error(f"Failed to find nodes for: {origin} or {destination}. Skipping route segment.")
                continue

            route = nx.shortest_path(G_proj, orig_node, dest_node, weight='length')

            # Collect turn-by-turn instructions with merging and skipping logic
            import re as _re
            for i_route in range(len(route) - 1):
                u = route[i_route]
                v = route[i_route + 1]
                edge_data = G_proj.get_edge_data(u, v, default={})
                if not edge_data:
                    continue
                for key in edge_data:
                    edge = edge_data[key]
                    road_name = edge.get('name', 'Unnamed Road')
                    if isinstance(road_name, list):
                        road_name = ", ".join(road_name)
                    length = edge.get('length', 0)
                    # Skip short unnamed roads
                    if road_name == "Unnamed Road" and length < 50:
                        continue
                    try:
                        from_lat, from_lng = G_proj.nodes[u]['y'], G_proj.nodes[u]['x']
                        to_lat, to_lng = G_proj.nodes[v]['y'], G_proj.nodes[v]['x']
                        delta_lat = to_lat - from_lat
                        delta_lng = to_lng - from_lng
                        if abs(delta_lat) > abs(delta_lng):
                            direction = "north" if delta_lat > 0 else "south"
                        else:
                            direction = "east" if delta_lng > 0 else "west"
                        instruction = f"Go {direction} on {road_name} for {int(length)} m"
                    except:
                        instruction = f"{road_name} – {int(length)} m"
                    # Merge with previous if same road, ensuring last entry is a string
                    if path_instructions and isinstance(path_instructions[-1], str) and road_name in path_instructions[-1]:
                        prev = path_instructions.pop()
                        m = _re.search(r"(\d+)\s*m", prev)
                        old_len = int(m.group(1)) if m else 0
                        new_len = old_len + int(length)
                        merged = _re.sub(r"\d+\s*m", f"{new_len} m", prev)
                        path_instructions.append(str(merged))
                    else:
                        path_instructions.append(str(instruction))

            for node in route:
                full_route.append([G_proj.nodes[node]['y'], G_proj.nodes[node]['x']])

        except Exception as e:
            logging.error(f"Error processing route from {places[i]['name']} to {places[i + 1]['name']}: {e}")
            # Optionally, skip this route or add fallback

    # Insert start and end instructions if places exist
    if places:
        start_place = places[0]['name']
        end_place = places[-1]['name']
        if path_instructions:
            path_instructions.insert(0, f"Start at {start_place}")
            path_instructions.append(f"Arrive at {end_place}")

    return full_route, path_instructions

# Route to serve the frontend HTML
@app.route('/')
def serve_frontend():
    return render_template('index.html')

# Route to handle route requests and return results
@app.route('/api/route', methods=['POST'])
def handle_route_request():
    try:
        data = request.get_json()
        if not data or 'places' not in data:
            return jsonify({'error': 'Invalid request format'}), 400

        logging.info("Received route request: %s", data['places'])
        route_coords, _ = calculate_optimal_path(data['places'])

        suggestions = {
            place['name']: FOOD_SUGGESTIONS.get(place['name'], [])
            for place in data['places']
        }

        return jsonify({
            'status': 'success',
            'route': route_coords,
            'food_suggestions': suggestions
        })

    except Exception as e:
        logging.error("Error processing route: %s", str(e))
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/ai-route', methods=['POST'])
def ai_route():
    data = request.get_json()
    prompt = data.get('prompt', '').strip()
    hotel_location = data.get('hotel_location')  # optional: {'lat':.., 'lng':..}

    if not prompt:
        return jsonify({'status': 'error', 'message': 'No prompt provided'}), 400

    prompt = re.sub(r"\(.*?\)", "", prompt)
    prompt = prompt.replace("South India", "")
    prompt = re.sub(r"[-→]", ",", prompt)
    prompt = re.sub(r"\s+", " ", prompt).strip()

    requested_days = None
    match = re.search(r'(\d+)\s*[- ]?\s*day', prompt.lower())
    if match:
        requested_days = int(match.group(1))
        logging.info(f"[ai_route] Detected user-requested trip length: {requested_days} days (from prompt)")

    try:
        gemini_content = get_gemini_response(
            f"""From the user's travel request below, extract JSON like this:
{{
    "city": "...",
    "places": ["Place 1", "Place 2", ...],
    "food": ["Dish 1", ...],
    "itinerary": [
        {{ "day": "Day 1", "activities": [ {{ "place":"Place Name", "time":"09:00-11:00", "travel_mode":"Car", "notes":"..." }} ] }}
    ]
}}
IMPORTANT: Prefer places from the provided database list when possible, but you may suggest additional well-known attractions. Respond ONLY with pure JSON."""
        )

        logging.info("AI raw response: " + gemini_content)
        content_clean = gemini_content.strip()
        if content_clean.startswith("```") and content_clean.endswith("```"):
            content_clean = re.sub(r"^```(?:json)?\s*", "", content_clean)
            content_clean = re.sub(r"\s*```$", "", content_clean)
        try:
            parsed = json.loads(content_clean)
        except Exception as e:
            logging.error("Failed to parse AI response as JSON. Content: " + content_clean)
            parsed = {"city": "unknown", "places": [], "food": [], "itinerary": []}

        city = (parsed.get('city') or 'delhi').strip().lower()
        if not city:
            city = 'delhi'

        places_from_ai = parsed.get('places', []) or []
        food_list = parsed.get('food', []) or []
        raw_itinerary = parsed.get('itinerary', []) or []
        itinerary = normalize_itinerary(raw_itinerary) if raw_itinerary else []

        city_obj = City.query.filter(db.func.lower(City.name) == city).first()
        if not city_obj:
            city_obj = City(name=city.title(), state=None, region=None)
            db.session.add(city_obj)
            db.session.commit()
            logging.info(f"Created new city record for '{city_obj.name}'")

        db_sites = {s.name.lower(): s for s in Site.query.filter_by(city_id=city_obj.id).all()}
        selected_places = []
        for place_name in places_from_ai:
            key = place_name.strip().lower()
            site = db_sites.get(key)
            if site:
                if site.latitude is None or site.longitude is None:
                    coords = geocode_place(f"{site.name}, {city_obj.name}, {city_obj.state or ''}")
                    if coords:
                        site.latitude = coords['lat']
                        site.longitude = coords['lng']
                        try:
                            db.session.commit()
                            logging.info(f"Updated coordinates for DB site '{site.name}'")
                        except Exception:
                            db.session.rollback()
                if site.latitude is not None and site.longitude is not None:
                    selected_places.append({
                        'name': site.name,
                        'lat': site.latitude,
                        'lng': site.longitude,
                        'details': {'description': site.description, 'image_url': site.image_url}
                    })
                else:
                    logging.warning(f"Skipping DB site '{site.name}' due to missing coords after geocode attempt")
            else:
                coords = geocode_place(f"{place_name}, {city_obj.name}, {city_obj.state or ''}")
                if coords:
                    new_site = Site(
                        name=place_name.strip(),
                        city_id=city_obj.id,
                        category=None,
                        description=None,
                        latitude=coords['lat'],
                        longitude=coords['lng'],
                        image_url=None
                    )
                    try:
                        db.session.add(new_site)
                        db.session.commit()
                        db_sites[new_site.name.lower()] = new_site
                        logging.info(f"Inserted new site '{new_site.name}' into DB for city {city_obj.name}")
                        selected_places.append({
                            'name': new_site.name,
                            'lat': new_site.latitude,
                            'lng': new_site.longitude,
                            'details': {'description': new_site.description, 'image_url': new_site.image_url}
                        })
                    except Exception as e:
                        db.session.rollback()
                        logging.warning(f"Failed to insert new site '{place_name}' into DB: {e}")
                else:
                    logging.warning(f"Could not geocode Gemini-suggested place '{place_name}', skipping.")

        if len(selected_places) < 2:
            logging.warning("Not enough DB/Gemini combined places resolved; falling back to generic geocoding flow.")
            selected_places = []
            for place_name in places_from_ai:
                coords = geocode_place(place_name)
                if coords:
                    details = get_place_details(place_name, coords['lat'], coords['lng'])
                    selected_places.append({'name': place_name, 'lat': coords['lat'], 'lng': coords['lng'], 'details': details})

        days = []
        if itinerary and isinstance(itinerary, list) and isinstance(itinerary[0].get('activities', []), list):
            structured = False
            for day in itinerary:
                acts = day.get('activities', [])
                if acts and isinstance(acts[0], dict) and acts[0].get('place'):
                    structured = True
                    break
            if structured:
                for day in itinerary:
                    day_places = []
                    for act in day.get('activities', []):
                        pname = act.get('place') if isinstance(act, dict) else None
                        if not pname:
                            continue
                        match = next((p for p in selected_places if p['name'].lower() == pname.strip().lower()), None)
                        if match:
                            day_places.append(match)
                    days.append({'day': day.get('day', 'Day X'), 'places': day_places, 'activities': day.get('activities', [])})
            else:
                day_count = len(itinerary)
                if requested_days:
                    day_count = requested_days
                n = len(selected_places)
                base = n // max(1, day_count)
                rem = n % max(1, day_count)
                idx = 0
                for d in range(day_count):
                    num = base + (1 if d < rem else 0)
                    days.append({'day': f'Day {d+1}', 'places': selected_places[idx: idx+num], 'activities': []})
                    idx += num
        else:
            day_count = requested_days if requested_days else max(1, len(selected_places) // 2)
            n = len(selected_places)
            base = n // max(1, day_count)
            rem = n % max(1, day_count)
            idx = 0
            for d in range(day_count):
                num = base + (1 if d < rem else 0)
                days.append({'day': f'Day {d+1}', 'places': selected_places[idx: idx+num], 'activities': []})
                idx += num

        # ---- HOTEL INTEGRATION LOGIC ----
        hotel_point = None
        hotel_source = None
        # 1. Use user's hotel if provided
        if hotel_location and isinstance(hotel_location, dict):
            if hotel_location.get('lat') is not None and hotel_location.get('lng') is not None:
                hotel_point = {
                    'name': hotel_location.get('name', 'Hotel'),
                    'lat': float(hotel_location['lat']),
                    'lng': float(hotel_location['lng']),
                    'details': {}
                }
                hotel_source = "provided_by_user"
                logging.info(f"Hotel location provided by user: {hotel_point}")
        # 2. If not provided, look up default hotel for that city from DB
        if hotel_point is None:
            hotels_db = Hotel.query.filter_by(city_id=city_obj.id).all()
            valid_hotel = None
            for h in hotels_db:
                if h.latitude is not None and h.longitude is not None:
                    valid_hotel = h
                    break
            if valid_hotel:
                hotel_point = {
                    'name': valid_hotel.name,
                    'lat': valid_hotel.latitude,
                    'lng': valid_hotel.longitude,
                    'details': {'image_url': valid_hotel.image_url, 'rating': valid_hotel.rating}
                }
                hotel_source = "fetched_from_db"
                logging.info(f"Hotel fetched from DB for city '{city_obj.name}': {hotel_point}")
            else:
                hotel_source = "none_found"
                logging.info(f"No valid hotel found in DB for city '{city_obj.name}'.")
        # 3. If no hotel or missing coordinates, fallback to first site in day's itinerary

        day_routes = []
        all_instructions = []
        for day in days:
            place_list = day['places']
            # Determine start/end point for this day
            _hotel_point = hotel_point
            _hotel_source = hotel_source
            # If no hotel or coords missing, fallback to first site in day's itinerary
            if (_hotel_point is None or _hotel_point.get('lat') is None or _hotel_point.get('lng') is None):
                if place_list and place_list[0].get('lat') is not None and place_list[0].get('lng') is not None:
                    _hotel_point = place_list[0]
                    _hotel_source = "fallback_first_site"
                    logging.info(f"Hotel fallback: using first site '{_hotel_point['name']}' as start/end for {day.get('day')}")
                else:
                    _hotel_point = None
                    _hotel_source = "no_valid_start"
                    logging.warning(f"No valid hotel or site to use as route start/end for {day.get('day')}")

            # Always use hotel → places → hotel sequence (if possible)
            if _hotel_point:
                seq = [_hotel_point] + place_list + [_hotel_point]
            else:
                seq = place_list

            # Remove duplicates by coordinates, but always keep hotel at start and end
            unique_seq = []
            seen = set()
            for idx, p in enumerate(seq):
                if p.get('lat') is None or p.get('lng') is None:
                    continue
                key = (round(p['lat'], 5), round(p['lng'], 5))
                # Always allow hotel at start and end, but skip duplicate in between
                if idx == 0 or idx == len(seq) - 1:
                    unique_seq.append(p)
                elif key not in seen:
                    unique_seq.append(p)
                    seen.add(key)

            if len(unique_seq) < 2:
                logging.warning(f"Not enough points to route for {day.get('day')}.")
                day_routes.append({'day': day.get('day'), 'route': [], 'places': [p['name'] for p in unique_seq]})
                continue

            try:
                route_coords, instructions = calculate_optimal_path(unique_seq, city=city_obj.name + ", India")
            except Exception as e:
                logging.warning(f"Day routing failed for {day.get('day')}: {e}. Trying fallback using first place.")
                try:
                    first_place = unique_seq[0]['name'] if unique_seq else city_obj.name
                    route_coords, instructions = calculate_optimal_path(unique_seq, city=first_place)
                except Exception as e2:
                    logging.error(f"Fallback routing failed for {day.get('day')}: {e2}")
                    route_coords, instructions = [], []

            day_routes.append({'day': day.get('day'), 'route': route_coords, 'places': [p['name'] for p in unique_seq]})
            if instructions:
                all_instructions.extend([f"{day.get('day')}: {ins}" for ins in instructions])

        trip = Trip(prompt=prompt, city=city, places=json.dumps([p['name'] for p in selected_places]), food=json.dumps(food_list), itinerary=json.dumps(itinerary))
        try:
            db.session.add(trip)
            db.session.commit()
        except Exception:
            db.session.rollback()

        return jsonify({'status': 'success', 'days': day_routes, 'instructions': all_instructions, 'itinerary': itinerary})

    except Exception as e:
        logging.error('Full exception details: ' + str(e))
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/ai-itinerary', methods=['POST'])
def generate_itinerary():
    data = request.get_json()
    places = data.get('places', [])
    prompt = data.get('prompt', '') or ''
    if not places:
        return jsonify({'status': 'error', 'message': 'No places provided'}), 400

    # Try to detect "X-day" request from the user's prompt if present
    requested_days = None
    if prompt:
        match = re.search(r'(\d+)\s*[- ]?\s*day', prompt.lower())
        if match:
            requested_days = int(match.group(1))
            logging.info(f"[ai-itinerary] Detected user-requested trip length: {requested_days} days (from prompt)")

    try:
        prompt_text = (
            f"Create a detailed day-wise travel itinerary as a JSON array. "
            f"Each day should be an object like {{'day': 'Day X', 'activities': ['Activity 1', 'Activity 2', ...]}}. "
            f"For these places: {', '.join(places)}."
        )

        # Use Gemini to generate itinerary
        itinerary_text = get_gemini_response(prompt_text)
        logging.info("Gemini itinerary response: " + itinerary_text)
        try:
            parsed_itinerary = json.loads(itinerary_text)
            parsed_itinerary = normalize_itinerary(parsed_itinerary)
            if not isinstance(parsed_itinerary, list):
                raise ValueError("Itinerary not in list format.")
        except Exception as e:
            logging.warning("Parsing failed or invalid format. Fallback to simple itinerary.")
            parsed_itinerary = []
            n_places = len(places)
            if requested_days:
                day_count = requested_days
                logging.info(f"[ai-itinerary] Using user-requested days: {day_count}")
                base = n_places // day_count
                rem = n_places % day_count
                idx = 0
                for day in range(day_count):
                    num_places = base + (1 if day < rem else 0)
                    activities = []
                    for _ in range(num_places):
                        if idx >= n_places:
                            break
                        place = places[idx]
                        activities.extend([
                            f"Visit {place}",
                            f"Explore nearby landmarks around {place}",
                            f"Sample local cuisine near {place}"
                        ])
                        idx += 1
                    parsed_itinerary.append({
                        "day": f"Day {day + 1}",
                        "activities": activities
                    })
            else:
                activities_per_day = 3
                for idx, place in enumerate(places, start=1):
                    parsed_itinerary.append({
                        "day": f"Day {idx}",
                        "activities": [
                            f"Visit {place}",
                            f"Explore nearby landmarks around {place}",
                            f"Sample local cuisine near {place}"
                        ]
                    })
        
        # Optional fallback using OpenAI (commented):
        # client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        # response = client.chat.completions.create(
        #     model="gpt-3.5-turbo",
        #     messages=[
        #         {"role": "system", "content": "You are a travel assistant. Create a detailed day-wise itinerary."},
        #         {"role": "user", "content": prompt}
        #     ],
        #     temperature=0.3
        # )
        # itinerary_text = response.choices[0].message.content

        return jsonify({'status': 'success', 'itinerary': parsed_itinerary})

    except Exception as e:
        logging.error("Itinerary generation error: " + str(e))
        return jsonify({'status': 'error', 'message': 'Itinerary generation failed.'}), 500



# Route to get recent trips history
@app.route('/api/trips', methods=['GET'])
def get_trips():
    trips = Trip.query.order_by(Trip.timestamp.desc()).limit(10).all()
    return jsonify([t.to_dict() for t in trips])

# Route to serve a history page using a template
@app.route('/history')
def history_page():
    trips = Trip.query.order_by(Trip.timestamp.desc()).limit(10).all()
    return render_template('history.html', trips=[t.to_dict() for t in trips])

# Cleanup function for old .graphml files
def cleanup_old_graphs(max_age_seconds=86400):
    now = time.time()
    for file in GRAPH_DIR.glob("*.graphml"):
        if now - file.stat().st_mtime > max_age_seconds:
            logging.info(f"Deleting old graph file: {file.name}")
            file.unlink()

# ----------- NEW ROUTES: /sites/<city_name> and /cities -----------

# Return sites for a given city
@app.route('/sites/<city_name>')
def get_sites(city_name):
    city = City.query.filter_by(name=city_name).first()
    if not city:
        return {"error": "City not found"}, 404
    
    sites = Site.query.filter_by(city_id=city.id).all()
    
    return {
        "city": city.name,
        "sites": [
            {
                "id": s.id,
                "name": s.name,
                "category": s.category,
                "description": s.description,
                "latitude": s.latitude,
                "longitude": s.longitude,
                "ticket_price": s.ticket_price,
                "best_time_to_visit": s.best_time_to_visit,
                "image_url": s.image_url
            }
            for s in sites
        ]
    }


# Return a list of all available cities
@app.route('/cities')
def get_cities():
    cities = City.query.all()
    return {
        "cities": [
            {"id": c.id, "name": c.name, "state": c.state, "region": c.region}
            for c in cities
        ]
    }

# Return all cities with their sites embedded
@app.route('/cities_with_sites')
def get_cities_with_sites():
    cities = City.query.all()
    result = []
    for city in cities:
        city_dict = {
            "id": city.id,
            "name": city.name,
            "state": city.state,
            "region": city.region,
            "sites": []
        }
        for s in city.sites:
            city_dict["sites"].append({
                "id": s.id,
                "name": s.name,
                "category": s.category,
                "description": s.description,
                "latitude": s.latitude,
                "longitude": s.longitude,
                "ticket_price": s.ticket_price,
                "best_time_to_visit": s.best_time_to_visit,
                "image_url": s.image_url
            })
        result.append(city_dict)
    return jsonify({"cities": result})

if __name__ == '__main__':
    logging.info("Initializing Flask server...")
    get_cached_graph()  # Load or cache graph at the start
    cleanup_old_graphs()  # Clean up stale graph files older than 24 hours
    logging.info("Server is live at http://localhost:5050")
    app.run(host='0.0.0.0', port=5050, threaded=True)
