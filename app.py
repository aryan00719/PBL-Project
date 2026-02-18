import os
import logging
import math
from typing import List, Dict, Any, Tuple

from flask import Flask, request, jsonify, render_template, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS

import networkx as nx
import osmnx as ox

from datetime import datetime
import math
from random import shuffle
import numpy as np
from sklearn.cluster import KMeans

from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

# --------------------------------------------------
# App & Config
# --------------------------------------------------

app = Flask(__name__)
CORS(app)

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
INSTANCE_DIR = os.path.join(BASE_DIR, "instance")
os.makedirs(INSTANCE_DIR, exist_ok=True)

database_url = os.environ.get("DATABASE_URL")

if database_url:
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
else:
    DB_PATH = os.path.join(INSTANCE_DIR, "travel.db")
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{DB_PATH}"

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret")

db = SQLAlchemy(app)

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

city_graph_cache = {}

# --------------------------------------------------
# Database Models
# --------------------------------------------------

class City(db.Model):
    __tablename__ = "cities"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    lat = db.Column(db.Float, nullable=False)
    lng = db.Column(db.Float, nullable=False)

    def __init__(self, name, lat, lng):
        self.name = name
        self.lat = lat
        self.lng = lng

class Site(db.Model):
    __tablename__ = "site"

    id = db.Column(db.Integer, primary_key=True)

    # Foreign Key
    city_id = db.Column(
        db.Integer,
        db.ForeignKey("cities.id"),
        nullable=False
    )

    # Basic Info
    name = db.Column(db.String(150), nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)

    # Classification
    category = db.Column(db.String(100))

    # Visiting Info
    opening_time = db.Column(db.String(50))
    closing_time = db.Column(db.String(50))
    visit_duration = db.Column(db.String(50))
    best_time_to_visit = db.Column(db.String(100))

    # Pricing
    ticket_price = db.Column(db.String(50))

    # Optional (Recommended for Popups)
    description = db.Column(db.Text)
    image_url = db.Column(db.String(255))

    # Relationship
    city = db.relationship("City", backref=db.backref("sites", lazy=True))

    def __init__(self, city_id, name, latitude, longitude, category=None, opening_time=None, closing_time=None, visit_duration=None, best_time_to_visit=None, ticket_price=None, description=None, image_url=None):
        self.city_id = city_id
        self.name = name
        self.latitude = latitude
        self.longitude = longitude
        self.category = category
        self.opening_time = opening_time
        self.closing_time = closing_time
        self.visit_duration = visit_duration
        self.best_time_to_visit = best_time_to_visit
        self.ticket_price = ticket_price
        self.description = description
        self.image_url = image_url


# --------------------------------------------------
# User Model
# --------------------------------------------------
class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

    def __init__(self, email, password):
        self.email = email
        self.password = password


class Trip(db.Model):
    __tablename__ = "trips"

    id = db.Column(db.Integer, primary_key=True)
    city = db.Column(db.String(100))
    days = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    user = db.relationship("User", backref=db.backref("trips", lazy=True))

    def __init__(self, city, days, user_id=None):
        self.city = city
        self.days = days
        self.user_id = user_id


