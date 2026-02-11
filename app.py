import os
import logging
from math import radians, cos, sin, asin, sqrt

from flask import Flask, request, jsonify, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS

import networkx as nx
import osmnx as ox

from datetime import datetime
import math
from random import shuffle

# --------------------------------------------------
# App & Config
# --------------------------------------------------

app = Flask(__name__)
CORS(app)

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
INSTANCE_DIR = os.path.join(BASE_DIR, "instance")
os.makedirs(INSTANCE_DIR, exist_ok=True)

DB_PATH = os.path.join(INSTANCE_DIR, "travel.db")
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{DB_PATH}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

logging.basicConfig(level=logging.INFO)
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


class Trip(db.Model):
    __tablename__ = "trips"

    id = db.Column(db.Integer, primary_key=True)
    city = db.Column(db.String(100))
    days = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# --------------------------------------------------
# Utilities
# --------------------------------------------------

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


def get_city_graph(city_name):
    city_key = city_name.lower()

    if city_key in city_graph_cache:
        return city_graph_cache[city_key]

    logger.info(f"Downloading map graph for {city_key}")
    G = ox.graph_from_place(city_name, network_type="drive")
    # Ensure we use only the largest strongly connected component
    try:
        largest_cc = max(nx.strongly_connected_components(G), key=len)
        G = G.subgraph(largest_cc).copy()
    except Exception as e:
        logger.warning(f"Could not extract largest component: {e}")

    city_graph_cache[city_key] = G
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
    city = City.query.filter(
        db.func.lower(City.name) == city_name.lower()
    ).first()

    if not city:
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
def index():
    return render_template("index.html")


@app.route("/history")
def history():
    trips = Trip.query.order_by(Trip.id.desc()).limit(10).all()
    return render_template("history.html", trips=trips)


@app.route("/api/db-route", methods=["POST"])
def db_route():
    data = request.get_json()
    city = data.get("city")
    days = int(data.get("days", 3))

    if not city:
        return jsonify({"status": "error", "message": "City required"}), 400

    itinerary = generate_procedural_itinerary(city, days)
    if not itinerary:
        return jsonify({"status": "error", "message": "No data found"}), 404

    trip = Trip(city=city, days=days)
    db.session.add(trip)
    db.session.commit()

    return jsonify({
        "status": "success",
        "city": itinerary["city"],
        "days": itinerary["days"]
    })


# --------------------------------------------------
# Bootstrap
# --------------------------------------------------

if __name__ == "__main__":
    with app.app_context():
        db.create_all()

    logger.info("Server running at http://localhost:5050")
    app.run(host="0.0.0.0", port=5050, debug=False)