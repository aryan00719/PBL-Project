import os
import json
import logging
import math
from typing import List, Dict, Any, Tuple

from flask import Flask, request, jsonify, render_template, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from flask_cors import CORS

import numpy as np

# Fix for OSMnx crashing on NumPy 2.0+ (np.float_ was removed)
if not hasattr(np, 'float_'):
    np.float_ = np.float64

import networkx as nx
import osmnx as ox

from datetime import datetime
import math
from random import shuffle
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
    is_admin = db.Column(db.Boolean, default=False)

    def __init__(self, email, password, is_admin=False):
        self.email = email
        self.password = password
        self.is_admin = is_admin


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
    """
    Ensures the six supported cities exist in the database.
    If the database is empty, it auto-seeds from data/initial_data.json.
    """
    CITIES = [
        {"name": "Jaipur",    "lat": 26.9124, "lng": 75.7873},
        {"name": "Delhi",     "lat": 28.6139, "lng": 77.2090},
        {"name": "Mumbai",    "lat": 19.0760, "lng": 72.8777},
        {"name": "Agra",      "lat": 27.1767, "lng": 78.0081},
        {"name": "Udaipur",   "lat": 24.5854, "lng": 73.7125},
        {"name": "Bangalore", "lat": 12.9716, "lng": 77.5946},
    ]

    # Seed Cities
    for c_data in CITIES:
        if not City.query.filter_by(name=c_data["name"]).first():
            db.session.add(City(name=c_data["name"], lat=c_data["lat"], lng=c_data["lng"]))
    db.session.commit()

    # Seed Sites from JSON if empty
    if Site.query.count() == 0:
        json_path = os.path.join(os.path.dirname(__file__), "data", "initial_data.json")
        if os.path.exists(json_path):
            print("🚀 DB empty. Seeding initial tourist sites from JSON...")
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    places_data = json.load(f)
                
                sites_added = 0
                for city_name, sites in places_data.items():
                    city_obj = City.query.filter_by(name=city_name).first()
                    if not city_obj: continue
                    
                    for s in sites:
                        new_site = Site(
                            city_id=city_obj.id,
                            name=s["name"],
                            latitude=s["latitude"],
                            longitude=s["longitude"],
                            category=s.get("category"),
                            opening_time=s.get("opening_time"),
                            closing_time=s.get("closing_time"),
                            visit_duration=s.get("visit_duration"),
                            best_time_to_visit=s.get("best_time_to_visit"),
                            ticket_price=s.get("ticket_price"),
                            description=s.get("description"),
                            image_url=s.get("image_url")
                        )
                        db.session.add(new_site)
                        sites_added += 1
                
                db.session.commit()
                print(f"✅ Auto-seeded {sites_added} initial site(s).")
            except Exception as e:
                print(f"❌ Failed to seed from JSON: {e}")
        else:
            print("⚠️  No tourist sites found and 'data/initial_data.json' is missing.")
    
    print(f"ℹ️  DB status: {City.query.count()} cities, {Site.query.count()} sites.")

def sync_db_schema():
    """
    Check if required columns exist and add them if missing.
    Specifically handles Postgres 'poisoned transactions' by performing
    a rollback before attempting an ALTER TABLE.
    """
    try:
        with db.engine.connect() as conn:
            is_postgres = "postgresql" in str(db.engine.url).lower()
            
            def ensure_column(table_name, col_name, sql_type):
                try:
                    conn.execute(text(f"SELECT {col_name} FROM {table_name} LIMIT 1"))
                except Exception:
                    if is_postgres:
                        conn.rollback()
                    logger.warning(f"🛠 Syncing {table_name}: Adding missing '{col_name}' column...")
                    try:
                        conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {col_name} {sql_type}"))
                        conn.commit()
                        logger.info(f"✅ Column '{col_name}' added to {table_name}.")
                    except Exception as e:
                        logger.error(f"❌ Failed to add '{col_name}' to {table_name}: {e}")

            # Sync User table
            bool_type = "BOOLEAN DEFAULT FALSE" if is_postgres else "BOOLEAN DEFAULT 0"
            ensure_column("users", "is_admin", bool_type)

            # Sync Site table (ensure newest features are present in Prod)
            ensure_column("sites", "description", "TEXT")
            ensure_column("sites", "image_url", "VARCHAR(255)")
            
    except Exception as e:
        logger.error(f"❌ Schema sync connection failed: {e}")