def seed_data():
    # 1. Ensure Cities Exist
    jaipur = City.query.filter_by(name="Jaipur").first()
    if not jaipur:
        jaipur = City(name="Jaipur", lat=26.9124, lng=75.7873)
        db.session.add(jaipur)
        print("✅ Added city: Jaipur")

    delhi = City.query.filter_by(name="Delhi").first()
    if not delhi:
        delhi = City(name="Delhi", lat=28.6139, lng=77.2090)
        db.session.add(delhi)
        print("✅ Added city: Delhi")

    db.session.commit()

    # 2. Define Sites Data
    sites_data = [
        # --- JAIPUR ---
        {"city_id": jaipur.id, "name": "Hawa Mahal", "latitude": 26.9239, "longitude": 75.8267, "category": "Monument", "best_time_to_visit": "Morning"},
        {"city_id": jaipur.id, "name": "Amer Fort", "latitude": 26.9855, "longitude": 75.8513, "category": "Fort", "best_time_to_visit": "Morning"},
        {"city_id": jaipur.id, "name": "City Palace", "latitude": 26.9258, "longitude": 75.8237, "category": "Palace", "best_time_to_visit": "Afternoon"},
        {"city_id": jaipur.id, "name": "Jal Mahal", "latitude": 26.9535, "longitude": 75.8462, "category": "Lake Palace", "best_time_to_visit": "Evening"},
        {"city_id": jaipur.id, "name": "Nahargarh Fort", "latitude": 26.9368, "longitude": 75.8160, "category": "Fort", "best_time_to_visit": "Evening"},
        {"city_id": jaipur.id, "name": "Albert Hall Museum", "latitude": 26.9124, "longitude": 75.8196, "category": "Museum", "best_time_to_visit": "Afternoon"},
        {"city_id": jaipur.id, "name": "Jantar Mantar", "latitude": 26.9248, "longitude": 75.8246, "category": "Observatory", "best_time_to_visit": "Morning"},
        
        # --- DELHI ---
        {"city_id": delhi.id, "name": "India Gate", "latitude": 28.6129, "longitude": 77.2295, "category": "Monument", "best_time_to_visit": "Evening", "visit_duration": "1-2 hours", "ticket_price": "Free", "opening_time": "24 hours", "closing_time": "24 hours"},
        {"city_id": delhi.id, "name": "Red Fort", "latitude": 28.6562, "longitude": 77.2410, "category": "Historical Fort", "best_time_to_visit": "Morning", "visit_duration": "2-3 hours", "ticket_price": "₹35 / ₹500", "opening_time": "9:30 AM", "closing_time": "4:30 PM"},
        {"city_id": delhi.id, "name": "Qutub Minar", "latitude": 28.5244, "longitude": 77.1855, "category": "Historical Monument", "best_time_to_visit": "Morning", "visit_duration": "1-2 hours", "ticket_price": "₹40 / ₹600", "opening_time": "7:00 AM", "closing_time": "5:00 PM"},
        {"city_id": delhi.id, "name": "Humayun’s Tomb", "latitude": 28.5933, "longitude": 77.2507, "category": "Historical Monument", "best_time_to_visit": "Afternoon", "visit_duration": "1-2 hours", "ticket_price": "₹40 / ₹600", "opening_time": "6:00 AM", "closing_time": "6:00 PM"},
        {"city_id": delhi.id, "name": "Lotus Temple", "latitude": 28.5535, "longitude": 77.2588, "category": "Religious Site", "best_time_to_visit": "Evening", "visit_duration": "1 hour", "ticket_price": "Free", "opening_time": "9:00 AM", "closing_time": "5:00 PM"},
        {"city_id": delhi.id, "name": "Connaught Place", "latitude": 28.6315, "longitude": 77.2167, "category": "Market", "best_time_to_visit": "Evening", "visit_duration": "2-3 hours", "ticket_price": "Free", "opening_time": "10:00 AM", "closing_time": "10:00 PM"},
        {"city_id": delhi.id, "name": "Jama Masjid", "latitude": 28.6507, "longitude": 77.2334, "category": "Religious Site", "best_time_to_visit": "Morning", "visit_duration": "1 hour", "ticket_price": "Free", "opening_time": "7:00 AM", "closing_time": "5:00 PM"},
        {"city_id": delhi.id, "name": "Akshardham Temple", "latitude": 28.6127, "longitude": 77.2773, "category": "Temple", "best_time_to_visit": "Evening", "visit_duration": "3-4 hours", "ticket_price": "Free", "opening_time": "10:00 AM", "closing_time": "8:00 PM"},
        {"city_id": delhi.id, "name": "Rashtrapati Bhavan", "latitude": 28.6143, "longitude": 77.1994, "category": "Landmark", "best_time_to_visit": "Morning", "visit_duration": "1 hour", "ticket_price": "₹50", "opening_time": "9:00 AM", "closing_time": "4:00 PM"}
    ]

    # 3. Add Sites if Missing
    added_sites = 0
    for s_data in sites_data:
        existing = Site.query.filter_by(name=s_data["name"], city_id=s_data["city_id"]).first()
        if not existing:
            site = Site(
                city_id=s_data["city_id"],
                name=s_data["name"],
                latitude=s_data["latitude"],
                longitude=s_data["longitude"],
                category=s_data.get("category"),
                best_time_to_visit=s_data.get("best_time_to_visit"),
                visit_duration=s_data.get("visit_duration"),
                ticket_price=s_data.get("ticket_price"),
                opening_time=s_data.get("opening_time"),
                closing_time=s_data.get("closing_time")
            )
            db.session.add(site)
            added_sites += 1
    
    if added_sites > 0:
        db.session.commit()
        print(f"✅ Added {added_sites} new sites.")
    else:
        print("ℹ️ All sites already exist.")

with app.app_context():
    db.create_all()
    seed_data()

# --------------------------------------------------
# Utilities
# --------------------------------------------------

def login_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("login"))
        return func(*args, **kwargs)
    return wrapper

def haversine(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))
    return 6371 * c


