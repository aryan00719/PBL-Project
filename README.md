# Procedural Travel Itinerary & Routing System

## Overview

This project is a database-driven travel itinerary planner that generates
structured, multi-day travel plans for a city and visualizes optimized routes
on an interactive map.

Unlike AI-generated systems, this application follows a **procedural,
deterministic approach**, ensuring reproducible and explainable outputs.

This version (v2.0) additionally includes user authentication, session-based access control, dynamic time-based location ordering, and improved route visualization with merged polylines for smoother navigation rendering.

---

## System Architecture

### Backend

- Flask-based REST API
- SQLite database for persistent city and site data
- Procedural itinerary generation logic
- Graph-based route computation using OpenStreetMap data
- Session-based authentication and user-linked trip history

### Frontend

- Interactive map visualization using Leaflet.js
- Animated route drawing
- Timeline-style itinerary display
- Navigation instruction summary panel

---

## Core Features

1. **City & Location Database**
   - Cities and tourist locations stored persistently
   - Easy expansion via database population scripts

2. **Procedural Itinerary Generation**
   - Automatically groups locations into day-wise plans
   - Fixed rules ensure consistency and predictability

3. **Graph-Based Route Computation**
   - Uses road network graphs for route calculation
   - Includes graceful fallback when routes are unavailable

4. **Interactive Visualization**
   - Animated route drawing
   - Map markers and bounds adjustment
   - Clean, modern UI for itinerary presentation

5. **User Authentication & Trip History**
   - Secure password hashing using PBKDF2
   - Session-based login protection
   - User-specific trip storage and retrieval

---

## Why This Is Not an AI-Based System

This project intentionally avoids AI-generated content to:

- Ensure deterministic outputs
- Improve explainability
- Enable consistent evaluation
- Support patentability and reproducibility

---

## Technologies Used

- Python (Flask, SQLAlchemy, Werkzeug Security)
- SQLite
- OpenStreetMap / OSMnx
- NetworkX
- Leaflet.js
- HTML, CSS, JavaScript

---

## Novelty & Contribution

This system introduces a deterministic, database-driven approach to
multi-day travel itinerary generation combined with graph-based
route visualization.

Key novel aspects include:

- Rule-based itinerary generation without AI dependence
- Tight integration of persistent city databases with live road graphs
- Graceful fallback routing strategies for disconnected graphs
- Deterministic outputs suitable for academic evaluation and patent filing

---

## Scope of Protection

The following components are intended for copyright and/or patent protection:

- Procedural itinerary generation logic
- Database schema and data organization strategy
- Route computation and fallback algorithms
- Frontend visualization workflow and interaction model

---

## Note

Graph cache files are generated locally and are not part of the core source code.

---

## Deployment Notes

- Designed for deployment using Gunicorn in production environments
- Graph caching implemented to reduce repeated OpenStreetMap downloads
- Debug mode disabled for production builds
- Suitable for hosting on platforms such as Render or similar cloud services

---

## License

License to be determined.
All rights reserved © 2026 Aryan Mishra.

---

## Author

Aryan Mishra  
B.Tech CSE – Manipal University Jaipur
