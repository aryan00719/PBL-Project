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

          // ── Build popup as a real DOM node so Leaflet's HTML sanitizer
          //    (v1.9+) cannot strip class/style/onerror attributes ──────
          const img      = place.image_url        ? place.image_url.trim()   : '';
          const desc     = place.description      ? place.description.trim() : '';
          const ticket   = place.ticket_price     || 'Free';
          const bestTime = place.best_time_to_visit || 'Anytime';
          const openHrs  = (place.opening_time && place.closing_time)
                           ? `${place.opening_time} – ${place.closing_time}` : '';
          const duration = place.visit_duration   || '';

          // Root card
          const card = document.createElement('div');
          card.className = 'ag-popup';

          // Hero image
          if (img) {
            const imgWrap = document.createElement('div');
            imgWrap.className = 'ag-popup-img-wrap';

            const imgEl = document.createElement('img');
            imgEl.className = 'ag-popup-img';
            imgEl.src   = img;
            imgEl.alt   = place.name;
            imgEl.onerror = () => { imgWrap.style.display = 'none'; };

            imgWrap.appendChild(imgEl);
            card.appendChild(imgWrap);
          }

          // Body
          const body = document.createElement('div');
          body.className = 'ag-popup-body';

          const title = document.createElement('h4');
          title.className   = 'ag-popup-title';
          title.style.color = color;
          title.textContent = place.name;
          body.appendChild(title);

          if (desc) {
            const p = document.createElement('p');
            p.className   = 'ag-popup-desc';
            p.textContent = desc;
            body.appendChild(p);
          }

          // Info chips
          const chips = document.createElement('div');
          chips.className = 'ag-popup-chips';

          const makeChip = (emoji, text) => {
            const s = document.createElement('span');
            s.className   = 'ag-chip';
            s.textContent = `${emoji} ${text}`;
            return s;
          };

          chips.appendChild(makeChip('🎟', ticket));
          chips.appendChild(makeChip('⏰', bestTime));
          if (openHrs)  chips.appendChild(makeChip('🕐', openHrs));
          if (duration) chips.appendChild(makeChip('⏱', duration));

          body.appendChild(chips);
          card.appendChild(body);

          // Bind using an explicit L.popup instance wrapping the DOM node
          // This prevents DOM detachment issues on repetitive clicks
          const popup = L.popup({ maxWidth: 300, className: 'ag-leaflet-popup' }).setContent(card);
          marker.bindPopup(popup);
          
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

    // --- FALLBACK: draw straight-line path for any places not covered by OSMnx routes ---
    // This guarantees every day has a visible connection even when the graph fails.
    days.forEach((day) => {
      if (!Array.isArray(day.places) || day.places.length < 2) return;

      const placeLatLngs = day.places.map(p => {
        const lat = p.lat || p.latitude;
        const lng = p.lng || p.longitude;
        return (lat && lng) ? [lat, lng] : null;
      }).filter(Boolean);

      if (placeLatLngs.length < 2) return;

      // Only draw the fallback dashes if the day has no OSMnx route at all
      const hasRealRoute = Array.isArray(day.route) && day.route.length > 1;
      if (!hasRealRoute) {
        const dayIdx = days.indexOf(day);
        const color = routeColors[dayIdx % routeColors.length];

        // Dashed fallback line
        const fallback = L.polyline(placeLatLngs, {
          color: color,
          weight: 3,
          opacity: 0.7,
          dashArray: '8 6',
          lineCap: 'round',
          lineJoin: 'round'
        }).addTo(map);
        routeLayers.push(fallback);
        placeLatLngs.forEach(pt => allLatLngs.push(pt));
        anyRouteDrawn = true;
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

  container.innerHTML = "";

  days.forEach((day, idx) => {
    const dayColor = routeColors[idx % routeColors.length];

    const dayCard = document.createElement("div");
    dayCard.className = "day-card";

    // Header
    const header = document.createElement("div");
    header.className = "day-header";
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
      item.id = `itinerary-${place.name.replace(/\W+/g, '-')}`;
      item.style.borderLeft = `3px solid transparent`;
      item.style.transition = "background-color 0.2s, border-left-color 0.2s";

      item.innerHTML = `
          <div class="place-header" style="display:flex; justify-content:space-between; align-items:center; cursor:pointer;">
              <div>
                  <div class="place-name">${placeIdx + 1}. ${place.name}</div>
                  <div class="place-meta">${place.category || "Sightseeing"} • ${place.visit_duration || place.time_spent || "1h"}</div>
              </div>
              <button class="btn btn-ghost btn-sm dropdown-trigger" style="padding: 0 8px;"><i class="fa-solid fa-chevron-down"></i></button>
          </div>
          <div class="place-details hidden" style="font-size: 0.83rem; color: var(--text-muted); margin-top: 8px; padding: 10px; border-radius: 6px; background: rgba(0,0,0,0.03); display: none;">
              <div style="margin-bottom: 4px;"><strong>Category:</strong> ${place.category || 'N/A'}</div>
              <div style="margin-bottom: 4px;"><strong>Best Time:</strong> ${place.best_time_to_visit || 'Anytime'}</div>
              <div style="margin-bottom: 4px;"><strong>Hours:</strong> ${(place.opening_time && place.closing_time) ? `${place.opening_time} - ${place.closing_time}` : 'Varies'}</div>
              <div><strong>Ticket:</strong> ${place.ticket_price || 'Free'}</div>
          </div>
      `;

      const headerDiv = item.querySelector('.place-header');
      const dropdownBtn = item.querySelector('.dropdown-trigger');
      const detailsDiv = item.querySelector('.place-details');

      dropdownBtn.addEventListener("click", (e) => {
          e.stopPropagation();
          if (detailsDiv.style.display === "none") {
              detailsDiv.style.display = "block";
              dropdownBtn.innerHTML = '<i class="fa-solid fa-chevron-up"></i>';
          } else {
              detailsDiv.style.display = "none";
              dropdownBtn.innerHTML = '<i class="fa-solid fa-chevron-down"></i>';
          }
      });

      const marker = placeMarkerMap[place.name];

      // Setup Two-Way Sync Logic on Marker Click
      if (marker) {
          marker.on('click', () => {
              // Center map smoothly to zoom 14 instead of jumping wildly
              map.flyTo(marker.getLatLng(), 14, { animate: true, duration: 0.8 });

              // Reset global iteration highlights
              document.querySelectorAll('.place-item').forEach(el => {
                  el.style.borderLeftColor = 'transparent';
                  el.style.backgroundColor = '';
              });

              // Highlight specific item
              item.style.borderLeftColor = dayColor;
              item.style.backgroundColor = "var(--color-surface-hover)";

              // Scroll to it if the panel is open
              const panel = document.getElementById("itinerary-panel");
              if (panel && !panel.classList.contains("collapsed")) {
                  item.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
              }
          });
      }

      // Handle hover highlight for map interaction
      item.addEventListener("mouseenter", () => {
          if (item.style.backgroundColor !== "var(--color-surface-hover)") {
              item.style.borderLeftColor = dayColor;
          }
          if (marker) {
              marker.setOpacity(1);
              marker._icon.style.transform += " scale(1.2)";
          }
      });

      item.addEventListener("mouseleave", () => {
          // If not currently "active" via click, reset border
          if (item.style.backgroundColor !== "var(--color-surface-hover)") {
              item.style.borderLeftColor = "transparent";
          }
          if (marker) {
              marker._icon.style.transform = marker._icon.style.transform.replace(" scale(1.2)", "");
          }
      });

      // Handle card click to focus map
      headerDiv.addEventListener("click", () => {
          if (marker) {
              if (window.innerWidth < 768) {
                  toggleItineraryPanel(false);
              }
              // Fire the marker's click event so we get identical behavior (highlight + center)
              setTimeout(() => {
                  marker.fire('click');
                  marker.openPopup(); // Ensure popup opens
              }, window.innerWidth < 768 ? 320 : 0);
          }
      });

      placeList.appendChild(item);
    });

    dayCard.appendChild(placeList);
    container.appendChild(dayCard);
  });
}