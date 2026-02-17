let map;
let routeLayers = [];
let markers = [];
let placeMarkerMap = {};
let isEventListenersSetup = false;

/* ---------------- INITIALIZATION ---------------- */

document.addEventListener("DOMContentLoaded", () => {
  console.log("DOM Loaded, initializing script...");
  initMap();
  setupEventListeners();

  // Check for URL params to auto-load route (e.g. from History)
  const urlParams = new URLSearchParams(window.location.search);
  const city = urlParams.get('city');
  const days = urlParams.get('days');

  if (city) {
    const cityInput = document.getElementById("priority-input");
    const daysInput = document.getElementById("days-input");
    if (cityInput) cityInput.value = city;
    if (daysInput && days) daysInput.value = days;

    // Small delay to ensure map is ready
    setTimeout(() => {
      handleRoute();
    }, 500);
  }
});

function initMap() {
  // Center roughly on India
  map = L.map("map", { zoomControl: false }).setView([22.9734, 78.6569], 5);

  // CartoDB Voyager - beautiful, colorful, clean
  L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png', {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
    subdomains: 'abcd',
    maxZoom: 20
  }).addTo(map);

  // Reposition zoom control
  L.control.zoom({
    position: 'bottomright'
  }).addTo(map);
}

function setupEventListeners() {
  if (isEventListenersSetup) return;
  isEventListenersSetup = true;

  const generateBtn = document.getElementById("generate-btn");
  const closeInstructionsBtn = document.getElementById("close-instructions");

  // Panel Toggles
  const toggleItineraryBtn = document.getElementById("toggle-itinerary");
  const openItineraryBtn = document.getElementById("open-itinerary-btn");

  if (generateBtn) {
    console.log("Generate button found, attaching listener");
    generateBtn.addEventListener("click", (e) => {
      console.log("Generate button clicked");
      e.preventDefault();
      handleRoute();
    });
  } else {
    console.error("Generate button NOT found!");
  }

  if (closeInstructionsBtn) {
    closeInstructionsBtn.addEventListener("click", () => {
      document.getElementById("route-instructions").classList.add("hidden");
    });
  }

  if (toggleItineraryBtn) {
    toggleItineraryBtn.addEventListener("click", () => {
      toggleItineraryPanel(false); // collapse
    });
  }

  if (openItineraryBtn) {
    openItineraryBtn.addEventListener("click", () => {
      toggleItineraryPanel(true); // expand
    });
  }
}

/* ---------------- UI LOGIC ---------------- */

function toggleItineraryPanel(show) {
  const panel = document.getElementById("itinerary-panel");
  const openBtn = document.getElementById("open-itinerary-btn");

  if (show) {
    panel.classList.remove("collapsed");
    openBtn.style.display = "none";
  } else {
    panel.classList.add("collapsed");
    openBtn.style.display = "block";
  }

  setTimeout(() => { map.invalidateSize(); }, 300);
}

function showLoader() {
  document.getElementById("loading-overlay").classList.remove("hidden");
}

function hideLoader() {
  document.getElementById("loading-overlay").classList.add("hidden");
}

