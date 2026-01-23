let map;
let routeLayers = [];
let markers = [];

/* ---------------- MAP INIT ---------------- */

document.addEventListener("DOMContentLoaded", () => {
  initMap();
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
  const input = document.getElementById("priority-input");
  if (!input || !input.value.trim()) {
    alert("Enter a city name");
    return;
  }

  const city = input.value.trim();
  const days = 3;

  fetchDBRoute(city, days);
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
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ city, days })
    });

    if (!res.ok) throw new Error("Backend error");

    const data = await res.json();

    if (!data || data.status !== "success" || !Array.isArray(data.days)) {
      alert("Could not load itinerary data");
      return;
    }

    // Center map on city if available
    if (data.city && data.city.lat && data.city.lng) {
      map.setView([data.city.lat, data.city.lng], 12);
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
    if (!Array.isArray(day.route) || day.route.length === 0) {
      console.warn(`Skipping route for ${day.day}`);
      return;
    }

    day.route.forEach((segment, segIdx) => {
      if (!Array.isArray(segment) || segment.length < 2) return;

      const animatedRoute = animatePolyline(segment, {
        color: routeColors[idx % routeColors.length],
        weight: 5,
        delay: 18
      });

      routeLayers.push(animatedRoute);
      anyRouteDrawn = true;

      segment.forEach(p => allLatLngs.push(p));

      // Start marker (once per day)
      if (segIdx === 0) {
        markers.push(
          L.marker(segment[0])
            .addTo(map)
            .bindPopup(`${day.day} – Start`)
        );
      }

      // End marker (last segment only)
      if (segIdx === day.route.length - 1) {
        markers.push(
          L.marker(segment[segment.length - 1])
            .addTo(map)
            .bindPopup(`${day.day} – End`)
        );
      }
    });
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
      li.innerHTML = `
        <strong>${place}</strong><br/>
        <span class="itinerary-note">Popular tourist spot</span>
      `;
      list.appendChild(li);
    });

    dayCard.appendChild(list);
    container.appendChild(dayCard);
  });
}