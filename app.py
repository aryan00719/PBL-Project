import os
import logging
from math import radians, cos, sin, asin, sqrt

from flask import Flask, request, jsonify, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS

import networkx as nx
import osmnx as ox

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
    city_id = db.Column(db.Integer, db.ForeignKey("cities.id"), nullable=False)
    name = db.Column(db.String(150), nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)


class Trip(db.Model):
    __tablename__ = "trips"
    id = db.Column(db.Integer, primary_key=True)
    city = db.Column(db.String(100))
    days = db.Column(db.Integer)


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
    logger.info(f"Downloading map graph for {city_name.lower()}")
    return ox.graph_from_place(
        city_name,
        network_type="drive",
        simplify=True
    )


# --------------------------------------------------
# Routing Engine
# --------------------------------------------------

def calculate_route(places, city_name):
    """
    Returns:
    - route_segments: List[List[[lat, lng]]]
    - instructions: List[str]
    """
    G = get_city_graph(city_name)
    route_segments = []
    instructions = []

    for i in range(len(places) - 1):
        o = places[i]
        d = places[i + 1]

        try:
            orig = ox.distance.nearest_nodes(G, o["lng"], o["lat"])
            dest = ox.distance.nearest_nodes(G, d["lng"], d["lat"])
            path = nx.shortest_path(G, orig, dest, weight="length")

            coords = [
                [G.nodes[n]["y"], G.nodes[n]["x"]] for n in path
            ]

            route_segments.append(coords)
            instructions.append("Go between two places")

        except Exception as e:
            logger.warning(
                f"Routing fallback activated between {o['name']} and {d['name']}: {e}"
            )
            route_segments.extend(fallback_segment(o, d))
            instructions.append("Go between two places (direct)")

    return route_segments, instructions


# --------------------------------------------------
# Itinerary Generator (DB-driven)
# --------------------------------------------------

def generate_procedural_itinerary(city_name, days):
    city = City.query.filter(
        db.func.lower(City.name) == city_name.lower()
    ).first()

    if not city:
        return None

    sites = Site.query.filter_by(city_id=city.id).all()
    if not sites:
        return None

    sites_data = [
        {
            "name": s.name,
            "lat": s.latitude,
            "lng": s.longitude
        } for s in sites
    ]

    per_day = max(2, len(sites_data) // days)
    itinerary = []
    idx = 0

    for d in range(days):
        day_places = sites_data[idx:idx + per_day]
        idx += per_day

        if len(day_places) < 2:
            break

        route, instructions = calculate_route(day_places, city.name)

        itinerary.append({
            "day": f"Day {d + 1}",
            "places": [p["name"] for p in day_places],
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