function showToast(message, type = 'info') {
  const container = document.getElementById("toast-container");
  const toast = document.createElement("div");
  toast.className = `toast ${type}`;

  let icon = type === 'success' ? '<i class="fa-solid fa-check-circle"></i>' : '<i class="fa-solid fa-info-circle"></i>';
  if (type === 'error') icon = '<i class="fa-solid fa-exclamation-circle"></i>';

  toast.innerHTML = `${icon} <span>${message}</span>`;

  container.appendChild(toast);

  // Auto remove
  setTimeout(() => {
    toast.style.animation = "slideIn 0.3s ease-in reverse";
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

function clearMap() {
  console.log("Clearing map and state...");
  routeLayers.forEach(l => map.removeLayer(l));
  markers.forEach(m => map.removeLayer(m));
  routeLayers = [];
  markers = [];
  placeMarkerMap = {};
  document.getElementById("instruction-list").innerHTML = "";
  document.getElementById("route-instructions").classList.add("hidden");

  // Also clear itinerary container here to be safe, or just in renderItinerary
  const itineraryContainer = document.getElementById("itinerary");
  if (itineraryContainer) itineraryContainer.innerHTML = "";
}


/* ---------------- ROUTING LOGIC ---------------- */

async function handleRoute() {
  const cityInput = document.getElementById("priority-input");
  const daysInput = document.getElementById("days-input");

  if (!cityInput || !cityInput.value.trim()) {
    showToast("Please enter a destination city", "error");
    cityInput.focus();
    return;
  }

  const city = cityInput.value.trim();
  const days = parseInt(daysInput.value);

  if (isNaN(days) || days < 1 || days > 14) {
    showToast("Days must be between 1 and 14", "error");
    return;
  }

  await fetchDBRoute(city, days);
}

async function fetchDBRoute(city, days) {
  showLoader();
  clearMap(); // Ensure state is clean before we start

  console.log(`Fetching route for city: ${city}, days: ${days}`);

  // Collapse itinerary on mobile to show map initially? Or keep it open?
  // Let's keep it open if desktop, maybe collapse on mobile.
  if (window.innerWidth < 768) toggleItineraryPanel(false);

  try {
    console.log("Sending POST request to /api/db-route");
    const res = await fetch("/api/db-route", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ city, days })
    });

    console.log("Fetch response received:", res.status, res.url);

    if (res.redirected && res.url.includes("/login")) {
      showToast("Session expired. Please log in again.", "error");
      setTimeout(() => window.location.href = "/login", 2000);
      return;
    }

    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      console.error("Server Error Details:", errData);
      throw new Error(`Server error: ${res.status} - ${errData.message || res.statusText}`);
    }
    const data = await res.json();

    if (!data || data.status !== "success" || !Array.isArray(data.days)) {
      showToast("Could not generate itinerary. Try another city.", "error");
      return;
    }

    showToast(`Itinerary generated for ${data.days.length} days!`, "success");

    // Center map
    if (data.city && (data.city.lat || data.city.latitude) && (data.city.lng || data.city.longitude)) {
      const lat = data.city.lat || data.city.latitude;
      const lng = data.city.lng || data.city.longitude;
      map.setView([lat, lng], 12);
    }

    renderRoutes(data.days);
    renderItinerary(data.days);

    // Open panel if collapsed
    toggleItineraryPanel(true);

  } catch (err) {
    console.error(err);
    showToast("Something went wrong. Please check console.", "error");
  } finally {
    hideLoader();
  }
}

/* ---------------- RENDERING ---------------- */

