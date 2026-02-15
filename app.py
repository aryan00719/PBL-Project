import os
import logging
from math import radians, cos, sin, asin, sqrt

from flask import Flask, request, jsonify, render_template, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS

import networkx as nx
import osmnx as ox

from datetime import datetime
import math
from random import shuffle

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


# --------------------------------------------------
# User Model
# --------------------------------------------------
class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)


class Trip(db.Model):
    __tablename__ = "trips"

    id = db.Column(db.Integer, primary_key=True)
    city = db.Column(db.String(100))
    days = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    user = db.relationship("User", backref=db.backref("trips", lazy=True))


def seed_data():
    if City.query.first():
        return  # already seeded

    jaipur = City(name="Jaipur", lat=26.9124, lng=75.7873)
    delhi = City(name="Delhi", lat=28.6139, lng=77.2090)

    db.session.add_all([jaipur, delhi])
    db.session.commit()

    # Add 2–3 demo sites
    site1 = Site(
        city_id=jaipur.id,
        name="Hawa Mahal",
        latitude=26.9239,
        longitude=75.8267,
        category="Monument",
        best_time_to_visit="Morning"
    )

    site2 = Site(
        city_id=delhi.id,
        name="India Gate",
        latitude=28.6129,
        longitude=77.2295,
        category="Monument",
        best_time_to_visit="Evening"
    )

    site3 = Site(
        city_id=jaipur.id,
        name="Amer Fort",
        latitude=26.9855,
        longitude=75.8513,
        category="Fort",
        best_time_to_visit="Morning"
    )

    site4 = Site(
        city_id=jaipur.id,
        name="City Palace",
        latitude=26.9258,
        longitude=75.8237,
        category="Palace",
        best_time_to_visit="Afternoon"
    )

    db.session.add_all([site1, site2, site3, site4])
    db.session.commit()

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
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))
    return 6371 * c


def fallback_segment(o, d):
    """Always return a SEGMENT (list of coords)."""
    return [[
        [o["lat"], o["lng"]],
        [d["lat"], d["lng"]]
    ]]


GRAPH_CACHE = {}

def get_city_graph(city_name):
    city_key = city_name.lower()

    # 1. In-memory cache (fastest)
    if city_key in GRAPH_CACHE:
        return GRAPH_CACHE[city_key]

    # 2. File cache
    cache_dir = "graph_cache"
    os.makedirs(cache_dir, exist_ok=True)
    graph_path = os.path.join(cache_dir, f"{city_key}.graphml")

    if os.path.exists(graph_path):
        G = ox.load_graphml(graph_path)
    else:
        G = ox.graph_from_place(city_name, network_type="drive")
        G = ox.utils_graph.get_largest_component(G, strongly=False)
        ox.save_graphml(G, graph_path)

    GRAPH_CACHE[city_key] = G
    return G

# --------------------------------------------------
# Routing Engine
# --------------------------------------------------

def calculate_route(places, city_name):
    """
    Returns:
    - full_route: List[[lat, lng]]  (single continuous polyline)
    - instructions: List[str]
    """
    G = get_city_graph(city_name)
    full_route = []
    instructions = []

    for i in range(len(places) - 1):
        o = places[i]
        d = places[i + 1]

        try:
            orig = ox.distance.nearest_nodes(G, o["lng"], o["lat"])
            dest = ox.distance.nearest_nodes(G, d["lng"], d["lat"])

            if not nx.has_path(G, orig, dest):
                raise Exception("No path")

            path = nx.shortest_path(G, orig, dest, weight="length")

            coords = [
                [G.nodes[n]["y"], G.nodes[n]["x"]] for n in path
            ]

            # Merge segments into one continuous polyline
            if not full_route:
                full_route.extend(coords)
            else:
                # Avoid duplicating first node of next segment
                full_route.extend(coords[1:])

            instructions.append("Go between two places")

        except Exception as e:
            logger.warning(
                f"Routing fallback activated between {o['name']} and {d['name']}: {e}"
            )

            fallback_coords = [
                [o["lat"], o["lng"]],
                [d["lat"], d["lng"]]
            ]

            if not full_route:
                full_route.extend(fallback_coords)
            else:
                full_route.extend(fallback_coords[1:])

            instructions.append("Go between two places (direct)")

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
    # Normalize input
    if not city_name:
        return None

    city_name = city_name.strip().lower()

    city = City.query.filter(
        db.func.lower(City.name) == city_name
    ).first()

    if not city:
        logger.warning(f"City not found in DB: {city_name}")
        available = [c.name for c in City.query.all()]
        logger.warning(f"Available cities: {available}")
        return None

    sites = Site.query.filter_by(city_id=city.id).all()
    if not sites:
        return None

    time_pref = get_time_priority()

    # First sort by time preference score
    sites.sort(
        key=lambda s: time_score(s.best_time_to_visit, time_pref)
    )

    # Shuffle within equal-priority groups for dynamic variation
    grouped = {}
    for s in sites:
        score = time_score(s.best_time_to_visit, time_pref)
        grouped.setdefault(score, []).append(s)

    new_sites = []
    for score in sorted(grouped.keys()):
        shuffle(grouped[score])
        new_sites.extend(grouped[score])

    sites = new_sites

    sites_data = [
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

    per_day = math.ceil(len(sites_data) / days)
    itinerary = []
    idx = 0

    for d in range(days):
        day_places = sites_data[idx:idx + per_day]
        idx += per_day

        if not day_places:
            break

        if len(day_places) >= 2:
            route, instructions = calculate_route(day_places, city.name)
        else:
            route = []
            instructions = []

        itinerary.append({
            "day": f"Day {d + 1}",
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
    return render_template("landing.html")

@app.route("/home")
@login_required
def home():
    return render_template("home.html")

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
    data = request.get_json()
    city = data.get("city")
    days = int(data.get("days", 3))

    if not city:
        return jsonify({"status": "error", "message": "City required"}), 400

    itinerary = generate_procedural_itinerary(city, days)
    if not itinerary:
        return jsonify({"status": "error", "message": "No data found"}), 404

    user_id = session.get("user_id")

    # Ensure user exists in DB (important after DB migrations)
    user = User.query.get(user_id) if user_id else None
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


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("landing"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050, debug=False)