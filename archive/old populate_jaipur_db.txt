from app import app, db, City, Site

def populate_jaipur_data():
    with app.app_context():
        # Check if Jaipur already exists
        city = City.query.filter_by(name="Jaipur").first()
        if not city:
            city = City(
                name="Jaipur",
                state="Rajasthan",
                country="India",
                region="North India",
                lat=26.9124,
                lng=75.7873,
                description="The capital city of Rajasthan, known as the Pink City for its distinct architecture and rich cultural heritage."
            )
            db.session.add(city)
            db.session.commit()
            print("✅ Added Jaipur city to database.")

        places = [
            {
                "name": "Amber Fort",
                "category": "Fort",
                "description": "A magnificent hilltop fort offering panoramic views and rich Rajput history.",
                "lat": 26.9855,
                "lng": 75.8513,
                "rating": 4.8,
                "visit_duration": "2-3 hours",
                "entry_fee": "₹100 (Indian) / ₹500 (Foreigner)",
                "opening_hours": "8:00 AM - 5:30 PM",
                "image_url": "https://upload.wikimedia.org/wikipedia/commons/0/0d/Amber_Fort_Jaipur_2016.jpg"
            },
            {
                "name": "Hawa Mahal",
                "category": "Palace",
                "description": "The 'Palace of Winds', famous for its pink lattice windows built for royal ladies.",
                "lat": 26.9239,
                "lng": 75.8267,
                "rating": 4.6,
                "visit_duration": "1 hour",
                "entry_fee": "₹50 (Indian) / ₹200 (Foreigner)",
                "opening_hours": "9:00 AM - 4:30 PM",
                "image_url": "https://upload.wikimedia.org/wikipedia/commons/d/dc/Hawa_Mahal_2011.jpg"
            },
            {
                "name": "City Palace",
                "category": "Palace",
                "description": "A stunning complex of courtyards, museums, and royal residences in central Jaipur.",
                "lat": 26.9262,
                "lng": 75.8238,
                "rating": 4.7,
                "visit_duration": "2 hours",
                "entry_fee": "₹200 (Indian) / ₹700 (Foreigner)",
                "opening_hours": "9:30 AM - 5:00 PM",
                "image_url": "https://upload.wikimedia.org/wikipedia/commons/1/12/City_Palace_Jaipur_2016.jpg"
            },
            {
                "name": "Jantar Mantar",
                "category": "Observatory",
                "description": "A UNESCO World Heritage site housing 18th-century astronomical instruments.",
                "lat": 26.9258,
                "lng": 75.8236,
                "rating": 4.6,
                "visit_duration": "1 hour",
                "entry_fee": "₹50 (Indian) / ₹200 (Foreigner)",
                "opening_hours": "9:00 AM - 5:00 PM",
                "image_url": "https://upload.wikimedia.org/wikipedia/commons/3/35/Jantar_Mantar%2C_Jaipur.jpg"
            },
            {
                "name": "Nahargarh Fort",
                "category": "Fort",
                "description": "A scenic fort overlooking Jaipur city, perfect for sunset views.",
                "lat": 26.9372,
                "lng": 75.8195,
                "rating": 4.5,
                "visit_duration": "2 hours",
                "entry_fee": "₹50 (Indian) / ₹200 (Foreigner)",
                "opening_hours": "10:00 AM - 5:30 PM",
                "image_url": "https://upload.wikimedia.org/wikipedia/commons/0/0f/Nahargarh_Fort.jpg"
            },
            {
                "name": "Jaigarh Fort",
                "category": "Fort",
                "description": "Houses the world’s largest cannon on wheels, 'Jaivana Cannon'.",
                "lat": 26.9859,
                "lng": 75.8429,
                "rating": 4.6,
                "visit_duration": "2-3 hours",
                "entry_fee": "₹50 (Indian) / ₹200 (Foreigner)",
                "opening_hours": "9:00 AM - 4:30 PM",
                "image_url": "https://upload.wikimedia.org/wikipedia/commons/9/99/Jaigarh_Fort_2016.jpg"
            },
            {
                "name": "Albert Hall Museum",
                "category": "Museum",
                "description": "The oldest museum in Rajasthan with an impressive Indo-Saracenic architecture.",
                "lat": 26.9118,
                "lng": 75.8195,
                "rating": 4.5,
                "visit_duration": "1.5 hours",
                "entry_fee": "₹40 (Indian) / ₹300 (Foreigner)",
                "opening_hours": "9:00 AM - 5:00 PM",
                "image_url": "https://upload.wikimedia.org/wikipedia/commons/1/1b/Albert_Hall_Museum_2017.jpg"
            },
            {
                "name": "Jal Mahal",
                "category": "Palace",
                "description": "A palace situated in the middle of Man Sagar Lake, best viewed from the lakeside.",
                "lat": 26.9539,
                "lng": 75.8466,
                "rating": 4.5,
                "visit_duration": "30 mins",
                "entry_fee": "Free (view only)",
                "opening_hours": "24 hours (view only)",
                "image_url": "https://upload.wikimedia.org/wikipedia/commons/f/f4/Jal_Mahal_2011.jpg"
            },
            {
                "name": "Birla Mandir",
                "category": "Temple",
                "description": "A modern white marble temple dedicated to Lord Vishnu and Goddess Lakshmi.",
                "lat": 26.8900,
                "lng": 75.8150,
                "rating": 4.7,
                "visit_duration": "1 hour",
                "entry_fee": "Free",
                "opening_hours": "6:00 AM - 12:00 PM, 3:00 PM - 9:00 PM",
                "image_url": "https://upload.wikimedia.org/wikipedia/commons/e/e8/Birla_Mandir_Jaipur.jpg"
            },
            {
                "name": "Chokhi Dhani",
                "category": "Cultural Village",
                "description": "An ethnic village resort showcasing Rajasthani culture, food, and performances.",
                "lat": 26.7714,
                "lng": 75.8281,
                "rating": 4.4,
                "visit_duration": "3 hours",
                "entry_fee": "₹800-₹1200 (depending on meal)",
                "opening_hours": "5:30 PM - 11:00 PM",
                "image_url": "https://upload.wikimedia.org/wikipedia/commons/5/5d/Chokhi_Dhani_Jaipur.jpg"
            },
            {
                "name": "Johari Bazaar",
                "category": "Market",
                "description": "Famous for jewelry, textiles, and traditional Rajasthani handicrafts.",
                "lat": 26.9184,
                "lng": 75.8269,
                "rating": 4.3,
                "visit_duration": "1-2 hours",
                "entry_fee": "Free",
                "opening_hours": "10:00 AM - 8:00 PM",
                "image_url": "https://upload.wikimedia.org/wikipedia/commons/1/1b/Johari_Bazaar_Jaipur.jpg"
            },
            {
                "name": "Galtaji Temple (Monkey Temple)",
                "category": "Temple",
                "description": "An ancient pilgrimage site surrounded by hills, known for its monkeys and holy water tanks.",
                "lat": 26.9361,
                "lng": 75.8642,
                "rating": 4.4,
                "visit_duration": "2 hours",
                "entry_fee": "Free",
                "opening_hours": "5:00 AM - 9:00 PM",
                "image_url": "https://upload.wikimedia.org/wikipedia/commons/7/70/Galta_Ji_temple.jpg"
            },
            {
                "name": "Sisodia Rani Garden",
                "category": "Garden",
                "description": "A serene garden with fountains, murals, and royal architecture.",
                "lat": 26.9018,
                "lng": 75.8533,
                "rating": 4.3,
                "visit_duration": "1 hour",
                "entry_fee": "₹50",
                "opening_hours": "8:00 AM - 8:00 PM",
                "image_url": "https://upload.wikimedia.org/wikipedia/commons/5/53/Sisodia_Rani_Garden_2017.jpg"
            },
            {
                "name": "Jaipur Wax Museum",
                "category": "Museum",
                "description": "Features life-size wax statues of famous personalities, located inside Nahargarh Fort.",
                "lat": 26.9380,
                "lng": 75.8197,
                "rating": 4.5,
                "visit_duration": "1 hour",
                "entry_fee": "₹350",
                "opening_hours": "10:00 AM - 6:30 PM",
                "image_url": "https://upload.wikimedia.org/wikipedia/commons/f/f2/Jaipur_Wax_Museum.jpg"
            },
            {
                "name": "Patrika Gate",
                "category": "Landmark",
                "description": "A colorful gateway with intricate paintings representing Rajasthan’s culture.",
                "lat": 26.8418,
                "lng": 75.8013,
                "rating": 4.8,
                "visit_duration": "30 mins",
                "entry_fee": "Free",
                "opening_hours": "24 hours",
                "image_url": "https://upload.wikimedia.org/wikipedia/commons/9/9d/Patrika_Gate_Jaipur.jpg"
            }
        ]

        for place in places:
            if not Site.query.filter_by(name=place["name"]).first():
                db_place = Site(city_id=city.id, **place)
                db.session.add(db_place)
                print(f"✅ Added: {place['name']}")
        db.session.commit()
        print("🎉 Jaipur data population complete!")

if __name__ == "__main__":
    populate_jaipur_data()