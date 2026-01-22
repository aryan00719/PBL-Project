from app import app, db, City, Site


def populate_jaipur_data():
    with app.app_context():

        # =========================
        # 1️⃣ FETCH OR CREATE CITY
        # =========================
        city = City.query.filter_by(name="Jaipur").first()

        if not city:
            city = City(
                name="Jaipur",
                state="Rajasthan",
                region="North India",
                latitude=26.9124,
                longitude=75.7873,
            )
            db.session.add(city)
            db.session.commit()
            print("✅ Added Jaipur city to database.")
        else:
            print("ℹ️ Jaipur city already exists.")

        # =========================
        # 2️⃣ PLACES DATA
        # =========================
        places = [
            {
                "name": "Amber Fort",
                "category": "Fort",
                "description": "A magnificent hilltop fort offering panoramic views and rich Rajput history.",
                "latitude": 26.9855,
                "longitude": 75.8513,
                "rating": 4.8,
                "visit_duration": "2–3 hours",
                "entry_fee": "₹100 (Indian) / ₹500 (Foreigner)",
                "opening_hours": "8:00 AM – 5:30 PM",
                "image_url": "https://upload.wikimedia.org/wikipedia/commons/0/0d/Amber_Fort_Jaipur_2016.jpg"
            },
            {
                "name": "Hawa Mahal",
                "category": "Palace",
                "description": "The Palace of Winds, famous for its pink lattice windows.",
                "latitude": 26.9239,
                "longitude": 75.8267,
                "rating": 4.6,
                "visit_duration": "1 hour",
                "entry_fee": "₹50 / ₹200",
                "opening_hours": "9:00 AM – 4:30 PM",
                "image_url": "https://upload.wikimedia.org/wikipedia/commons/d/dc/Hawa_Mahal_2011.jpg"
            },
            {
                "name": "City Palace",
                "category": "Palace",
                "description": "A royal complex of courtyards, museums, and residences.",
                "latitude": 26.9262,
                "longitude": 75.8238,
                "rating": 4.7,
                "visit_duration": "2 hours",
                "entry_fee": "₹200 / ₹700",
                "opening_hours": "9:30 AM – 5:00 PM",
                "image_url": "https://upload.wikimedia.org/wikipedia/commons/1/12/City_Palace_Jaipur_2016.jpg"
            },
            {
                "name": "Jantar Mantar",
                "category": "Observatory",
                "description": "UNESCO World Heritage site with astronomical instruments.",
                "latitude": 26.9258,
                "longitude": 75.8236,
                "rating": 4.6,
                "visit_duration": "1 hour",
                "entry_fee": "₹50 / ₹200",
                "opening_hours": "9:00 AM – 5:00 PM",
                "image_url": "https://upload.wikimedia.org/wikipedia/commons/3/35/Jantar_Mantar%2C_Jaipur.jpg"
            },
            {
                "name": "Nahargarh Fort",
                "category": "Fort",
                "description": "A scenic fort overlooking Jaipur, famous for sunset views.",
                "latitude": 26.9372,
                "longitude": 75.8195,
                "rating": 4.5,
                "visit_duration": "2 hours",
                "entry_fee": "₹50",
                "opening_hours": "10:00 AM – 5:30 PM",
                "image_url": "https://upload.wikimedia.org/wikipedia/commons/0/0f/Nahargarh_Fort.jpg"
            },
            {
                "name": "Jal Mahal",
                "category": "Palace",
                "description": "A palace in the middle of Man Sagar Lake.",
                "latitude": 26.9539,
                "longitude": 75.8466,
                "rating": 4.5,
                "visit_duration": "30 minutes",
                "entry_fee": "Free",
                "opening_hours": "24 hours",
                "image_url": "https://upload.wikimedia.org/wikipedia/commons/f/f4/Jal_Mahal_2011.jpg"
            }
        ]

        # =========================
        # 3️⃣ INSERT PLACES
        # =========================
        for place in places:
            exists = Site.query.filter_by(
                name=place["name"],
                city_id=city.id
            ).first()

            if exists:
                print(f"⚠️ Skipped: {place['name']}")
                continue

            db_place = Site(
                city_id=city.id,
                name=place["name"],
                category=place["category"],
                description=place["description"],
                latitude=place["latitude"],
                longitude=place["longitude"],
            )
            db.session.add(db_place)
            print(f"✅ Added: {place['name']}")

        db.session.commit()
        print("🎉 Jaipur data population complete!")


if __name__ == "__main__":
    populate_jaipur_data()