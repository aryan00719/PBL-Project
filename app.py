from flask import Flask, jsonify, request, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
import osmnx as ox
import networkx as nx
import logging
import time
import json
import requests
import re
from pathlib import Path

# ------------------ APP SETUP ------------------

app = Flask(__name__, static_folder='static')
CORS(app)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///travel.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

logging.basicConfig(level=logging.INFO)

# ------------------ MODELS ------------------

class City(db.Model):
    __tablename__ = "cities"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    state = db.Column(db.String(100))
    region = db.Column(db.String(100))
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)

    sites = db.relationship("Site", back_populates="city", lazy=True)


class Site(db.Model):
    __tablename__ = "site"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    category = db.Column(db.String(100))
    description = db.Column(db.Text)
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    city_id = db.Column(db.Integer, db.ForeignKey("cities.id"))

    city = db.relationship("City", back_populates="sites")


# ------------------ GRAPH CACHE ------------------

GRAPH_DIR = Path("graph_cache")
GRAPH_DIR.mkdir(exist_ok=True)
graph_cache = {}
CACHE_TIMEOUT = 86400  # 24h

ox.settings.use_cache = True
ox.settings.log_console = False


def get_cached_graph(city_name):
    key = city_name.lower().replace(" ", "_")
    path = GRAPH_DIR / f"{key}.graphml"

    if key in graph_cache:
        return graph_cache[key]

    if path.exists():
        age = time.time() - path.stat().st_mtime
        if age < CACHE_TIMEOUT:
            G = ox.load_graphml(path)
            graph_cache[key] = G
            return G

    logging.info(f"Downloading map graph for {city_name}")
    G = ox.graph_from_place(
        f"{city_name}, India",
        network_type="drive",   #network_type="all",
        simplify=True
    )
    ox.save_graphml(G, path)
    graph_cache[key] = G
    return G


# ------------------ ROUTING ------------------

def calculate_route(places, city):
    G = get_cached_graph(city)

    route_coords = []
    instructions = []

    for i in range(len(places) - 1):
        o = places[i]
        d = places[i + 1]

        try:
            orig = ox.distance.nearest_nodes(G, o["lng"], o["lat"])
            dest = ox.distance.nearest_nodes(G, d["lng"], d["lat"])
            path = nx.shortest_path(G, orig, dest, weight="length")

            segment = [
                [G.nodes[node]["y"], G.nodes[node]["x"]]
                for node in path
            ]

            if segment:
                route_coords.extend(segment)
                instructions.append(f"Go from {o['name']} to {d['name']}")

        except Exception as e:
            logging.info(
                f"Fallback route used between {o['name']} and {d['name']}"
            )

            # 🔁 Fallback: straight line
            route_coords.append([o["lat"], o["lng"]])
            route_coords.append([d["lat"], d["lng"]])
            instructions.append(
                f"Go from {o['name']} to {d['name']} (direct)"
            )

    return route_coords, instructions

# ------------------ ITINERARY (PROCEDURAL) ------------------

def generate_itinerary_from_db(city_name, days):
    city = City.query.filter(db.func.lower(City.name) == city_name.lower()).first()
    if not city:
        raise ValueError("City not found")

    sites = city.sites
    sites = sites[: days * 3]  # 3 places/day

    per_day = max(1, len(sites) // days)
    itinerary = []
    idx = 0

    for d in range(days):
        itinerary.append({
            "day": f"Day {d+1}",
            "places": sites[idx:idx + per_day]
        })
        idx += per_day

    return itinerary


# ------------------ ROUTES ------------------

@app.route("/")
def home():
    return render_template("index.html")


@app.route("/api/db-route", methods=["POST"])
def db_route():
    data = request.get_json()
    city = data.get("city")
    days = int(data.get("days", 3))

    if not city:
        return jsonify({"error": "City required"}), 400

    itinerary = generate_itinerary_from_db(city, days)
    day_routes = []

    for day in itinerary:
        places = [
            {"name": s.name, "lat": s.latitude, "lng": s.longitude}
            for s in day["places"]
            if s.latitude and s.longitude
        ]

        if len(places) < 2:
            day_routes.append({
                "day": day["day"],
                "places": [p["name"] for p in places],
                "route": [],
                "instructions": []
            })
            continue

        route, instructions = calculate_route(places, city)

        day_routes.append({
            "day": day["day"],
            "places": [p["name"] for p in places],
            "route": route,
            "instructions": instructions
        })

    return jsonify({"status": "success", "days": day_routes})


@app.route("/cities")
def cities():
    return jsonify({
        "cities": [
            {"id": c.id, "name": c.name, "state": c.state}
            for c in City.query.all()
        ]
    })


@app.route("/sites/<city_name>")
def sites(city_name):
    city = City.query.filter_by(name=city_name).first()
    if not city:
        return jsonify({"error": "City not found"}), 404

    return jsonify({
        "city": city.name,
        "sites": [
            {
                "name": s.name,
                "category": s.category,
                "description": s.description,
                "latitude": s.latitude,
                "longitude": s.longitude
            } for s in city.sites
        ]
    })


# ------------------ START ------------------

if __name__ == "__main__":
    logging.info("Server running at http://localhost:5050")
    app.run(host="0.0.0.0", port=5050, threaded=True)