# --------------------------------------------------
# Startup Initialization (Robust / Non-Blocking)
# --------------------------------------------------
with app.app_context():
    try:
        logger.info("🚀 Starting database initialization...")
        db.create_all()
        # Ensure schema is synced (adds new columns to existing tables)
        sync_db_schema()
        # Seeding
        seed_data()
        logger.info("✅ Database initialization complete.")
    except Exception as e:
        logger.error(f"❌ CRITICAL: Database initialization failed: {e}")
        logger.info("⚠️  Continuing server launch anyway (Manual DB fix may be required).")



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

# CRITICAL SETTING: Disable graph download on Render Free Tier to prevent OOM
# Localhost (Mac) has plenty of RAM, so we enable it there.
IS_RENDER = os.environ.get("RENDER", "False").lower() == "true"
ENABLE_ROUTING_GRAPH = not IS_RENDER

if not ENABLE_ROUTING_GRAPH:
    logger.info("⚡️ RUNNING IN LIGHTWEIGHT MODE (Straight Lines) - Graph Download Disabled")
else:
    logger.info("🌍 RUNNING IN FULL MODE (Road Network) - Graph Download Enabled")

# Use OSMnx HTTP cache to avoid re-downloading the same road tiles
if ENABLE_ROUTING_GRAPH:
    try:
        ox.settings.use_cache = True
        ox.settings.log_console = False
    except Exception:
        pass




def get_city_graph(city_name: str, places: list = None, city_lat: float = None, city_lng: float = None):
    """
    Download (or load from cache) a road-network graph that covers all
    the given places.  Uses a tight bounding-box download so the graph
    is as small as possible while still including every waypoint.
    """
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
        logger.info(f"Loading graph for {city_name} from disk cache...")
        G = ox.load_graphml(graph_path)
        GRAPH_CACHE[city_key] = G
        return G

    # 3. Fresh download — compute center+radius from places bounding box
    #    Uses graph_from_point (more compatible than graph_from_bbox across OSMnx versions).
    logger.info(f"Downloading road graph for {city_name}...")

    BUFFER_M = 5000   # 5 km padding beyond the outermost place

    if places and len(places) >= 1:
        lats = [p["lat"] for p in places]
        lngs = [p["lng"] for p in places]
        center_lat = (max(lats) + min(lats)) / 2
        center_lng = (max(lngs) + min(lngs)) / 2

        # Straight-line distance from centre to a corner, converted to metres
        half_diag_m = haversine(
            center_lat, center_lng,
            max(lats), max(lngs)
        ) * 1000

        radius = int(half_diag_m + BUFFER_M)
        radius = min(max(radius, 8000), 80000)   # clamp: 8 km – 80 km

        logger.info(f"Point-based download for {city_name}: centre ({center_lat:.4f},{center_lng:.4f}), radius={radius}m")
        G = ox.graph_from_point((center_lat, center_lng), dist=radius, network_type="drive")
    elif city_lat is not None and city_lng is not None:
        logger.info(f"Point-based download for {city_name} (15 km fallback radius)")
        G = ox.graph_from_point((city_lat, city_lng), dist=15000, network_type="drive")
    else:
        logger.info(f"Place-based download for {city_name}")
        G = ox.graph_from_place(city_name, network_type="drive")

    G = ox.utils_graph.get_largest_component(G, strongly=True)
    ox.save_graphml(G, graph_path)
    GRAPH_CACHE[city_key] = G
    logger.info(f"Graph for {city_name} saved ({len(G.nodes)} nodes).")
    return G


