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
                "description": "War memorial and iconic landmark in central Delhi"
            },
            {
                "name": "Red Fort",
                "latitude": 28.6562,
                "longitude": 77.2410,
                "category": "Historical Fort",
                "description": "UNESCO World Heritage Site and former Mughal residence"
            },
            {
                "name": "Qutub Minar",
                "latitude": 28.5244,
                "longitude": 77.1855,
                "category": "Historical Monument",
                "description": "Tallest brick minaret in the world, UNESCO site"
            },
            {
                "name": "Humayun’s Tomb",
                "latitude": 28.5933,
                "longitude": 77.2507,
                "category": "Historical Monument",
                "description": "Precursor to the Taj Mahal, Mughal architecture"
            },
            {
                "name": "Lotus Temple",
                "latitude": 28.5535,
                "longitude": 77.2588,
                "category": "Religious Site",
                "description": "Baháʼí House of Worship, lotus-shaped structure"
            },
            {
                "name": "Connaught Place",
                "latitude": 28.6315,
                "longitude": 77.2167,
                "category": "Market",
                "description": "Major commercial and cultural hub of Delhi"
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

            site = Site(
                city_id=city.id,
                name=site_data["name"],
                latitude=site_data["latitude"],
                longitude=site_data["longitude"]
            )

            db.session.add(site)
            added += 1

        db.session.commit()
        print(f"🎉 Delhi data population complete! Added {added}, skipped {skipped}.")


if __name__ == "__main__":
    populate_delhi_data()