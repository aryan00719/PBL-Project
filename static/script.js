let map, userMarker, markers = [];
window.currentMarkers = [];
let routingControl = null;

const planeIcon = L.icon({
  iconUrl: 'https://cdn-icons-png.flaticon.com/512/34/34627.png',
  iconSize: [32, 32],
  iconAnchor: [16, 16]
});

// Define custom icons for categories
const categoryIcons = {
  culture: L.icon({
    iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-green.png',
    iconSize: [25, 41],
    iconAnchor: [12, 41]
  }),
  food: L.icon({
    iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-red.png',
    iconSize: [25, 41],
    iconAnchor: [12, 41]
  }),
  adventure: L.icon({
    iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-orange.png',
    iconSize: [25, 41],
    iconAnchor: [12, 41]
  }),
  nature: L.icon({
    iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-yellow.png',
    iconSize: [25, 41],
    iconAnchor: [12, 41]
  })
};

// Geocode a place name using OpenStreetMap Nominatim API
const geocodePlace = async (placeName) => {
  const url = `https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(placeName)}`;
  try {
    const res = await fetch(url);
    const data = await res.json();
    if (data.length > 0) {
      return { lat: parseFloat(data[0].lat), lng: parseFloat(data[0].lon) };
    } else {
      console.warn("🌐 No geocode result for:", placeName);
      return null;
    }
  } catch (err) {
    console.error("🌐 Geocode error:", err);
    return null;
  }
};

document.addEventListener('DOMContentLoaded', () => {
  initMap();
  hideLoader();
});

// Function to initialize the Leaflet map
function initMap() {
  map = L.map('map', {
    zoomControl: false
  }).setView([28.6139, 77.2090], 12);

  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '© OpenStreetMap contributors'
  }).addTo(map);

  L.control.zoom({ position: 'topright' }).addTo(map);
  // Invalidate size to ensure proper display after container changes
  setTimeout(() => map.invalidateSize(), 100);
}

// Toggle sidebar visibility and update map layout
function toggleSidebar() {
  const sidebar = document.getElementById('sidebar');
  sidebar.classList.toggle('active');
  setTimeout(() => {
    map.invalidateSize();
  }, 300);
}

// Get recommendations based on selected travel categories
async function getRecommendations() {
  clearMarkers();
  const selected = Array.from(document.querySelectorAll('.category:checked')).map(cb => cb.value);
  const bounds = L.latLngBounds();

  try {
    const res = await fetch('/static/data/delhi_places.json');
    if (!res.ok) throw new Error("Failed to load places data");
    const placeData = await res.json();

    selected.forEach(cat => {
      placeData[cat]?.forEach(loc => {
        const marker = L.marker([loc.lat, loc.lng], { icon: categoryIcons[cat] })
          .addTo(map)
          .bindPopup(`<div class="popup-header">${loc.name}</div><div class="popup-content">${loc.details}</div>`);
        markers.push(marker);
        bounds.extend(marker.getLatLng());
      });
    });

    if (markers.length > 0) {
      map.fitBounds(bounds.pad(0.1));
    }
  } catch (err) {
    console.error("Error loading recommendations:", err);
    alert("Could not load recommendations.");
  }
}

// Remove all markers from the map
function clearMarkers() {
  markers.forEach(marker => map.removeLayer(marker));
  markers = [];
}

// Remove all markers from both markers and window.currentMarkers arrays
function clearAllMarkers() {
  if (window.currentMarkers) {
    window.currentMarkers.forEach(marker => map.removeLayer(marker));
    window.currentMarkers = [];
  }
  if (markers && markers.length > 0) {
    markers.forEach(marker => map.removeLayer(marker));
    markers = [];
  }
}

// Use the browser's geolocation API to find and mark the user's location
function findNearby() {
  if (!navigator.geolocation) return alert("Geolocation not supported");

  navigator.geolocation.getCurrentPosition(position => {
    const { latitude, longitude } = position.coords;
    if (userMarker) map.removeLayer(userMarker);

    userMarker = L.marker([latitude, longitude], {
      icon: L.icon({
        iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-blue.png',
        iconSize: [25, 41],
        iconAnchor: [12, 41]
      })
    }).addTo(map).bindPopup("Your Location").openPopup();

    map.setView([latitude, longitude], 14);
  }, error => {
    alert("Error retrieving location: " + error.message);
  });
}

// Mapping from place names to coordinates for route planning
const placeToCoords = {
  jaipur: [26.9124, 75.7873],
  ajmer: [26.4499, 74.6399],
  pushkar: [26.4890, 74.5510],
  delhi: [28.6139, 77.2090],
  agra: [27.1767, 78.0081],
  redfort: [28.6562, 77.2410],
  qutubminar: [28.5245, 77.1855],
  chandnichowk: [28.6564, 77.2303],
  indiagate: [28.6129, 77.2295],
  humayunstomb: [28.5933, 77.2507],
  lotustemple: [28.5535, 77.2588]
};