def _preload_graphs_background():
    """Pre-download road graphs for all supported cities at startup.
    Runs in a daemon thread so it doesn't block the server from starting.
    City-centre coordinates are used here (not place-level bbox),
    so the graphs cover the main urban area.  Individual routes may
    trigger a bbox-based re-download if it covers a wider area.
    """
    from app import app, db, City, Site  # local import to avoid circular import
    try:
        with app.app_context():
            cities = City.query.all()
            for city in cities:
                city_key = city.name.lower()
                if city_key in GRAPH_CACHE:
                    continue
                graph_path = os.path.join("graph_cache", f"{city_key}.graphml")
                if os.path.exists(graph_path):
                    logger.info(f"[BG] Graph already on disk for {city.name}, skipping.")
                    continue
                try:
                    # Fetch all sites for this city to get the real bbox
                    sites = Site.query.filter_by(city_id=city.id).all()
                    place_list = [{"lat": s.latitude, "lng": s.longitude} for s in sites if s.latitude and s.longitude]
                    logger.info(f"[BG] Pre-downloading graph for {city.name} ({len(place_list)} sites)...")
                    get_city_graph(city.name, places=place_list, city_lat=city.lat, city_lng=city.lng)
                    logger.info(f"[BG] Graph ready for {city.name}.")
                except Exception as e:
                    logger.error(f"[BG] Failed to pre-download graph for {city.name}: {e}")
    except Exception as e:
        logger.error(f"[BG] Pre-load thread error: {e}")

# Start background graph pre-loader only on the main process (not the Werkzeug reloader child)
if ENABLE_ROUTING_GRAPH and os.environ.get("WERKZEUG_RUN_MAIN") != "true":
    import threading
    threading.Thread(target=_preload_graphs_background, daemon=True, name="GraphPreloader").start()
    logger.info("🗺 Background graph pre-loader started.")

# --------------------------------------------------
# Routing Engine
# --------------------------------------------------