const routeColors = ["#4f46e5", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6"];

function createCustomIcon(number, color) {
  return L.divIcon({
    className: 'custom-marker',
    html: `<div style="
            background-color: ${color};
            width: 24px;
            height: 24px;
            border-radius: 50%;
            border: 2px solid white;
            box-shadow: 0 2px 4px rgba(0,0,0,0.3);
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-weight: bold;
            font-size: 12px;
            position: relative;
        ">
            <div class="marker-pulse" style="color: ${color}; border-color: ${color};"></div>
            ${number}
        </div>`,
    iconSize: [24, 24],
    iconAnchor: [12, 12],
    popupAnchor: [0, -12]
  });
}

function renderRoutes(days) {
  const allLatLngs = [];
  let anyRouteDrawn = false;
  let instructionHtml = "";

  days.forEach((day, dayIdx) => {
    const color = routeColors[dayIdx % routeColors.length];

    // Markers
    if (Array.isArray(day.places)) {
      day.places.forEach((place, placeIdx) => {
        const lat = place.lat || place.latitude;
        const lng = place.lng || place.longitude;

        if (lat && lng) {
          const marker = L.marker([lat, lng], {
            icon: createCustomIcon(placeIdx + 1, color)
          }).addTo(map);

          const popupContent = `
                    <div style="min-width: 200px;">
                        <h4 style="margin:0 0 5px 0; color:${color}; font-weight:700;">${place.name}</h4>
                        <div style="font-size:12px; color:#555;">
                            <p style="margin:2px 0;"><strong>Time:</strong> ${place.best_time_to_visit || "Daytime"}</p>
                            <p style="margin:2px 0;"><strong>Ticket:</strong> ${place.ticket_price || "Free"}</p>
                        </div>
                    </div>
                `;

          marker.bindPopup(popupContent);
          markers.push(marker);
          placeMarkerMap[place.name] = marker;
        }
      });
    }

    // Routes (Polylines)
    if (Array.isArray(day.route) && day.route.length > 0) {
      // Flatten logic for different route formats
      let segments = [];

      // Check structure: [[lat,lng],...] vs [[[lat,lng]...],...]
      if (Array.isArray(day.route[0]) && typeof day.route[0][0] === "number") {
        segments.push(day.route); // Single segment
      } else {
        segments = day.route; // Multiple segments
      }

      segments.forEach(segment => {
        if (!Array.isArray(segment) || segment.length < 2) return;

        // Glow/Shadow effect
        const glowPolyline = L.polyline(segment, {
          color: color,
          weight: 10,
          opacity: 0.3,
          className: 'route-glow'
        }).addTo(map).bringToBack();
        routeLayers.push(glowPolyline);

        const polyline = L.polyline(segment, {
          color: color,
          weight: 5,
          opacity: 1.0,
          lineCap: 'round',
          lineJoin: 'round'
        }).addTo(map);
        routeLayers.push(polyline);

        anyRouteDrawn = true;

        segment.forEach(pt => allLatLngs.push(pt));
      });
    }
  });

  if (anyRouteDrawn && allLatLngs.length > 0) {
    map.fitBounds(allLatLngs, { padding: [50, 50] });
  }
}


function renderItinerary(days) {
  console.log("Rendering Itinerary...", days);
  const container = document.getElementById("itinerary");
  if (!container) return;

  // Crucial: Clear container first
  container.innerHTML = "";

  days.forEach((day, idx) => {
    const dayColor = routeColors[idx % routeColors.length];

    const dayCard = document.createElement("div");
    dayCard.className = "day-card";

    // Header
    const header = document.createElement("div");
    header.className = "day-header";
    // Check if day.day already has "Day" prefix
    const dayLabel = day.day.toString().toLowerCase().startsWith("day") ? day.day : `Day ${day.day}`;

    header.innerHTML = `
        <span style="color: ${dayColor}">${dayLabel}</span>
        <span class="text-xs text-muted">${day.places.length} stops</span>
    `;
    dayCard.appendChild(header);

    // Places List
    const placeList = document.createElement("div");

    day.places.forEach((place, placeIdx) => {
      const item = document.createElement("div");
      item.className = "place-item";

      // CSS trick for strict coloring of the dot using variable not fully supported inline easily without style attr
      // We'll use border-left instead for easy visualization or custom style
      item.style.borderLeft = `3px solid transparent`;

      item.innerHTML = `
            <div class="place-name">${placeIdx + 1}. ${place.name}</div>
            <div class="place-meta">${place.category || "Sightseeing"} • ${place.time_spent || "1h"}</div>
        `;

      item.addEventListener("mouseenter", () => {
        item.style.borderLeftColor = dayColor;
        item.style.backgroundColor = "var(--color-surface-hover)";
        // Highlight marker
        const marker = placeMarkerMap[place.name];
        if (marker) {
          marker.setOpacity(1);
          marker._icon.style.transform += " scale(1.2)";
        }
      });

      item.addEventListener("mouseleave", () => {
        item.style.borderLeftColor = "transparent";
        item.style.backgroundColor = "";
        const marker = placeMarkerMap[place.name];
        if (marker) {
          marker._icon.style.transform = marker._icon.style.transform.replace(" scale(1.2)", "");
        }
      });

      item.addEventListener("click", () => {
        const marker = placeMarkerMap[place.name];
        if (marker) {
          map.setView(marker.getLatLng(), 15);
          marker.openPopup();
          // Mobile: close panel to see map
          if (window.innerWidth < 768) toggleItineraryPanel(false);
        }
      });

      placeList.appendChild(item);
    });

    dayCard.appendChild(placeList);
    container.appendChild(dayCard);
  });
}