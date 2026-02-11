"""
populate_delhi_db.py
--------------------
Populates Delhi city and its major tourist sites into the database.
Safe to re-run (skips existing entries).
"""

from app import app, db, City, Site

def populate_delhi_data():
    with app.app_context():

        # ----------------------------
        # 1️⃣ Check / Create City
        # ----------------------------
        city = City.query.filter_by(name="Delhi").first()

        if city:
            print("ℹ️ Delhi city already exists.")
        else:
            city = City(
                name="Delhi",
                lat=28.6139,
                lng=77.2090
            )
            db.session.add(city)
            db.session.commit()
            print("✅ Added city: Delhi")

        # ----------------------------
        # 2️⃣ Delhi Tourist Sites
        # ----------------------------
        delhi_sites = [
            {
                "name": "India Gate",
                "latitude": 28.6129,
                "longitude": 77.2295,
                "category": "Monument",
                "visit_duration": "1-2 hours",
                "entry_fee": "Free",
                "opening_hours": "24 hours – 24 hours",
                "best_time_to_visit": "Evening"
            },
            {
                "name": "Red Fort",
                "latitude": 28.6562,
                "longitude": 77.2410,
                "category": "Historical Fort",
                "visit_duration": "2-3 hours",
                "entry_fee": "₹35 / ₹500",
                "opening_hours": "9:30 AM – 4:30 PM",
                "best_time_to_visit": "Morning"
            },
            {
                "name": "Qutub Minar",
                "latitude": 28.5244,
                "longitude": 77.1855,
                "category": "Historical Monument",
                "visit_duration": "1-2 hours",
                "entry_fee": "₹40 / ₹600",
                "opening_hours": "7:00 AM – 5:00 PM",
                "best_time_to_visit": "Morning"
            },
            {
                "name": "Humayun’s Tomb",
                "latitude": 28.5933,
                "longitude": 77.2507,
                "category": "Historical Monument",
                "visit_duration": "1-2 hours",
                "entry_fee": "₹40 / ₹600",
                "opening_hours": "6:00 AM – 6:00 PM",
                "best_time_to_visit": "Afternoon"
            },
            {
                "name": "Lotus Temple",
                "latitude": 28.5535,
                "longitude": 77.2588,
                "category": "Religious Site",
                "visit_duration": "1 hour",
                "entry_fee": "Free",
                "opening_hours": "9:00 AM – 5:00 PM",
                "best_time_to_visit": "Evening"
            },
            {
                "name": "Connaught Place",
                "latitude": 28.6315,
                "longitude": 77.2167,
                "category": "Market",
                "visit_duration": "2-3 hours",
                "entry_fee": "Free",
                "opening_hours": "10:00 AM – 10:00 PM",
                "best_time_to_visit": "Evening"
            }
        ]

        # ----------------------------
        # 3️⃣ Insert Sites Safely
        # ----------------------------
        added = 0
        skipped = 0

        for site_data in delhi_sites:
            existing = Site.query.filter_by(
                name=site_data["name"],
                city_id=city.id
            ).first()

            if existing:
                print(f"⚠️ Skipped: {site_data['name']}")
                skipped += 1
                continue

            opening_time = None
            closing_time = None

            if " – " in site_data["opening_hours"]:
                opening_time, closing_time = site_data["opening_hours"].split(" – ")
            else:
                opening_time = site_data["opening_hours"]
                closing_time = site_data["opening_hours"]

            site = Site(
                city_id=city.id,
                name=site_data["name"],
                category=site_data["category"],
                latitude=site_data["latitude"],
                longitude=site_data["longitude"],
                visit_duration=site_data["visit_duration"],
                ticket_price=site_data["entry_fee"],
                opening_time=opening_time,
                closing_time=closing_time,
                best_time_to_visit=site_data["best_time_to_visit"]
            )

            db.session.add(site)
            added += 1

        db.session.commit()
        print(f"🎉 Delhi data population complete! Added {added}, skipped {skipped}.")


if __name__ == "__main__":
    populate_delhi_data()