// Plan a route based on user-entered destinations
function planRoute() {
  showLoader();
  const input = document.getElementById('priority-input').value.trim();
  if (!input) {
    hideLoader();
    return alert("Enter destinations");
  }

  const places = input.split(',').map(p => p.trim().toLowerCase());
  const coords = [];
  const unknown = [];

  places.forEach(p => {
    if (placeToCoords[p]) {
      coords.push(L.latLng(...placeToCoords[p]));
    } else {
      unknown.push(p);
    }
  });

  if (unknown.length) {
    hideLoader();
    return alert("Unknown locations: " + unknown.join(', '));
  }

  if (places.length > 0) {
    fetchItinerary(places);
  }

  if (routingControl) map.removeControl(routingControl);

  routingControl = L.Routing.control({
    waypoints: coords,
    router: L.Routing.osrmv1({ serviceUrl: 'https://router.project-osrm.org/route/v1' }),
    routeWhileDragging: false,
    lineOptions: { styles: [{ color: '#0074D9', weight: 5 }] },
    createMarker: () => null,   // 🚫 disable default markers
    show: false,
    errorHandler: (err) => alert("Routing error: " + err.message)
  }).addTo(map);

  // Once the route is successfully calculated, suggest local food options
  routingControl.on('routesfound', suggestLocalFood);
  hideLoader();
}

// Provide food suggestions along the planned route
function suggestLocalFood() {
  const foods = [
    "Dal Baati Churma in Jaipur 🍲",
    "Street chaat in Ajmer 🧆",
    "Pushkar's rose lassi 🌹🥤",
    "Parathas in Delhi 🫓",
    "Agra's Petha sweets 🍬"
  ];

  const list = document.getElementById('food-list');
  list.innerHTML = foods.map(food => `<li>${food}</li>`).join('');

  // Show the food suggestions section
  document.getElementById('food-section').style.display = 'block';
}