def fallback_segment(o, d):
    """Always return a SEGMENT (list of coords)."""
    return [[
        [o["lat"], o["lng"]],
        [d["lat"], d["lng"]]
    ]]


GRAPH_CACHE = {}

# CRITICAL SETTING: Disable graph download to prevent Server OOM (Out of Memory) crash
# Set to True only if server has >1GB RAM
ENABLE_ROUTING_GRAPH = False

def get_city_graph(city_name, lat=None, lng=None):
    if not ENABLE_ROUTING_GRAPH:
        return None

    city_key = city_name.lower()

    # 1. In-memory cache (fastest)
    if city_key in GRAPH_CACHE:
        return GRAPH_CACHE[city_key]

    # 2. File cache
    cache_dir = "graph_cache"
    os.makedirs(cache_dir, exist_ok=True)
    graph_path = os.path.join(cache_dir, f"{city_key}.graphml")

    if os.path.exists(graph_path):
        logger.info(f"Loading graph for {city_name} from disk...")
        G = ox.load_graphml(graph_path)
    else:
        logger.info(f"Downloading graph for {city_name}...")
        
        # Optimization: Use graph_from_point instead of graph_from_place
        # graph_from_place uses complex polygon clipping which causes OOM on small servers (like Render free tier).
        # graph_from_point with a radius is much lighter on memory.
        if lat is not None and lng is not None:
             logger.info(f"Using point-based download for {city_name} (6km radius)")
             G = ox.graph_from_point((lat, lng), dist=6000, network_type="drive")
        else:
             # Fallback if no coords provided (shouldn't happen with updated logic)
             logger.info(f"Using place-based download for {city_name}")
             G = ox.graph_from_place(city_name, network_type="drive")

        # Ensure strongly connected to prevent routing errors
        G = ox.utils_graph.get_largest_component(G, strongly=True)
        ox.save_graphml(G, graph_path)

    GRAPH_CACHE[city_key] = G
    return G

# --------------------------------------------------
# Routing Engine
# --------------------------------------------------

def calculate_route(places: List[Dict[str, Any]], city_name: str, city_lat: float = None, city_lng: float = None) -> Tuple[List[List[float]], List[str]]:
    """
    Returns:
    - full_route: List[[lat, lng]]  (single continuous polyline)
    - instructions: List[str]
    """
    try:
        G = get_city_graph(city_name, city_lat, city_lng)
    except Exception as e:
        logger.error(f"Failed to load graph: {e}")
        G = None

    if G is None:
        # Fallback: Straight lines (Lightweight Mode)
        full_route = []
        instructions = []
        for i in range(len(places) - 1):
            o, d = places[i], places[i+1]
            full_route.extend([
                [o["lat"], o["lng"]],
                [d["lat"], d["lng"]]
            ])
            instructions.append(f"Travel to {d['name']} (Direct)")
        return full_route, instructions

    full_route: List[List[float]] = []
    instructions: List[str] = []

    for i in range(len(places) - 1):
        o = places[i]
        d = places[i + 1]

        try:
            orig_node = ox.distance.nearest_nodes(G, o["lng"], o["lat"])
            dest_node = ox.distance.nearest_nodes(G, d["lng"], d["lat"])

            path = nx.shortest_path(G, orig_node, dest_node, weight="length")

            # Extract geometry from edges
            segment_coords = []
            
            # If path is just one node (start == end), skip
            if len(path) < 2:
                continue

            for u, v in zip(path[:-1], path[1:]):
                # Get edge data
                edge_data = G.get_edge_data(u, v)
                
                # OSMnx graphs are MultiDiGraphs, so edge_data is a dictionary keyed by key (0, 1, etc.)
                # applied usually 0 for the first edge
                if edge_data:
                    # Prefer lowest key (0) or any available
                    data = edge_data[0]
                    if "geometry" in data:
                        # Extract geometry (LineString) checking for .coords or directly interacting
                        # Shapely LineString.coords is list of (x, y) = (lng, lat)
                        # We need [lat, lng]
                        xs, ys = data["geometry"].xy
                        for x, y in zip(xs, ys):
                            segment_coords.append([y, x])
                    else:
                        # Fallback to straight line between nodes if no geometry
                        # Node u
                        segment_coords.append([G.nodes[u]["y"], G.nodes[u]["x"]])
                        # Node v
                        segment_coords.append([G.nodes[v]["y"], G.nodes[v]["x"]])
            
            # Ensure the last node coords are added if segment_coords is empty or for continuity
            # But the loop above adds all points. We might have duplicates at seams.
            
            if not segment_coords:
                 # Fallback if loop didn't run (shouldn't happen if path > 1)
                 segment_coords = [[G.nodes[n]["y"], G.nodes[n]["x"]] for n in path]

            # Append to full route
            # Avoid duplicate points at connection (end of previous == start of current)
            if full_route and segment_coords:
                # Calculate distance between last of full_route and first of segment
                # If very close, skip first of segment
                last_pt = full_route[-1]
                first_pt = segment_coords[0]
                if last_pt == first_pt:
                    full_route.extend(segment_coords[1:])
                else:
                    full_route.extend(segment_coords)
            else:
                full_route.extend(segment_coords)

            instructions.append(f"Travel from {o['name']} to {d['name']}")

        except Exception as e:
            logger.error(f"Routing failed between {o['name']} and {d['name']}: {e}")
            # Fallback: Straight line
            fallback = [[o["lat"], o["lng"]], [d["lat"], d["lng"]]]
            if full_route:
                full_route.extend(fallback[1:])
            else:
                full_route.extend(fallback)
            instructions.append(f"Travel to {d['name']} (Direct)")

    return full_route, instructions