def calculate_route(places: List[Dict[str, Any]], city_name: str, city_lat: float = None, city_lng: float = None) -> Tuple[List[List[float]], List[str]]:
    """
    Returns:
    - full_route: List[[lat, lng]]  (single continuous polyline)
    - instructions: List[str]
    """
    logger.info(f"Starting routing for {city_name} with {len(places)} places")
    try:
        G = get_city_graph(city_name, places=places, city_lat=city_lat, city_lng=city_lng)
        if G is not None:
             logger.info(f"Graph successfully loaded for {city_name}.")
        else:
             logger.warning(f"Graph is None for {city_name}.")
    except Exception as e:
        logger.error(f"Failed to load graph: {e}")
        G = None

    if G is None:
        # Fallback: Straight lines (Lightweight Mode)
        logger.info("Using Haversine straight-line fallback for overall route.")
        full_route = []
        instructions = []
        for i in range(len(places) - 1):
            o, d = places[i], places[i+1]
            pt_o = [o["lat"], o["lng"]]
            pt_d = [d["lat"], d["lng"]]
            if not full_route or full_route[-1] != pt_o:
                full_route.append(pt_o)
            full_route.append(pt_d)
            instructions.append(f"Travel to {d['name']} (Direct)")
        logger.info(f"Fallback complete. Continuous route points: {len(full_route)}")
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
                edge_data = G.get_edge_data(u, v)
                
                if edge_data:
                    # MultiDiGraph yields a dict of edges between u and v keyed by edge key
                    if isinstance(edge_data, dict):
                        data = min(edge_data.values(), key=lambda d: d.get('length', float('inf')))
                    else:
                        data = edge_data

                    if "geometry" in data:
                        for x, y in data["geometry"].coords:
                            pt = [y, x] # Convert (lng, lat) to [lat, lng]
                            if not segment_coords or segment_coords[-1] != pt:
                                segment_coords.append(pt)
                    else:
                        # Fallback to straight line between nodes if no geometry
                        pt_u = [G.nodes[u]["y"], G.nodes[u]["x"]]
                        pt_v = [G.nodes[v]["y"], G.nodes[v]["x"]]
                        if not segment_coords or segment_coords[-1] != pt_u:
                            segment_coords.append(pt_u)
                        if not segment_coords or segment_coords[-1] != pt_v:
                            segment_coords.append(pt_v)
            
            if not segment_coords:
                 # Fallback if loop didn't run
                 for n in path:
                     pt = [G.nodes[n]["y"], G.nodes[n]["x"]]
                     if not segment_coords or segment_coords[-1] != pt:
                         segment_coords.append(pt)

            # Append to full route, avoiding duplicate points at junctions
            if full_route and segment_coords:
                if full_route[-1] == segment_coords[0]:
                    full_route.extend(segment_coords[1:])
                else:
                    full_route.extend(segment_coords)
            else:
                full_route.extend(segment_coords)

            instructions.append(f"Travel from {o['name']} to {d['name']}")

        except Exception as e:
            logger.error(f"Routing failed between {o['name']} and {d['name']}: {e}. Triggering fallback for this segment.")
            # Fallback: Straight line for this segment
            pt_o = [o["lat"], o["lng"]]
            pt_d = [d["lat"], d["lng"]]
            if not full_route or full_route[-1] != pt_o:
                full_route.append(pt_o)
            full_route.append(pt_d)
            instructions.append(f"Travel to {d['name']} (Direct)")

    logger.info(f"Routing complete. Total route points generated: {len(full_route)}")
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
            "visit_duration": s.visit_duration,
            "description": s.description,
            "image_url": s.image_url
        } for s in sites
    ]

    if days <= 0:
        days = 1

    # Cap: can't plan more days than available places (KMeans requires n_clusters ≤ n_samples)
    # The natural limit is applied below via num_days = min(days, len(sites_data))

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

@app.route("/api/delete-trip/<int:trip_id>", methods=["DELETE"])
@login_required
def delete_trip(trip_id):
    try:
        user_id = session.get("user_id")
        trip = db.session.get(Trip, trip_id)
        if not trip or trip.user_id != user_id:
            return jsonify({"status": "error", "message": "Trip not found or unauthorized"}), 404
            
        db.session.delete(trip)
        db.session.commit()
        return jsonify({"status": "success", "message": "Trip deleted."}), 200
    except Exception as e:
        logger.error(f"Error deleting trip {trip_id}: {e}")
        return jsonify({"status": "error", "message": "Server error"}), 500

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


# ===========================================================
# ADMIN PANEL
# ===========================================================