async function submitAIPrompt() {
  let prompt = document.getElementById('ai-prompt-input').value.trim();
  prompt = prompt.replace(/\(([^)]+)\)/g, '$1') // keep content inside brackets
    .replace(/south india/gi, '') // remove vague region
    .replace(/[-→]/g, ',') // normalize separators
    .replace(/\s+/g, ' ') // clean up extra spaces
    .trim();
  if (!prompt) return alert("Please enter your travel request.");

  showLoader();
  try {
    const res = await fetch('/api/ai-route', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt })
    });

    if (!res.ok) {
      const text = await res.text();
      console.error("🛑 Backend error response:", text);
      alert(`AI route error (HTTP ${res.status}):\n${text}`);
      hideLoader();
      return;
    }

    const data = await res.json();
    console.log("📦 Raw AI response JSON:", data);

    // --- Route array conversion fix ---
    if (Array.isArray(data.route)) {
      if (
        data.route.length > 0 &&
        Array.isArray(data.route[0]) &&
        typeof data.route[0][0] === 'number' &&
        typeof data.route[0][1] === 'number'
      ) {
        data.route = data.route.map(coord => ({
          lat: coord[0],
          lng: coord[1]
        }));
        console.log("🔁 Converted route array from [lat, lng] to { lat, lng } format.");
      } else if (
        typeof data.route[0]?.lat === 'number' &&
        typeof data.route[0]?.lng === 'number'
      ) {
        console.log("✅ Route already in { lat, lng } format.");
      } else {
        console.warn("⚠️ Unexpected route format:", JSON.stringify(data.route, null, 2));
      }
    }
    // Show route instructions if available
    if (Array.isArray(data.instructions) && data.instructions.length > 0) {
      const enriched = data.instructions.map(instr => {
        const match = instr.match(/(go|head)\s+(\w+)/i);
        return {
          instruction: instr,
          direction: match ? match[2] : 'forward',
          distance: instr.match(/(\d+)\s?m/i)?.[1] || ''
        };
      });
      renderInstructions(enriched);
    } else {
      console.warn("⚠️ No instructions received or format invalid.");
    }

    try {
      if (data.status !== 'success') throw new Error(data.message);

      // Filter out invalid coordinates
      const validRoute = (data.route || []).filter(coord => (
        coord && typeof coord.lat === 'number' && typeof coord.lng === 'number'
      ));

      // Fallback if route is missing: use placeToCoords for known places
      if (validRoute.length < 2 && Array.isArray(data.places)) {
        // Remove all previous markers before rendering fallback markers
        clearAllMarkers();
        // Only one start and one end marker, and a dashed line between them
        if (data.places.length >= 2) {
          const start = data.places[0];
          const end = data.places[data.places.length - 1];

          const startCoord = validRoute[0] || { lat: 28.6139, lng: 77.2090 }; // Delhi fallback
          const endCoord = validRoute[1] || { lat: 28.6139, lng: 77.2190 };

          const startMarker = L.marker([startCoord.lat, startCoord.lng]).addTo(map).bindPopup(`<b>🚩Start: ${start}</b>`);
          const endMarker = L.marker([endCoord.lat, endCoord.lng]).addTo(map).bindPopup(`<b>End: ${end}</b>`);

          markers.push(startMarker, endMarker);
          window.currentMarkers.push(startMarker, endMarker);

          const fallbackLine = L.polyline([[startCoord.lat, startCoord.lng], [endCoord.lat, endCoord.lng]], {
            color: 'gray',
            dashArray: '5, 5'
          }).addTo(map);

          map.fitBounds(fallbackLine.getBounds().pad(0.1));
        } else if (data.places.length === 1) {
          const fallbackLatLng = L.latLng(28.6139, 77.2090); // Delhi center
          const marker = L.marker(fallbackLatLng).addTo(map).bindPopup(`<b>${data.places[0]}</b>`);
          markers.push(marker);
          window.currentMarkers.push(marker);
          map.setView(fallbackLatLng, 13);
        }
      }

      // Extra last-resort fuzzy mapping if nothing matched above
      if (validRoute.length === 0 && Array.isArray(data.places) && data.places.length > 0) {
        console.warn("⚠️ No matched coordinates from known places. Attempting last-resort mapping.");
        data.places.forEach(p => {
          if (typeof p !== 'string') {
            if (typeof p.name === 'string') {
              const name = p.name.toLowerCase().replace(/[^a-z]/g, '');
              for (const key in placeToCoords) {
                if (name.includes(key)) {
                  validRoute.push({ lat: placeToCoords[key][0], lng: placeToCoords[key][1] });
                  console.log("🔄 Last-resort fuzzy match (object):", p.name, "→", key);
                  break;
                }
              }
            } else {
              console.warn("⚠️ Skipping non-string place without name:", p);
            }
            return;
          }
          const name = p.toLowerCase().replace(/[^a-z]/g, '');
          for (const key in placeToCoords) {
            if (name.includes(key)) {
              validRoute.push({ lat: placeToCoords[key][0], lng: placeToCoords[key][1] });
              console.log("🔄 Last-resort fuzzy match:", p, "→", key);
              break;
            }
          }
        });
      }

      if (validRoute.length === 0) {
        console.warn("No coordinates in route field, falling back to known location matching.");
      }
      // Debug: log validRoute after construction
      console.log("✅ ValidRoute computed:", validRoute);
      // Debug: log route length before planning
      console.log("⚠️ Route length before planning:", validRoute.length);
      // ✅ Only now do the final validation check
      if (validRoute.length < 2) {
        console.warn("🚫 Not enough valid coordinates for routing (even after fallback):", JSON.stringify(validRoute, null, 2));

        // Remove all previous markers before rendering fallback markers
        clearAllMarkers();

        // If places exist, show only start/end marker using existing start/end coordinates if possible
        // Commented out fallback marker rendering loop (see above for removal)
        // Clean start/end marker-only logic using existing start/end coordinates
        if (data.places && data.places.length >= 2) {
          const start = data.places[0];
          const end = data.places[data.places.length - 1];

          const startCoord = validRoute[0];
          const endCoord = validRoute[validRoute.length - 1];

          const startMarker = L.marker([startCoord.lat, startCoord.lng]).addTo(map).bindPopup(`<b>Start: ${start}</b>`);
          const endMarker = L.marker([endCoord.lat, endCoord.lng]).addTo(map).bindPopup(`<b>End: ${end}</b>`);

          markers.push(startMarker, endMarker);
          window.currentMarkers.push(startMarker, endMarker);

          const fallbackLine = L.polyline([[startCoord.lat, startCoord.lng], [endCoord.lat, endCoord.lng]], {
            color: 'gray',
            dashArray: '5, 5'
          }).addTo(map);
          map.fitBounds(fallbackLine.getBounds().pad(0.1));
        } else if (data.places && data.places.length === 1) {
          // If only 1 place, fallback to showing a single marker at Delhi center
          const fallbackLatLng = L.latLng(28.6139, 77.2090); // Delhi center
          const marker = L.marker(fallbackLatLng).addTo(map).bindPopup(`<b>${data.places[0]}</b>`);
          markers.push(marker);
          window.currentMarkers.push(marker);
          map.setView(fallbackLatLng, 13);
        }

        alert("Could not generate full route, but places are shown on the map.");
        hideLoader();
        return;
      }

      clearAllMarkers();

      if (routingControl) {
        routingControl.getPlan().setWaypoints([]);
        map.removeControl(routingControl);
        routingControl = null;
      }

      console.log("AI Places:", data.places);
      // --- Debugging output for AI response fields ---
      if (!Array.isArray(data.places) || data.places.length === 0) {
        console.warn("⚠️ Warning: No places returned from AI response.");
      }
      if (!Array.isArray(data.route)) {
        console.warn("⚠️ Warning: No route array returned from AI response.");
      }
      if (Array.isArray(data.route) && data.route.length > 0) {
        console.info("✅ Route returned with " + data.route.length + " coordinates.");
      }
      if (Array.isArray(data.itinerary)) {
        console.info("🗓️ Itinerary received with " + data.itinerary.length + " days.");
      }
      console.log("AI Route:", data.route);

      // --- Only show one start marker and one end marker with custom icons and popups ---
      if (validRoute.length >= 2) {
        // Remove old route if it exists
        if (window.routeLayer) {
          map.removeLayer(window.routeLayer);
        }

        // Draw the polyline for the full route
        const routeLatLngs = validRoute.map(coord => [coord.lat, coord.lng]);
        window.routeLayer = L.polyline(routeLatLngs, { color: "blue", weight: 5 }).addTo(map);
        map.fitBounds(window.routeLayer.getBounds());

        // Only add one green start marker and one red end marker
        if (Array.isArray(data.places) && data.places.length > 0) {
          const start = data.places[0];
          const end = data.places[data.places.length - 1];

          // Start marker (green pin)
          const startMarker = L.marker([validRoute[0].lat, validRoute[0].lng], {
            icon: L.icon({
              iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-green.png',
              shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
              iconSize: [25, 41],
              iconAnchor: [12, 41],
              popupAnchor: [1, -34],
              shadowSize: [41, 41]
            })
          }).addTo(map).bindPopup(`<b>🚩 Start: ${typeof start === 'string' ? start : start.name}</b>`);
          markers.push(startMarker);
          window.currentMarkers.push(startMarker);

          // End marker (red pin)
          const endMarker = L.marker([validRoute[validRoute.length - 1].lat, validRoute[validRoute.length - 1].lng], {
            icon: L.icon({
              iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-red.png',
              shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
              iconSize: [25, 41],
              iconAnchor: [12, 41],
              popupAnchor: [1, -34],
              shadowSize: [41, 41]
            })
          }).addTo(map).bindPopup(`<b>📍 Destination: ${typeof end === 'string' ? end : end.name}</b>`);
          markers.push(endMarker);
          window.currentMarkers.push(endMarker);
        }

        // --- Use renderInstructions for instruction panel ---
        if (data.instructions && data.instructions.length > 0) {
          const enriched = data.instructions.map(instr => {
            const match = instr.match(/(go|head)\s+(\w+)/i);
            return {
              instruction: instr,
              direction: match ? match[2] : 'forward',
              distance: instr.match(/(\d+)\s?m/i)?.[1] || ''
            };
          });
          renderInstructions(enriched);
        } else {
          renderInstructions([]);
        }
      } else if (data.places && data.places.length >= 2) {
        // Fallback: show only start marker and dashed gray line between start and end (plain marker)
        const start = data.places[0];
        const end = data.places[data.places.length - 1];
        // Try to get coordinates from validRoute if available, otherwise fallback to Delhi
        const startCoord = validRoute[0] || { lat: 28.6139, lng: 77.2090 };
        const endCoord = validRoute[1] || { lat: 28.6139, lng: 77.2190 };

        // Start marker (green pin)
        const startMarker = L.marker([startCoord.lat, startCoord.lng], {
          icon: L.icon({
            iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-green.png',
            shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
            iconSize: [25, 41],
            iconAnchor: [12, 41],
            popupAnchor: [1, -34],
            shadowSize: [41, 41]
          })
        }).addTo(map).bindPopup(`<b>🚩 Start: ${typeof start === 'string' ? start : start.name}</b>`);
        markers.push(startMarker);
        window.currentMarkers.push(startMarker);

        // End marker (red pin)
        const endMarker = L.marker([endCoord.lat, endCoord.lng], {
          icon: L.icon({
            iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-red.png',
            shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
            iconSize: [25, 41],
            iconAnchor: [12, 41],
            popupAnchor: [1, -34],
            shadowSize: [41, 41]
          })
        }).addTo(map).bindPopup(`<b>📍 Destination: ${typeof end === 'string' ? end : end.name}</b>`);
        markers.push(endMarker);
        window.currentMarkers.push(endMarker);

        const fallbackLine = L.polyline([[startCoord.lat, startCoord.lng], [endCoord.lat, endCoord.lng]], {
          color: 'gray',
          dashArray: '5, 5'
        }).addTo(map);
        map.fitBounds(fallbackLine.getBounds().pad(0.1));

        // --- Use renderInstructions for instruction panel ---
        if (data.instructions && data.instructions.length > 0) {
          const enriched = data.instructions.map(instr => {
            const match = instr.match(/(go|head)\s+(\w+)/i);
            return {
              instruction: instr,
              direction: match ? match[2] : 'forward',
              distance: instr.match(/(\d+)\s?m/i)?.[1] || ''
            };
          });
          renderInstructions(enriched);
        } else {
          renderInstructions([]);
        }
      } else if (data.places && data.places.length === 1) {
        // Only one place, show a single marker at Delhi center
        const fallbackLatLng = L.latLng(28.6139, 77.2090); // Delhi center
        const marker = L.marker(fallbackLatLng).addTo(map).bindPopup(`<b>${data.places[0]}</b>`);
        markers.push(marker);
        window.currentMarkers.push(marker);
        map.setView(fallbackLatLng, 13);

        // --- Use renderInstructions for instruction panel ---
        if (data.instructions && data.instructions.length > 0) {
          const enriched = data.instructions.map(instr => {
            const match = instr.match(/(go|head)\s+(\w+)/i);
            return {
              instruction: instr,
              direction: match ? match[2] : 'forward',
              distance: instr.match(/(\d+)\s?m/i)?.[1] || ''
            };
          });
          renderInstructions(enriched);
        } else {
          renderInstructions([]);
        }
      }

      console.log("📍 Waypoints being passed to router:", JSON.stringify(validRoute, null, 2));
      // Show route on map
      routingControl = L.Routing.control({
        waypoints: (validRoute.length > data.places.length)
          ? validRoute.map(coord => L.latLng(coord.lat, coord.lng))
          : (data.places || []).map(() => map.getCenter()),
        router: L.Routing.osrmv1({ serviceUrl: 'https://router.project-osrm.org/route/v1' }),
        routeWhileDragging: false,
        lineOptions: { styles: [{ color: '#0074D9', weight: 5 }] },
        createMarker: () => null,    // 🚫 disable default markers
        show: false
      }).addTo(map);

      // Show food suggestions
      const list = document.getElementById('food-list');
      list.innerHTML = Array.isArray(data.food_suggestions)
        ? data.food_suggestions.map(f => `<li>${f}</li>`).join('')
        : '<li>No food suggestions available.</li>';

      const aiItinerarySection = document.getElementById('ai-itinerary-section');
      const aiItineraryCards = document.getElementById('ai-itinerary-cards');

      if (aiItinerarySection && aiItineraryCards) {
        if (data.itinerary && data.itinerary.length > 0) {
          let itineraryHTML = '';
          data.itinerary.forEach((dayObj, index) => {
            itineraryHTML += `
              <div class="itinerary-card">
                <div class="itinerary-day">${dayObj.day || `Day ${index + 1}`}</div>
                <div class="itinerary-activities">
                  ${Array.isArray(dayObj.activities) ? dayObj.activities.map(activity => `<div class="itinerary-activity">${activity}</div>`).join('') : ''}
                </div>
              </div>
            `;
          });
          aiItineraryCards.innerHTML = itineraryHTML;
          aiItinerarySection.style.display = 'block';
        } else {
          aiItineraryCards.innerHTML = '<li>No AI itinerary available.</li>';
          aiItinerarySection.style.display = 'block';
        }
      } else {
        console.warn('AI itinerary section or list missing from DOM.');
      }

      // Final formatted dump for debugging
      console.log("🧪 Final data object for debugging:", JSON.stringify(data, null, 2));
      console.log("✅ Finished processing AI route, map should be updated.");
      hideLoader();
    } catch (frontendErr) {
      console.error("💥 Frontend processing error after AI response:", frontendErr);
      alert("Frontend error after AI response: " + (frontendErr.message || frontendErr));
      hideLoader();
      return;
    }
  } catch (err) {
    console.error("AI route fetch failed:", err);
    alert("AI route error: " + (err.message || "Unknown error"));
    hideLoader();
  }
}
// Tab switching logic for the sidebar
function showTab(tab, event = null) {
  document.querySelectorAll('.tab-panel').forEach(panel => panel.style.display = 'none');
  document.querySelectorAll('.tab-button').forEach(btn => btn.classList.remove('active'));
  document.getElementById(`tab-${tab}`).style.display = 'block';
  if (event) event.target.classList.add('active');
}

