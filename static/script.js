let map;
let routeLayers = [];
let markers = [];

let placeMarkerMap = {};

/* ---------------- MAP INIT ---------------- */

document.addEventListener("DOMContentLoaded", () => {
  initMap();

  const generateBtn = document.getElementById("generate-btn");
  if (generateBtn) {
    generateBtn.addEventListener("click", (e) => {
      e.preventDefault();
      handleRoute();
    });
  }
});

function initMap() {
  map = L.map("map").setView([22.9734, 78.6569], 5); // India center

  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: "© OpenStreetMap"
  }).addTo(map);
}

/* ---------------- HELPERS ---------------- */

function clearMap() {
  routeLayers.forEach(l => map.removeLayer(l));
  markers.forEach(m => map.removeLayer(m));
  routeLayers = [];
  markers = [];
  placeMarkerMap = {};
}

function showLoader() {
  const l = document.getElementById("loading-overlay");
  if (l) l.style.display = "flex";
}

function hideLoader() {
  const l = document.getElementById("loading-overlay");
  if (l) l.style.display = "none";
}

/* ---------------- MAIN ROUTE HANDLER ---------------- */

async function handleRoute() {
  const cityInput = document.getElementById("priority-input");
  const daysInput = document.getElementById("days-input");

  if (!cityInput || !cityInput.value.trim()) {
    alert("Please enter a city name.");
    return;
  }

  if (!daysInput || !daysInput.value) {
    alert("Please enter number of days.");
    return;
  }

  const city = cityInput.value.trim();
  const days = parseInt(daysInput.value);

  if (isNaN(days) || days < 1 || days > 14) {
    alert("Days must be between 1 and 14.");
    return;
  }

  await fetchDBRoute(city, days);
}

/* ---------------- ANIMATED POLYLINE ---------------- */

function animatePolyline(latLngs, options = {}) {
  const {
    color = "blue",
    weight = 5,
    delay = 15
  } = options;

  let index = 0;
  const animatedLine = L.polyline([], {
    color,
    weight,
    opacity: 0.9,
    lineCap: "round",
    lineJoin: "round"
  }).addTo(map);

  const interval = setInterval(() => {
    if (index >= latLngs.length) {
      clearInterval(interval);
      return;
    }
    animatedLine.addLatLng(latLngs[index]);
    index++;
  }, delay);

  return animatedLine;
}

/* ---------------- FETCH FROM BACKEND ---------------- */

async function fetchDBRoute(city, days) {
  showLoader();
  clearMap();

  try {
    const res = await fetch("/api/db-route", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      credentials: "same-origin",
      body: JSON.stringify({
        city: city,
        days: days
      })
    });

    if (!res.ok) throw new Error("Backend error");

    const data = await res.json();

    if (!data || data.status !== "success" || !Array.isArray(data.days)) {
      alert("Could not load itinerary data");
      return;
    }

    // Center map on city if available
    if (data.city && (data.city.lat || data.city.latitude) && (data.city.lng || data.city.longitude)) {
      const lat = data.city.lat || data.city.latitude;
      const lng = data.city.lng || data.city.longitude;
      map.setView([lat, lng], 12);
    }

    renderRoutes(data.days);
    renderItinerary(data.days);

    console.log("DB days:", data.days);
  } catch (err) {
    console.error("Routing error:", err);
  } finally {
    hideLoader();
  }

  setTimeout(() => {
    map.invalidateSize(true);
  }, 800);
}

/* ---------------- ROUTE DRAWING (FIXED) ---------------- */

const routeColors = ["#1E90FF", "#32CD32", "#FF8C00", "#8A2BE2"];

function renderRoutes(days) {
  const allLatLngs = [];
  let anyRouteDrawn = false;

  days.forEach((day, idx) => {

    /* ---- DRAW ROUTES ---- */
    if (Array.isArray(day.route) && day.route.length > 0) {

      // CASE 1: Flat route array [[lat,lng], [lat,lng], ...]
      if (Array.isArray(day.route[0]) && typeof day.route[0][0] === "number") {

        if (day.route.length >= 2) {
          const animatedRoute = animatePolyline(day.route, {
            color: routeColors[idx % routeColors.length],
            weight: 5,
            delay: 18
          });

          routeLayers.push(animatedRoute);
          anyRouteDrawn = true;

          day.route.forEach(p => {
            if (Array.isArray(p) && p.length === 2) {
              allLatLngs.push([p[0], p[1]]);
            }
          });
        }

      } else {

        // CASE 2: Nested segments [[[lat,lng]...], [[lat,lng]...]]
        day.route.forEach((segment) => {
          if (!Array.isArray(segment) || segment.length < 2) return;

          const animatedRoute = animatePolyline(segment, {
            color: routeColors[idx % routeColors.length],
            weight: 5,
            delay: 18
          });

          routeLayers.push(animatedRoute);
          anyRouteDrawn = true;

          segment.forEach(p => {
            if (Array.isArray(p) && p.length === 2) {
              allLatLngs.push([p[0], p[1]]);
            }
          });
        });

      }
    }

    /* ---- CREATE PLACE MARKERS ---- */
    if (Array.isArray(day.places)) {
      day.places.forEach(place => {

        const lat = place.lat || place.latitude;
        const lng = place.lng || place.longitude;

        if (!lat || !lng) return;

        const popupHTML = `
          <div class="popup-card">
            <h4>${place.name}</h4>
            <p><strong>Category:</strong> ${place.category || "Tourist Place"}</p>
            <p><strong>Best Time:</strong> ${place.best_time_to_visit || "Morning"}</p>
            <p><strong>Opening:</strong> ${place.opening_time || "Not Available"}</p>
            <p><strong>Closing:</strong> ${place.closing_time || "Not Available"}</p>
            <p><strong>Ticket Price:</strong> ${place.ticket_price || "Free"}</p>
          </div>
        `;

        const marker = L.marker([lat, lng])
          .addTo(map)
          .bindPopup(popupHTML);

        markers.push(marker);

        if (place.name) {
          placeMarkerMap[place.name] = marker;
        }
      });
    }
  });

  if (anyRouteDrawn && allLatLngs.length > 0) {
    map.fitBounds(allLatLngs, { padding: [40, 40] });
  } else {
    console.warn("No valid routes drawn");
  }
}

/* ---------------- ITINERARY UI ---------------- */

function renderItinerary(days) {
  const container = document.getElementById("itinerary");
  if (!container) return;

  container.innerHTML = "";

  days.forEach(day => {
    const dayCard = document.createElement("div");
    dayCard.className = "itinerary-card";

    const title = document.createElement("h3");
    title.textContent = day.day;
    dayCard.appendChild(title);

    const list = document.createElement("ul");

    day.places.forEach(place => {
      const li = document.createElement("li");
      li.style.cursor = "pointer";

      li.innerHTML = `
        <strong>${place.name}</strong><br/>
        <span class="itinerary-note">
          ${place.category || "Popular tourist spot"}
        </span>
      `;

      li.addEventListener("click", () => {
        const marker = placeMarkerMap[place.name];
        if (marker) {
          map.setView(marker.getLatLng(), 14);
          marker.openPopup();
        }
      });

      list.appendChild(li);
    });

    dayCard.appendChild(list);
    container.appendChild(dayCard);
  });
}