def admin_required(func):
    """Decorator: requires logged-in user with is_admin=True."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        user_id = session.get("user_id")
        if not user_id:
            return redirect(url_for("login"))
        user = db.session.get(User, user_id)
        if not user or not user.is_admin:
            return "⛔ Admin access required.", 403
        return func(*args, **kwargs)
    return wrapper


@app.route("/admin")
@admin_required
def admin_dashboard():
    cities = City.query.order_by(City.name).all()
    total_sites = Site.query.count()
    return render_template("admin/dashboard.html", cities=cities, total_sites=total_sites)


@app.route("/admin/cities/add", methods=["GET", "POST"])
@admin_required
def admin_add_city():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        lat  = request.form.get("lat",  type=float)
        lng  = request.form.get("lng",  type=float)
        if not name or lat is None or lng is None:
            return render_template("admin/city_form.html", error="All fields are required.", city=None)
        if City.query.filter_by(name=name).first():
            return render_template("admin/city_form.html", error=f"City '{name}' already exists.", city=None)
        db.session.add(City(name=name, lat=lat, lng=lng))
        db.session.commit()
        return redirect(url_for("admin_dashboard"))
    return render_template("admin/city_form.html", city=None, error=None)


@app.route("/admin/cities/<int:city_id>/edit", methods=["GET", "POST"])
@admin_required
def admin_edit_city(city_id):
    city = db.session.get(City, city_id)
    if not city:
        return "City not found", 404
    if request.method == "POST":
        city.name = request.form.get("name", city.name).strip()
        city.lat  = request.form.get("lat",  type=float) or city.lat
        city.lng  = request.form.get("lng",  type=float) or city.lng
        db.session.commit()
        return redirect(url_for("admin_dashboard"))
    return render_template("admin/city_form.html", city=city, error=None)


@app.route("/admin/cities/<int:city_id>/delete", methods=["POST"])
@admin_required
def admin_delete_city(city_id):
    city = db.session.get(City, city_id)
    if city:
        Site.query.filter_by(city_id=city_id).delete()
        db.session.delete(city)
        db.session.commit()
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/cities/<int:city_id>/sites")
@admin_required
def admin_sites(city_id):
    city  = db.session.get(City, city_id)
    if not city:
        return "City not found", 404
    sites = Site.query.filter_by(city_id=city_id).order_by(Site.name).all()
    return render_template("admin/sites.html", city=city, sites=sites)


@app.route("/admin/cities/<int:city_id>/sites/add", methods=["GET", "POST"])
@admin_required
def admin_add_site(city_id):
    city = db.session.get(City, city_id)
    if not city:
        return "City not found", 404
    if request.method == "POST":
        f = request.form
        site = Site(
            city_id=city_id,
            name=f.get("name","").strip(),
            latitude=float(f.get("latitude") or 0),
            longitude=float(f.get("longitude") or 0),
            category=f.get("category","").strip() or None,
            opening_time=f.get("opening_time","").strip() or None,
            closing_time=f.get("closing_time","").strip() or None,
            visit_duration=f.get("visit_duration","").strip() or None,
            ticket_price=f.get("ticket_price","").strip() or None,
            best_time_to_visit=f.get("best_time_to_visit","").strip() or None,
            description=f.get("description","").strip() or None,
            image_url=f.get("image_url","").strip() or None,
        )
        db.session.add(site)
        db.session.commit()
        return redirect(url_for("admin_sites", city_id=city_id))
    return render_template("admin/site_form.html", city=city, site=None, error=None)


@app.route("/admin/sites/<int:site_id>/edit", methods=["GET", "POST"])
@admin_required
def admin_edit_site(site_id):
    site = db.session.get(Site, site_id)
    if not site:
        return "Site not found", 404
    if request.method == "POST":
        site.name             = request.form.get("name", site.name).strip()
        site.latitude         = float(request.form.get("latitude") or site.latitude)
        site.longitude        = float(request.form.get("longitude") or site.longitude)
        site.category         = request.form.get("category","").strip() or site.category
        site.opening_time     = request.form.get("opening_time","").strip() or site.opening_time
        site.closing_time     = request.form.get("closing_time","").strip() or site.closing_time
        site.visit_duration   = request.form.get("visit_duration","").strip() or site.visit_duration
        site.ticket_price     = request.form.get("ticket_price","").strip() or site.ticket_price
        site.best_time_to_visit = request.form.get("best_time_to_visit","").strip() or site.best_time_to_visit
        site.description      = request.form.get("description","").strip() or site.description
        site.image_url        = request.form.get("image_url","").strip() or site.image_url
        db.session.commit()
        return redirect(url_for("admin_sites", city_id=site.city_id))
    return render_template("admin/site_form.html", city=site.city, site=site, error=None)


@app.route("/admin/sites/<int:site_id>/delete", methods=["POST"])
@admin_required
def admin_delete_site(site_id):
    site = db.session.get(Site, site_id)
    if site:
        city_id = site.city_id
        db.session.delete(site)
        db.session.commit()
        return redirect(url_for("admin_sites", city_id=city_id))
    return redirect(url_for("admin_dashboard"))



if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    app.run(host="0.0.0.0", port=port, debug=True)