function showLoader() {
  document.getElementById('loading-overlay').style.display = 'flex';
}

function hideLoader() {
  document.getElementById('loading-overlay').style.display = 'none';
}

async function fetchItinerary(places) {
  showLoader();
  try {
    const res = await fetch('/api/ai-itinerary', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ places })
    });

    const data = await res.json();
    if (data.status === 'success') {
      const itinerarySection = document.getElementById('itinerary-section');
      const itineraryList = document.getElementById('itinerary-list');

      // ---- Pin locations on the map ----
      if (window.itineraryMarkers) {
        window.itineraryMarkers.forEach(m => map.removeLayer(m));
      }
      window.itineraryMarkers = [];
      let allLocations = [];
      if (Array.isArray(data.itinerary)) {
        data.itinerary.forEach(day => {
          if (Array.isArray(day.locations)) {
            allLocations = allLocations.concat(day.locations);
          }
        });
      }
      if (allLocations.length === 0 && Array.isArray(data.itinerary)) {
        data.itinerary.forEach(day => {
          if (Array.isArray(day.activities)) {
            allLocations = allLocations.concat(day.activities.map(a => ({ name: a })));
          }
        });
      }
      for (const loc of allLocations) {
        let lat = loc.lat, lng = loc.lng;
        if (typeof lat !== 'number' || typeof lng !== 'number') {
          let key = (loc.name || '').toLowerCase().replace(/\s|_/g, '');
          if (placeToCoords[key]) {
            [lat, lng] = placeToCoords[key];
          } else {
            continue;
          }
        }
        // Check for duplicate markers by lat/lng
        const latLngKey = `${lat.toFixed(6)},${lng.toFixed(6)}`;
        if (window.itineraryMarkers.some(m => {
          const pos = m.getLatLng();
          return `${pos.lat.toFixed(6)},${pos.lng.toFixed(6)}` === latLngKey;
        })) {
          continue; // Skip adding this marker if already present
        }
        let icon = L.icon({
          iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-violet.png',
          iconSize: [25, 41],
          iconAnchor: [12, 41]
        });
        if (loc.category && categoryIcons[loc.category]) icon = categoryIcons[loc.category];
        const name = loc.name || 'Place';
        const photo = loc.photo || 'https://placehold.co/200x120?text=Photo';
        const time = loc.time || loc.visit_time || '10:00 AM - 5:00 PM';
        const price = (loc.ticket_price !== undefined) ? loc.ticket_price : '₹200';
        const desc = loc.description || 'A wonderful place to visit.';
        const popupContent = `
          <div style="font-weight:bold;font-size:1.1em;margin-bottom:4px;">${name}</div>
          <img src="${photo}" alt="photo" style="width:200px;height:120px;object-fit:cover;border-radius:4px;margin-bottom:4px;">
          <div><b>Timings:</b> ${time}</div>
          <div><b>Ticket Price:</b> ${price}</div>
          <div style="margin-top:4px;">${desc}</div>
        `;
        const marker = L.marker([lat, lng], { icon }).addTo(map).bindPopup(popupContent);
        window.itineraryMarkers.push(marker);
      }
      if (window.itineraryMarkers.length > 0) {
        const group = new L.featureGroup(window.itineraryMarkers);
        map.fitBounds(group.getBounds().pad(0.18));
      }

      // ---- Collapsible itinerary ----
      if (itinerarySection && itineraryList) {
        if (Array.isArray(data.itinerary) && data.itinerary.length > 0) {
          let itineraryHTML = '';
          data.itinerary.forEach((day, dayIdx) => {
            const dayLabel = day.day || `Day ${dayIdx + 1}`;
            itineraryHTML += `
                <div class="itinerary-collapsible-day" style="margin-bottom:8px;">
                    <button class="itinerary-day-toggle" style="font-weight:bold;width:100%;text-align:left;padding:8px;border:none;background:#eee;cursor:pointer;border-radius:4px;">${dayLabel}</button>
                    <div class="itinerary-day-details" style="display:none;padding-left:12px;">
                        ${Array.isArray(day.locations)
                ? day.locations.map((loc, locIdx) => `
                        <div class="itinerary-collapsible-location" style="margin:6px 0;">
                            <button class="itinerary-location-toggle" style="font-size:1em;width:100%;text-align:left;padding:6px;border:none;background:#f9f9f9;cursor:pointer;border-radius:4px;">
                                ${loc.name || `Place ${locIdx + 1}`}
                            </button>
                            <div class="itinerary-location-details" style="display:none;padding-left:10px;">
                                <div style="margin:4px 0;"><b>Description:</b> ${loc.description || 'A wonderful place to visit.'}</div>
                                <img src="${loc.photo || 'https://placehold.co/200x120?text=Photo'}" alt="photo" style="width:180px;height:100px;object-fit:cover;border-radius:4px;margin-bottom:4px;">
                                <div><b>Timings:</b> ${loc.time || loc.visit_time || '10:00 AM - 5:00 PM'}</div>
                                <div><b>Ticket Price:</b> ${loc.ticket_price !== undefined ? loc.ticket_price : '₹200'}</div>
                            </div>
                        </div>
                    `).join('')
                : (Array.isArray(day.activities)
                  ? day.activities.map((a, idx) => `<div style="margin:4px 0;">${a}</div>`).join('')
                  : '')
              }
                    </div>
                </div>
            `;
          });
          itineraryList.innerHTML = itineraryHTML;
          itinerarySection.style.display = 'block';
          setTimeout(() => {
            itineraryList.querySelectorAll('.itinerary-day-toggle').forEach(btn => {
              btn.addEventListener('click', function () {
                const details = this.parentElement.querySelector('.itinerary-day-details');
                if (details) {
                  details.style.display = (details.style.display === 'none' ? 'block' : 'none');
                }
              });
            });
            itineraryList.querySelectorAll('.itinerary-location-toggle').forEach(btn => {
              btn.addEventListener('click', function (e) {
                e.stopPropagation();
                const details = this.parentElement.querySelector('.itinerary-location-details');
                if (details) {
                  details.style.display = (details.style.display === 'none' ? 'block' : 'none');
                }
              });
            });
          }, 0);
        } else {
          itineraryList.innerHTML = '<li>No itinerary available.</li>';
          itinerarySection.style.display = 'block';
        }
      }
    } else {
      alert("Failed to generate itinerary.");
    }
  } catch (error) {
    console.error('Itinerary fetch failed:', error);
    alert("Error generating itinerary.");
  }
  hideLoader();
}
// ---- End of itinerary/map/collapsible enhancements ----