# --------------------------------------------------
# Itinerary Generator (DB-driven)
# --------------------------------------------------

def get_time_priority():
    hour = datetime.now().hour

    if 6 <= hour < 12:
        return "Morning"
    elif 12 <= hour < 17:
        return "Afternoon"
    elif 17 <= hour < 21:
        return "Evening"
    else:
        # Late night treated as evening preference
        return "Evening"

def time_score(site_time, current_time):
    if not site_time:
        return 2
    if site_time.lower() == current_time.lower():
        return 0
    if site_time.lower() == "any":
        return 1
    return 2

def generate_procedural_itinerary(city_name, days):

    if not city_name:
        return None

    city_name = city_name.strip().lower()

    city = City.query.filter(
        db.func.lower(City.name) == city_name
    ).first()

    if not city:
        return None

    sites = Site.query.filter_by(city_id=city.id).all()
    if not sites:
        return None

    sites_data: List[Dict[str, Any]] = [
        {
            "id": s.id,
            "name": s.name,
            "lat": s.latitude,
            "lng": s.longitude,
            "category": s.category,
            "opening_time": s.opening_time,
            "closing_time": s.closing_time,
            "ticket_price": s.ticket_price,
            "best_time_to_visit": s.best_time_to_visit,
            "visit_duration": s.visit_duration
        } for s in sites
    ]

    if days <= 0:
        days = 1

    # For demo: allow max 3 days
    days = min(days, 3)

    # Clustering Logic
    coordinates = np.array([[s["lat"], s["lng"]] for s in sites_data])
    
    # K-Means Clustering to group by days
    # If sites < days, reduce days to len(sites) - handled below naturally
    
    num_days = min(days, len(sites_data))
    
    # Map cluster index to list of sites
    day_clusters = {i: [] for i in range(num_days)}
    
    if num_days > 1:
        kmeans = KMeans(n_clusters=num_days, random_state=42, n_init=10)
        labels = kmeans.fit_predict(coordinates)
        
        for idx, label in enumerate(labels):
            day_clusters[label].append(sites_data[idx])
    else:
        # Just one day (or one cluster)
        day_clusters[0] = sites_data

    # Generate Itinerary for each day
    itinerary = []
    
    # Sort clusters by something? Maybe distance from city center?
    # For now, just iterate 0..k
    
    for d in range(num_days):
        day_places_unsorted = day_clusters[d]
        
        if not day_places_unsorted:
            continue
            
        # Optimization: Sort using Nearest Neighbor Heuristic (TSP)
        # Start with the place closest to top-left or city center?
        # Let's just pick the first in list as start, or the one with min latitude (most north?)
        
        # Optimization: TSP with 2-Opt Layout
        # 1. Start with the northernmost point (simple heuristic)
        # 2. Use Greedy Nearest Neighbor to build initial path
        # 3. Refine with 2-Opt to remove crossovers

        if not day_places_unsorted:
            continue
            
        # Helper: Approximate distance in km (Equirectangular approximation)
        def get_dist(p1, p2):
            R = 6371  # Earth radius in km
            lat1, lon1 = math.radians(p1["lat"]), math.radians(p1["lng"])
            lat2, lon2 = math.radians(p2["lat"]), math.radians(p2["lng"])
            x = (lon2 - lon1) * math.cos((lat1 + lat2) / 2)
            y = lat2 - lat1
            return R * math.sqrt(x*x + y*y)

        # 1. Start North
        day_places_unsorted.sort(key=lambda x: x["lat"], reverse=True)
        current = day_places_unsorted.pop(0)
        day_places = [current]

        # 2. Greedy Nearest Neighbor
        while day_places_unsorted:
            nearest = min(day_places_unsorted, key=lambda p: get_dist(current, p))
            day_places.append(nearest)
            day_places_unsorted.remove(nearest)
            current = nearest

        # 3. 2-Opt Optimization (Refining the route)
        # Swaps edges to remove crossings
        def optimize_2opt(route):
            best_route = route
            # Calculate total distance of a route
            def route_dist(r):
                d = 0
                for i in range(len(r)-1):
                    d += get_dist(r[i], r[i+1])
                return d
            
            improved = True
            best_dist = route_dist(route)
            
            # Limit iterations for performance
            for _ in range(50): 
                improved = False
                for i in range(1, len(route) - 2):
                    for j in range(i + 1, len(route)):
                        if j - i == 1: continue
                        
                        # New route with swapped segment
                        new_route = route[:]
                        new_route[i:j] = route[j-1:i-1:-1] # Reverse segment
                        
                        new_dist = route_dist(new_route)
                        if new_dist < best_dist:
                            best_route = new_route
                            best_dist = new_dist
                            improved = True
                            route = best_route
                if not improved:
                    break
            return best_route

        if len(day_places) > 3:
            day_places = optimize_2opt(day_places)

        logger.info(f"Day {d+1} Optimized: {[p['name'] for p in day_places]}")

        # Route Generation
        route = []
        instructions = []
        
        try:
             # Pass city lat/lng to route calculator
             route, instructions = calculate_route(day_places, city.name, city.lat, city.lng)
        except Exception as e:
             logger.error(f"Error calculating route for day {d+1}: {e}")

        # Fallback if routing completely failed (e.g. graph load error)
        if not route and len(day_places) > 1:
            route = [[p["lat"], p["lng"]] for p in day_places]
            instructions = [f"Visit {p['name']}" for p in day_places]

        itinerary.append({
            "day": f"Day {d+1}",
            "places": day_places,
            "route": route,
            "instructions": instructions
        })



    return {
        "city": {
            "name": city.name,
            "lat": city.lat,
            "lng": city.lng
        },
        "days": itinerary
    }

