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
  loadMockItinerary();
});

// Allow user to select hotel location by clicking on the map
function enableHotelSelection() {
  alert("Click on the map to set your hotel location.");
  map.once('click', function (e) {
    const { lat, lng } = e.latlng;
    if (window.hotelMarker) {
      map.removeLayer(window.hotelMarker);
    }
    window.hotelMarker = L.marker([lat, lng], {
      icon: L.icon({
        iconUrl: 'https://cdn-icons-png.flaticon.com/512/684/684908.png',
        iconSize: [30, 30],
        iconAnchor: [15, 30]
      })
    }).addTo(map).bindPopup("🏨 Hotel Location").openPopup();
    window.hotelLocation = { lat, lng };
    map.setView([lat, lng], 14);
    alert("Hotel location set!");
  });
}

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

    // always render itinerary UI if present
    if (typeof renderAIItinerarySection === 'function') {
      renderAIItinerarySection(data.itinerary || data.days || []);
    }

    // Normalize any route formats to array of {lat, lng}
    let normalized = [];
    if (Array.isArray(data.route) && data.route.length > 0) {
      // route may be [[lat,lng], [lat,lng]] or [{lat:..,lng:..}] or [{latitude:..,longitude:..}]
      for (const r of data.route) {
        if (Array.isArray(r) && r.length >= 2 && typeof r[0] === 'number') {
          normalized.push({ lat: r[0], lng: r[1] });
        } else if (r && typeof r.lat === 'number' && typeof r.lng === 'number') {
          normalized.push({ lat: r.lat, lng: r.lng });
        } else if (r && typeof r.latitude === 'number' && typeof r.longitude === 'number') {
          normalized.push({ lat: r.latitude, lng: r.longitude });
        }
      }
    }

    // if no route in data.route, try to extract from data.days or data.itinerary
    if (normalized.length < 2) {
      if (Array.isArray(data.days)) {
        data.days.forEach(day => {
          if (Array.isArray(day.route)) {
            day.route.forEach(p => {
              if (Array.isArray(p) && p.length >= 2 && typeof p[0] === 'number') normalized.push({ lat: p[0], lng: p[1] });
              else if (p && typeof p.lat === 'number' && typeof p.lng === 'number') normalized.push({ lat: p.lat, lng: p.lng });
            });
          }
        });
      }

      if (Array.isArray(data.itinerary)) {
        data.itinerary.forEach(day => {
          const acts = Array.isArray(day.activities) ? day.activities : (Array.isArray(day.locations) ? day.locations : []);
          acts.forEach(act => {
            if (act && typeof act.lat === 'number' && typeof act.lng === 'number') normalized.push({ lat: act.lat, lng: act.lng });
          });
        });
      }
    }

    // Last-resort: fuzzy match place names to known placeToCoords
    if (normalized.length < 2 && Array.isArray(data.places)) {
      for (const p of data.places) {
        if (typeof p === 'string') {
          const key = p.toLowerCase().replace(/[^a-z]/g, '');
          for (const k in placeToCoords) {
            if (key.includes(k)) {
              normalized.push({ lat: placeToCoords[k][0], lng: placeToCoords[k][1] });
              break;
            }
          }
        } else if (p && typeof p.name === 'string') {
          const key = p.name.toLowerCase().replace(/[^a-z]/g, '');
          for (const k in placeToCoords) {
            if (key.includes(k)) {
              normalized.push({ lat: placeToCoords[k][0], lng: placeToCoords[k][1] });
              break;
            }
          }
        }
      }
    }

    // Deduplicate coordinates (by lat/lng rounded)
    const seen = new Set();
    const validRoute = [];
    normalized.forEach(c => {
      if (!c || typeof c.lat !== 'number' || typeof c.lng !== 'number') return;
      const key = `${c.lat.toFixed(6)},${c.lng.toFixed(6)}`;
      if (!seen.has(key)) {
        seen.add(key);
        validRoute.push(c);
      }
    });

    console.log('✅ Normalized validRoute:', validRoute);

    // If still not enough points, notify and render whatever markers we have
    if (validRoute.length < 2) {
      console.warn('🚫 Not enough points for routing. Showing markers only.');
      clearAllMarkers();
      // show markers for known places if available
      if (Array.isArray(data.places) && data.places.length > 0) {
        data.places.forEach((p, idx) => {
          let latlng = null;
          if (Array.isArray(p) && p.length >= 2 && typeof p[0] === 'number') latlng = { lat: p[0], lng: p[1] };
          else if (p && typeof p.lat === 'number' && typeof p.lng === 'number') latlng = { lat: p.lat, lng: p.lng };
          else if (typeof p === 'string') {
            const key = p.toLowerCase().replace(/[^a-z]/g, '');
            if (placeToCoords[key]) latlng = { lat: placeToCoords[key][0], lng: placeToCoords[key][1] };
          }
          if (latlng) {
            const m = L.marker([latlng.lat, latlng.lng]).addTo(map).bindPopup(`<b>${typeof p === 'string' ? p : (p.name || 'Place')}</b>`);
            markers.push(m);
            window.currentMarkers.push(m);
          }
        });
        if (window.currentMarkers.length > 0) {
          const group = new L.featureGroup(window.currentMarkers);
          map.fitBounds(group.getBounds().pad(0.15));
        }
      }
      hideLoader();
      return;
    }

    // Clear any previous drawn route layers and markers
    if (window.routeLayer) { map.removeLayer(window.routeLayer); window.routeLayer = null; }
    if (routingControl) { map.removeControl(routingControl); routingControl = null; }
    clearAllMarkers();

    // Draw and focus on route
    if (validRoute.length >= 2) {
      const routeLatLngs = validRoute.map(c => [c.lat, c.lng]);

      if (window.routeLayer) map.removeLayer(window.routeLayer);
      window.routeLayer = L.polyline(routeLatLngs, { color: '#0074D9', weight: 5, opacity: 0.9 }).addTo(map);

      map.fitBounds(window.routeLayer.getBounds().pad(0.15));

      if (routingControl) map.removeControl(routingControl);
      routingControl = L.Routing.control({
        waypoints: validRoute.map(c => L.latLng(c.lat, c.lng)),
        router: L.Routing.osrmv1({ serviceUrl: 'https://router.project-osrm.org/route/v1' }),
        routeWhileDragging: false,
        show: false,
        createMarker: () => null,
        lineOptions: { styles: [{ color: '#0074D9', weight: 4 }] }
      }).addTo(map);
    }
    // add start/end markers
    const start = validRoute[0];
    const end = validRoute[validRoute.length - 1];
    const startMarker = L.marker([start.lat, start.lng], { icon: categoryIcons.culture }).addTo(map).bindPopup('<b>Start</b>').openPopup();
    const endMarker = L.marker([end.lat, end.lng], { icon: categoryIcons.food }).addTo(map).bindPopup('<b>End</b>');
    markers.push(startMarker, endMarker); window.currentMarkers.push(startMarker, endMarker);

    // Fit map to route
    map.fitBounds(window.routeLayer.getBounds().pad(0.12));

    // Also create a routingControl for turn-by-turn if desired (OSRM) — use the validRoute points as waypoints
    try {
      routingControl = L.Routing.control({
        waypoints: validRoute.map(c => L.latLng(c.lat, c.lng)),
        router: L.Routing.osrmv1({ serviceUrl: 'https://router.project-osrm.org/route/v1' }),
        routeWhileDragging: false,
        show: false,
        createMarker: () => null,
        lineOptions: { styles: [{ color: '#0074D9', weight: 4 }] }
      }).addTo(map);

      // If routing gives routes, hide default leaflet routing UI and show our instructions panel
      routingControl.on('routesfound', function (e) {
        const routes = e.routes || [];
        if (routes.length > 0) {
          const summary = routes[0].summary || {};
          console.log('Routing summary:', summary);
        }
      });
    } catch (err) {
      console.warn('Routing control failed, but polyline is drawn:', err);
    }

    // Render instructions panel if AI provided 'instructions'
    if (Array.isArray(data.instructions) && data.instructions.length > 0) {
      const enriched = data.instructions.map(instr => ({ instruction: instr, distance: instr.match(/(\d+\.?\d*)\s?m/i)?.[1] || '' }));
      renderInstructions(enriched);
    }

    // populate food suggestions
    const list = document.getElementById('food-list');
    list.innerHTML = Array.isArray(data.food) ? data.food.map(f => `<li>${f}</li>`).join('') : '<li>No food suggestions available.</li>';

    // ---- Enhanced AI Itinerary Rendering ----
    // const aiItinerarySection = document.getElementById('ai-itinerary-section');
    // const aiItineraryCards = document.getElementById('ai-itinerary-cards');
    // if (aiItinerarySection && aiItineraryCards && Array.isArray(data.itinerary)) {
    //   aiItineraryCards.innerHTML = '';
    //   if (window.aiItineraryMarkers) {
    //     window.aiItineraryMarkers.forEach(m => map.removeLayer(m));
    //   }
    //   window.aiItineraryMarkers = [];

    //   data.itinerary.forEach((day, dayIdx) => {
    //     const dayLabel = day.day || `Day ${dayIdx + 1}`;
    //     const dayDiv = document.createElement('div');
    //     dayDiv.classList.add('itinerary-collapsible-day');
    //     dayDiv.innerHTML = `
    //       <button class="itinerary-day-toggle" style="font-weight:bold;width:100%;text-align:left;padding:8px;border:none;background:#eee;cursor:pointer;border-radius:4px;">${dayLabel}</button>
    //       <div class="itinerary-day-details" style="display:none;padding-left:12px;"></div>
    //     `;
    //     const detailsDiv = dayDiv.querySelector('.itinerary-day-details');

    //     const places = Array.isArray(day.locations) ? day.locations : (Array.isArray(day.activities) ? day.activities : []);
    //     places.forEach((loc, locIdx) => {
    //       const name = loc.name || loc.place || `Place ${locIdx + 1}`;
    //       const lat = loc.lat, lng = loc.lng;
    //       const photo = loc.photo || 'https://placehold.co/200x120?text=Photo';
    //       const desc = loc.description || loc.details || 'A great place to visit.';
    //       const food = loc.food || loc.famous_food || '';
    //       const time = loc.time || loc.visit_time || '10:00 AM - 5:00 PM';
    //       const price = (loc.ticket_price !== undefined) ? loc.ticket_price : '₹200';

    //       if (typeof lat === 'number' && typeof lng === 'number') {
    //         const icon = categoryIcons[loc.category] || L.icon({
    //           iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-violet.png',
    //           iconSize: [25, 41],
    //           iconAnchor: [12, 41]
    //         });
    //         const popupHTML = `
    //           <div style="font-weight:bold;font-size:1.1em;margin-bottom:4px;">${name}</div>
    //           <img src="${photo}" style="width:200px;height:120px;object-fit:cover;border-radius:4px;margin-bottom:4px;">
    //           <div><b>Description:</b> ${desc}</div>
    //           ${food ? `<div><b>Famous Food:</b> ${food}</div>` : ''}
    //           <div><b>Timings:</b> ${time}</div>
    //           <div><b>Ticket Price:</b> ${price}</div>
    //         `;
    //         const marker = L.marker([lat, lng], { icon }).addTo(map).bindPopup(popupHTML);
    //         window.aiItineraryMarkers.push(marker);

    //         const locDiv = document.createElement('div');
    //         locDiv.classList.add('itinerary-collapsible-location');
    //         locDiv.innerHTML = `
    //           <button class="itinerary-location-toggle" style="font-size:1em;width:100%;text-align:left;padding:6px;border:none;background:#f9f9f9;cursor:pointer;border-radius:4px;">
    //             ${name}
    //           </button>
    //           <div class="itinerary-location-details" style="display:none;padding-left:10px;">
    //             <div style="margin:4px 0;"><b>Description:</b> ${desc}</div>
    //             ${food ? `<div><b>Famous Food:</b> ${food}</div>` : ''}
    //             <img src="${photo}" alt="photo" style="width:180px;height:100px;object-fit:cover;border-radius:4px;margin-bottom:4px;">
    //             <div><b>Timings:</b> ${time}</div>
    //             <div><b>Ticket Price:</b> ${price}</div>
    //           </div>
    //         `;
    //         detailsDiv.appendChild(locDiv);

    //         // Click to zoom to the marker and open popup
    //         locDiv.querySelector('.itinerary-location-toggle').addEventListener('click', (e) => {
    //           e.stopPropagation();
    //           const details = locDiv.querySelector('.itinerary-location-details');
    //           details.style.display = (details.style.display === 'none' ? 'block' : 'none');
    //           map.setView([lat, lng], 14);
    //           marker.openPopup();
    //         });
    //       }
    //     });

    //     // Add day toggle event immediately after appending
    //     const dayToggle = dayDiv.querySelector('.itinerary-day-toggle');
    //     dayToggle.addEventListener('click', () => {
    //       const details = dayDiv.querySelector('.itinerary-day-details');
    //       details.style.display = (details.style.display === 'none' ? 'block' : 'none');
    //     });

    //     // Append the whole day block
    //     aiItineraryCards.appendChild(dayDiv);
    //   });

    //   // Ensure collapsible toggles work after DOM is added
    //   setTimeout(() => {
    //     document.querySelectorAll('.itinerary-day-toggle').forEach(btn => {
    //       btn.addEventListener('click', () => {
    //         const details = btn.parentElement.querySelector('.itinerary-day-details');
    //         if (details) {
    //           details.style.display = details.style.display === 'none' ? 'block' : 'none';
    //         }
    //       });
    //     });

    //     document.querySelectorAll('.itinerary-location-toggle').forEach(btn => {
    //       btn.addEventListener('click', (e) => {
    //         e.stopPropagation();
    //         const details = btn.parentElement.querySelector('.itinerary-location-details');
    //         if (details) {
    //           details.style.display = details.style.display === 'none' ? 'block' : 'none';
    //         }
    //       });
    //     });
    //   }, 0);

    //   aiItinerarySection.style.display = 'block';

    //   if (window.aiItineraryMarkers.length > 0) {
    //     const group = new L.featureGroup(window.aiItineraryMarkers);
    //     map.fitBounds(group.getBounds().pad(0.15));
    //   }
    // }

    // ---- Simplified AI Itinerary Rendering (non-collapsible) ----
    const aiItinerarySection = document.getElementById('ai-itinerary-section');
    const aiItineraryCards = document.getElementById('ai-itinerary-cards');

    if (aiItinerarySection && aiItineraryCards && Array.isArray(data.itinerary)) {
      aiItineraryCards.innerHTML = '';

      if (window.aiItineraryMarkers) {
        window.aiItineraryMarkers.forEach(m => map.removeLayer(m));
      }
      window.aiItineraryMarkers = [];

      // Build compact markup using CSS classes (avoid inline styles that override your stylesheet)
      const markup = data.itinerary.map((day, dayIdx) => {
        const dayLabel = day.day || `Day ${dayIdx + 1}`;
        const places = Array.isArray(day.locations)
          ? day.locations
          : (Array.isArray(day.activities) ? day.activities : []);

        const placesHTML = places.map((loc, locIdx) => {
          const name = (loc && (loc.name || loc.place)) ? (loc.name || loc.place) : `Place ${locIdx + 1}`;
          const desc = loc && (loc.description || loc.details) ? (loc.description || loc.details) : '';
          const time = loc && (loc.time || loc.visit_time) ? (loc.time || loc.visit_time) : '';
          const photo = loc && loc.photo ? loc.photo : '';

          // add marker if coords present
          if (loc && typeof loc.lat === 'number' && typeof loc.lng === 'number') {
            const marker = L.marker([loc.lat, loc.lng]).addTo(map).bindPopup(`<b>${name}</b><br>${desc}`);
            window.aiItineraryMarkers.push(marker);
          }

          return `
            <div class="itinerary-item">
              ${photo ? `<img class="itinerary-photo" src="${photo}" alt="${name}">` : ''}
              <div class="itinerary-content">
                <div class="itinerary-place">${name}</div>
                ${time ? `<div class="itinerary-time">${time}</div>` : ''}
                ${desc ? `<div class="itinerary-notes">${desc}</div>` : ''}
              </div>
            </div>
          `;
        }).join('');

        return `
          <div class="itinerary-card">
            <div class="itinerary-day">${dayLabel}</div>
            <div class="itinerary-day-places">${placesHTML}</div>
          </div>
        `;
      }).join('');

      aiItineraryCards.innerHTML = markup;
      aiItinerarySection.style.display = 'block';

      if (window.aiItineraryMarkers.length > 0) {
        const group = new L.featureGroup(window.aiItineraryMarkers);
        map.fitBounds(group.getBounds().pad(0.15));
      }
    }


    hideLoader();
  } catch (err) {
    console.error('AI route fetch failed:', err);
    alert('AI route error: ' + (err.message || 'Unknown error'));
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

// ---- Enhanced renderItinerary Functionality ----
/**
 * Renders the itinerary with collapsible days, clickable places (zoom to marker), and food suggestions.
 * @param {Array} itinerary - Array of day objects with activities [{place, time, notes, ...}]
 * @param {Array} foodList - Array of food strings for suggestions (optional)
 */
function renderItinerary(itinerary, foodList = []) {
  const itineraryDiv = document.getElementById("itinerary");
  itineraryDiv.innerHTML = "";

  if (!itinerary || itinerary.length === 0) {
    itineraryDiv.innerHTML = "<p>No itinerary available.</p>";
    return;
  }

  const foodSamples = foodList.slice(0, 3); // Take top 3 food items for suggestions

  itinerary.forEach((day) => {
    const dayContainer = document.createElement("div");
    dayContainer.className = "day-container";

    const dayHeader = document.createElement("div");
    dayHeader.className = "day-header";
    dayHeader.textContent = day.day;

    const activitiesList = document.createElement("div");
    activitiesList.className = "activities-list";
    activitiesList.style.display = "none";

    dayHeader.addEventListener("click", () => {
      activitiesList.style.display =
        activitiesList.style.display === "none" ? "block" : "none";
    });

    day.activities.forEach((activity) => {
      const activityItem = document.createElement("div");
      activityItem.className = "activity-item";

      const title = document.createElement("h4");
      title.textContent = `${activity.place} (${activity.time})`;
      title.style.cursor = "pointer";

      // When user clicks on a place, zoom to its marker
      title.addEventListener("click", () => {
        const marker = markers.find(
          (m) => m.options.title === activity.place
        );
        if (marker) {
          map.setView(marker.getLatLng(), 14);
          marker.openPopup();
        }
      });

      const notes = document.createElement("p");
      notes.textContent = activity.notes;

      // Add "Famous food to try" suggestion
      const foodNote = document.createElement("p");
      if (foodSamples.length > 0) {
        const randomFood = foodSamples[Math.floor(Math.random() * foodSamples.length)];
        foodNote.innerHTML = `<strong>🍴 Try:</strong> ${randomFood}`;
      }

      activityItem.appendChild(title);
      activityItem.appendChild(notes);
      activityItem.appendChild(foodNote);
      activitiesList.appendChild(activityItem);
    });

    dayContainer.appendChild(dayHeader);
    dayContainer.appendChild(activitiesList);
    itineraryDiv.appendChild(dayContainer);
  });
}

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