function applyTheme(isDark) {
  const html = document.documentElement;
  const body = document.body;
  const themeButton = document.getElementById('theme-toggle');

  html.classList.toggle('dark', isDark);
  body.classList.toggle('dark-theme', isDark);

  localStorage.setItem('theme', isDark ? 'dark' : 'light');

  if (themeButton) {
    themeButton.innerText = isDark ? "Light Mode" : "Dark Mode";
    themeButton.classList.toggle('dark-mode-button', isDark);
    themeButton.classList.toggle('light-mode-button', !isDark);
  }
}

function toggleTheme() {
  document.documentElement.classList.toggle('dark');
  localStorage.setItem('theme', document.documentElement.classList.contains('dark') ? 'dark' : 'light');
  const themeBtn = document.getElementById('theme-toggle');
  if (document.documentElement.classList.contains('dark')) {
    themeBtn.textContent = '🌞 Light Mode';
  } else {
    themeBtn.textContent = '🌙 Dark Mode';
  }
}

window.onload = () => {
  const savedTheme = localStorage.getItem('theme');
  if (savedTheme === 'dark') {
    document.documentElement.classList.add('dark');
    document.getElementById('theme-toggle').textContent = '🌞 Light Mode';
  } else {
    document.documentElement.classList.remove('dark');
    document.getElementById('theme-toggle').textContent = '🌙 Dark Mode';
  }
};

