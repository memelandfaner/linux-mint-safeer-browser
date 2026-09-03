// Safeer Browser - Linux Mint Edition Start Page Logic

let currentEngine = 'google';

const searchUrls = {
  google: 'https://www.google.com/search?q=',
  duckduckgo: 'https://duckduckgo.com/?q=',
  brave: 'https://search.brave.com/search?q=',
  youtube: 'https://www.youtube.com/results?search_query='
};

// 1. Live Clock & Date (Slovenian)
function updateClock() {
  const now = new Date();
  const hours = String(now.getHours()).padStart(2, '0');
  const minutes = String(now.getMinutes()).padStart(2, '0');
  
  const timeEl = document.getElementById('clockTime');
  if (timeEl) timeEl.textContent = `${hours}:${minutes}`;

  const days = ['Nedelja', 'Ponedeljek', 'Torek', 'Sreda', 'Četrtek', 'Petek', 'Sobota'];
  const months = ['Januar', 'Februar', 'Marec', 'April', 'Maj', 'Junij', 'Julij', 'Avgust', 'September', 'Oktober', 'November', 'December'];

  const dayName = days[now.getDay()];
  const day = now.getDate();
  const monthName = months[now.getMonth()];
  const year = now.getFullYear();

  const dateEl = document.getElementById('clockDate');
  if (dateEl) dateEl.textContent = `${dayName}, ${day}. ${monthName} ${year}`;
}

// 2. Search Handler
function setEngine(engine, btn) {
  currentEngine = engine;
  document.querySelectorAll('.engine-pills .pill').forEach(p => p.classList.remove('active'));
  if (btn) btn.classList.add('active');
  
  const input = document.getElementById('searchInput');
  if (input) input.focus();
}

function performSearch(event) {
  event.preventDefault();
  const input = document.getElementById('searchInput');
  const query = input.value.trim();
  if (!query) return false;

  let targetUrl = '';
  if (query.startsWith('http://') || query.startsWith('https://')) {
    targetUrl = query;
  } else if (query.includes('.') && !query.includes(' ')) {
    targetUrl = 'https://' + query;
  } else {
    targetUrl = searchUrls[currentEngine] + encodeURIComponent(query);
  }

  // Communicate with Safeer Python Host or navigate
  if (window.webkit && window.webkit.messageHandlers && window.webkit.messageHandlers.safeer) {
    window.webkit.messageHandlers.safeer.postMessage({ action: 'navigate', url: targetUrl });
  } else {
    window.location.href = targetUrl;
  }
  return false;
}

// 3. Portals Grid
const defaultPortals = [
  { title: "Xplore TV", url: "https://www.xploretv.si/livetv", mark: "X", bg: "linear-gradient(145deg, #7a1024, #e31837)" },
  { title: "24ur.com", url: "https://www.24ur.com", mark: "2", bg: "linear-gradient(145deg, #0a2040, #1256a8)" },
  { title: "RTV SLO", url: "https://www.rtvslo.si", mark: "R", bg: "linear-gradient(145deg, #04364a, #0284c7)" },
  { title: "Filmi", url: "https://hydrahd.ws/", mark: "F", bg: "linear-gradient(145deg, #062a38, #0277a3)" },
  { title: "YouTube", url: "https://www.youtube.com", mark: "Y", bg: "linear-gradient(145deg, #4a0b0b, #cc0000)" },
  { title: "ChatGPT", url: "https://chatgpt.com", mark: "AI", bg: "linear-gradient(145deg, #063c2f, #10a37f)" }
];

function renderPortals() {
  const grid = document.getElementById('portalsGrid');
  if (!grid) return;

  grid.innerHTML = '';
  defaultPortals.forEach(portal => {
    const card = document.createElement('a');
    card.className = 'portal-card';
    card.href = portal.url;
    card.style.background = portal.bg;
    card.innerHTML = `
      <span class="portal-mark">${portal.mark}</span>
      <span class="portal-title">${portal.title}</span>
    `;
    card.addEventListener('click', (e) => {
      e.preventDefault();
      if (window.webkit && window.webkit.messageHandlers && window.webkit.messageHandlers.safeer) {
        window.webkit.messageHandlers.safeer.postMessage({ action: 'navigate', url: portal.url });
      } else {
        window.location.href = portal.url;
      }
    });
    grid.appendChild(card);
  });
}

function openSidebar(serviceId) {
  if (window.webkit && window.webkit.messageHandlers && window.webkit.messageHandlers.safeer) {
    window.webkit.messageHandlers.safeer.postMessage({ action: 'open_sidebar', service: serviceId });
  } else {
    alert(`Odpiram stransko integracijo: ${serviceId}`);
  }
}

function toggleEditMode() {
  alert("Urejanje portalov: V nastavitvah brskalnika lahko dodate svoje povezave ali prilagodite vrstni red.");
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
  updateClock();
  setInterval(updateClock, 1000);
  renderPortals();
});
