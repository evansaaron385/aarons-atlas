const DEFAULT_CENTER = [21.4389, -158.0001];

const map = L.map("map").setView(DEFAULT_CENTER, 10);

L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 19,
  attribution: "&copy; OpenStreetMap contributors"
}).addTo(map);

const cameraIcon = L.divIcon({
  html: "📷",
  className: "camera-marker",
  iconSize: [32, 32],
  iconAnchor: [16, 16],
  popupAnchor: [0, -12]
});

let allPhotos = [];
let markers = [];

fetch("data/photos.json")
  .then(response => {
    if (!response.ok) {
      throw new Error(`Photo data failed to load (${response.status})`);
    }
    return response.json();
  })
  .then(photos => {
    allPhotos = photos;
    buildCategoryFilters(photos);
    showPhotos("All");
  })
  .catch(error => {
    console.error(error);
    document.getElementById("photo-count").textContent =
      "Photos could not be loaded. Run the site through a local web server.";
  });

function showPhotos(category) {
  markers.forEach(marker => map.removeLayer(marker));
  markers = [];

  const selectedPhotos = category === "All"
    ? allPhotos
    : allPhotos.filter(photo => photo.category === category);

  const filteredPhotos = selectedPhotos.filter(photo =>
    Number.isFinite(photo.lat) && Number.isFinite(photo.lng)
  );
  const awaitingLocation = selectedPhotos.length - filteredPhotos.length;

  document.getElementById("photo-count").textContent =
    `Showing ${filteredPhotos.length} mapped photo${filteredPhotos.length === 1 ? "" : "s"}` +
    (awaitingLocation ? ` • ${awaitingLocation} need${awaitingLocation === 1 ? "s" : ""} location` : "");

  filteredPhotos.forEach(photo => {
    const popupContent = `
      <div class="popup-card">
        <img class="popup-photo" src="${photo.image}" alt="${photo.title}" />
        <h3>${photo.title}</h3>
        <p><strong>📍</strong> ${photo.location}</p>
        <p>${photo.caption}</p>
        <span class="category-tag">${photo.category}</span>
      </div>
    `;

    const marker = L.marker([photo.lat, photo.lng], { icon: cameraIcon })
      .addTo(map)
      .bindPopup(popupContent);

    marker.on("click", () => openPhotoPanel(photo));
    markers.push(marker);
  });

  if (markers.length === 1) {
    map.setView(markers[0].getLatLng(), 12);
  } else if (markers.length > 1) {
    map.fitBounds(L.featureGroup(markers).getBounds(), { padding: [40, 40] });
  }
}

function buildCategoryFilters(photos) {
  const filters = document.querySelector(".filters");
  const categories = [...new Set(photos.map(photo => photo.category))].sort();

  categories.forEach(category => {
    const button = document.createElement("button");
    button.dataset.category = category;
    button.textContent = category;
    filters.appendChild(button);
  });

  bindFilterButtons();
}

function bindFilterButtons() {
  document.querySelectorAll(".filters button").forEach(button => {
    button.addEventListener("click", () => {
      document.querySelectorAll(".filters button").forEach(item => {
        item.classList.remove("active");
      });

      button.classList.add("active");
      showPhotos(button.dataset.category);
    });
  });
}

document.querySelector('.filters button[data-category="All"]').classList.add("active");

function openPhotoPanel(photo) {
  document.getElementById("photo-panel").classList.remove("hidden");
  document.getElementById("panel-image").src = photo.image;
  document.getElementById("panel-image").alt = photo.title;
  document.getElementById("panel-title").textContent = photo.title;
  document.getElementById("panel-location").textContent = `📍 ${photo.location}`;
  document.getElementById("panel-date").textContent = `📅 ${photo.date || "Date Unknown"}`;
  document.getElementById("panel-caption").textContent = photo.caption;
  document.getElementById("panel-category").textContent = photo.category;
  document.getElementById("camera-info").innerHTML = `
    <p><strong>Camera:</strong> ${photo.camera || "Unknown"}</p>
    <p><strong>Lens:</strong> ${photo.lens || "Unknown"}</p>
  `;
}

document.getElementById("close-panel").addEventListener("click", () => {
  document.getElementById("photo-panel").classList.add("hidden");
});

document.getElementById("enter-atlas").addEventListener("click", () => {
  document.getElementById("landing-page").classList.add("hidden");
  setTimeout(() => map.invalidateSize(), 350);
});