// Helper to ensure the directions panel exists and is styled
function ensureDirectionsPanel() {
  let panel = document.getElementById('directions-panel');
  if (!panel) {
    panel = document.createElement('div');
    panel.id = 'directions-panel';
    panel.style.position = 'absolute';
    panel.style.top = '80px';
    panel.style.right = '10px';
    panel.style.width = '300px';
    panel.style.maxHeight = '400px';
    panel.style.overflowY = 'auto';
    panel.style.background = 'white';
    panel.style.border = '1px solid #ccc';
    panel.style.padding = '10px';
    panel.style.zIndex = 1000;
    // Dark mode styling
    const isDark = document.documentElement.classList.contains('dark');
    panel.style.background = isDark ? '#1e1e1e' : 'white';
    panel.style.color = isDark ? '#f0f0f0' : 'black';
    panel.style.boxShadow = isDark ? '0 2px 8px rgba(0,0,0,0.8)' : '0 2px 8px rgba(0,0,0,0.2)';
    panel.style.border = isDark ? '1px solid #444' : '1px solid #ccc';
    // Add a header, toggle button, and collapsible content container
    panel.innerHTML = `
      <div style="display:flex;justify-content:space-between;align-items:center;">
        <h2 style="margin:0;flex:1;">🧭 Directions</h2>
        <button id="directions-toggle" style="margin-left:8px;">Hide</button>
      </div>
      <div id="directions-content">
        <div id="directions-list"></div>
      </div>
    `;
    document.body.appendChild(panel);
    const toggleBtn = panel.querySelector('#directions-toggle');
    const contentDiv = panel.querySelector('#directions-content');
    // Button style for theme
    if (toggleBtn) {
      toggleBtn.style.background = isDark ? '#333' : '#f9f9f9';
      toggleBtn.style.color = isDark ? '#f0f0f0' : '#000';
      toggleBtn.style.border = isDark ? '1px solid #555' : '1px solid #ccc';
    }
    toggleBtn.addEventListener('click', () => {
      if (contentDiv.style.display === 'none') {
        contentDiv.style.display = 'block';
        toggleBtn.textContent = 'Hide';
      } else {
        contentDiv.style.display = 'none';
        toggleBtn.textContent = 'Show';
      }
    });
  } else {
    // Update dark mode styling if panel already exists
    const isDark = document.documentElement.classList.contains('dark');
    panel.style.background = isDark ? '#1e1e1e' : 'white';
    panel.style.color = isDark ? '#f0f0f0' : 'black';
    panel.style.boxShadow = isDark ? '0 2px 8px rgba(0,0,0,0.8)' : '0 2px 8px rgba(0,0,0,0.2)';
    panel.style.border = isDark ? '1px solid #444' : '1px solid #ccc';
    const toggleBtn = panel.querySelector('#directions-toggle');
    if (toggleBtn) {
      toggleBtn.style.background = isDark ? '#333' : '#f9f9f9';
      toggleBtn.style.color = isDark ? '#f0f0f0' : '#000';
      toggleBtn.style.border = isDark ? '1px solid #555' : '1px solid #ccc';
    }
  }
  return panel;
}