# --------------------------------------------------
# Routes
# --------------------------------------------------

@app.route("/")
def landing():
    try:
        return render_template("landing.html")
    except Exception as e:
        logger.error(f"Error rendering landing page: {e}")
        return "Error loading landing page", 500

@app.route("/home")
@login_required
def home():
    return render_template("home.html")

# ... (omitted similar lines for brevity, target carefully) ...

@app.route("/logout")
def logout():
    try:
        logger.info("Logging out user...")
        session.clear()
        logger.info("Session cleared. Redirecting to landing.")
        return redirect(url_for("landing"))
    except Exception as e:
        logger.error(f"Error during logout: {e}")
        return redirect(url_for("landing")) # Fallback

@app.route("/planner")
@login_required
def planner():
    return render_template("index.html")

@app.route("/history")
@login_required
def history():
    trips = Trip.query.filter_by(user_id=session.get("user_id")) \
                .order_by(Trip.id.desc()) \
                .limit(10) \
                .all()
    return render_template("history.html", trips=trips)

@app.route("/api/db-route", methods=["POST"])
@login_required
def db_route():
    try:
        data = request.get_json()
        city = data.get("city")
        days = int(data.get("days", 3))

        if not city:
            return jsonify({"status": "error", "message": "City required"}), 400

        # Debug
        logger.info(f"Generating itinerary for {city}, {days} days")

        itinerary = generate_procedural_itinerary(city, days)
        
        if not itinerary:
            return jsonify({"status": "error", "message": "No data found for this city"}), 404

        user_id = session.get("user_id")

        # Ensure user exists in DB (important after DB migrations)
        user = db.session.get(User, user_id) if user_id else None
        if not user:
            session.clear()
            return jsonify({"status": "error", "message": "User session invalid. Please login again."}), 401

        trip = Trip(city=city, days=days, user_id=user.id)
        db.session.add(trip)
        db.session.commit()

        return jsonify({
            "status": "success",
            "city": itinerary["city"],
            "days": itinerary["days"]
        })

    except Exception as e:
        logger.error(f"CRITICAL ERROR in db_route: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": f"Server crash: {str(e)}"}), 500

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password, password):
            session["user_id"] = user.id
            return redirect(url_for("home"))

        return "Invalid credentials"

    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        existing = User.query.filter_by(email=email).first()
        if existing:
            return "User already exists"

        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        new_user = User(email=email, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()

        return redirect(url_for("login"))

    return render_template("register.html")




if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    app.run(host="0.0.0.0", port=port, debug=True)