// Renders a directions panel with steps and distances
function renderInstructions(instructions) {
  const container = ensureDirectionsPanel();
  // Only clear the directions-list, not the whole container
  const list = container.querySelector('#directions-list');
  list.innerHTML = '';
  const seen = new Set();
  instructions.forEach((step) => {
    let cleanInstr = step.instruction.replace(/\s+/g, ' ').replace(/\([^)]*\)/g, '').trim();
    if (!cleanInstr || seen.has(cleanInstr)) return;
    seen.add(cleanInstr);
    const p = document.createElement('p');
    p.textContent = `${cleanInstr}${step.distance ? ` (${step.distance} m)` : ''}`;
    list.appendChild(p);
  });
  if (list.children.length === 0) {
    const p = document.createElement('p');
    p.textContent = 'No clear directions available.';
    list.appendChild(p);
  }
  // Ensure the panel is visible and styled accordingly
  container.style.display = 'block';
  container.classList.add('instructions-visible');
  // 🚫 Hide default Leaflet routing container to avoid messy text
  const leafletContainers = document.querySelectorAll('.leaflet-routing-container, .leaflet-routing-error');
  leafletContainers.forEach(el => {
    el.style.display = 'none';
  });
}

function getDirectionIcon(direction) {
  switch (direction.toLowerCase()) {
    case 'left': return '⬅️';
    case 'right': return '➡️';
    case 'straight': return '⬆️';
    case 'back': return '⬇️';
    case 'northeast': return '↗️';
    case 'northwest': return '↖️';
    case 'southeast': return '↘️';
    case 'southwest': return '↙️';
    default: return '➡️';
  }
}

// UX Enhancement: Disable submit button if input is empty
document.addEventListener('DOMContentLoaded', () => {
  const promptInput = document.getElementById('ai-prompt-input');
  const submitBtn = document.getElementById('submit-button');
  if (promptInput && submitBtn) {
    const toggleButtonState = () => {
      submitBtn.disabled = promptInput.value.trim() === '';
    };
    promptInput.addEventListener('input', toggleButtonState);
    toggleButtonState(); // Initial check
  }
});

// Ensure the directions panel is visible on page load and update styling for theme changes
document.addEventListener('DOMContentLoaded', () => {
  const panel = document.getElementById('directions-panel');
  if (panel) {
    panel.style.display = 'block';
  }
  // Listen for theme toggle to update panel styling
  const themeBtn = document.getElementById('theme-toggle');
  if (themeBtn) {
    themeBtn.addEventListener('click', () => {
      const panel = document.getElementById('directions-panel');
      if (panel) {
        const isDark = document.documentElement.classList.contains('dark');
        panel.style.background = isDark ? '#1e1e1e' : 'white';
        panel.style.color = isDark ? '#f0f0f0' : 'black';
        panel.style.boxShadow = isDark ? '0 2px 8px rgba(0,0,0,0.8)' : '0 2px 8px rgba(0,0,0,0.2)';
        panel.style.border = isDark ? '1px solid #444' : '1px solid #ccc';
        const toggleBtn = panel.querySelector('#directions-toggle');
        if (toggleBtn) {
          toggleBtn.style.background = isDark ? '#333' : '#f9f9f9';
          toggleBtn.style.color = isDark ? '#f0f0f0' : '#000';
          toggleBtn.style.border = isDark ? '1px solid #555' : '1px solid #ccc';
        }
      }
    });
  }
});