// Safeer Browser — Linux Mint Edition Start Page Logic

let currentEngine = 'google';

const searchUrls = {
  google: 'https://www.google.com/search?q=',
  duckduckgo: 'https://duckduckgo.com/?q=',
  brave: 'https://search.brave.com/search?q=',
  youtube: 'https://www.youtube.com/results?search_query='
};

// 1. Live Clock & Date in Slovenian
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
  if (event) event.preventDefault();
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

  // Communicate with Safeer Python Host or direct navigate
  if (window.webkit && window.webkit.messageHandlers && window.webkit.messageHandlers.safeer) {
    window.webkit.messageHandlers.safeer.postMessage({ action: 'navigate', url: targetUrl });
  } else {
    window.location.href = targetUrl;
  }
  return false;
}

// 3. Portals Grid with Dynamic Synchronization & Management
const defaultPortals = [
  { id: "p1", title: "Xplore TV", url: "https://www.xploretv.si/livetv", mark: "📺", bg: "linear-gradient(145deg, #7a1024, #e31837)" },
  { id: "p2", title: "YouTube", url: "https://www.youtube.com", mark: "▶️", bg: "linear-gradient(145deg, #4a0b0b, #cc0000)" },
  { id: "p3", title: "24ur.com", url: "https://www.24ur.com", mark: "📰", bg: "linear-gradient(145deg, #0a2040, #1256a8)" },
  { id: "p4", title: "RTV SLO", url: "https://www.rtvslo.si", mark: "🇸🇮", bg: "linear-gradient(145deg, #04364a, #0284c7)" },
  { id: "p5", title: "Filmi & Serije", url: "https://hydrahd.ws/", mark: "🎬", bg: "linear-gradient(145deg, #062a38, #0277a3)" },
  { id: "p6", title: "ChatGPT AI", url: "https://chatgpt.com", mark: "🤖", bg: "linear-gradient(145deg, #063c2f, #10a37f)" },
  { id: "p7", title: "CryptoQuant", url: "https://cryptoquant.com", mark: "📊", bg: "linear-gradient(145deg, #3d2303, #d97706)" },
  { id: "p8", title: "GitHub", url: "https://github.com", mark: "🐙", bg: "linear-gradient(145deg, #1b1f24, #24292e)" }
];

let customPortalsList = null;

window.setCustomPortals = function(portals) {
  if (Array.isArray(portals) && portals.length > 0) {
    customPortalsList = portals;
    try {
      localStorage.setItem('safeer_custom_portals', JSON.stringify(portals));
    } catch(e) {}
    renderPortals();
  }
};

function getActivePortals() {
  if (customPortalsList && customPortalsList.length > 0) return customPortalsList;
  try {
    const raw = localStorage.getItem('safeer_custom_portals');
    if (raw) {
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed) && parsed.length > 0) {
        customPortalsList = parsed;
        return customPortalsList;
      }
    }
  } catch(e) {}
  return defaultPortals;
}

function renderPortals() {
  const grid = document.getElementById('portalsGrid');
  if (!grid) return;

  const portals = getActivePortals();
  grid.innerHTML = '';

  portals.forEach(portal => {
    const card = document.createElement('a');
    card.className = 'portal-card';
    card.href = portal.url;
    card.style.background = portal.bg || `linear-gradient(145deg, #0f172a, ${portal.color || '#00d2ff'})`;
    card.innerHTML = `
      <span class="portal-mark">${portal.mark || '🌐'}</span>
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

  // Dodaj kartico "➕ Dodaj stran" na konec mreže
  const addCard = document.createElement('div');
  addCard.className = 'portal-card portal-add-card';
  addCard.style.border = '2px dashed rgba(255, 255, 255, 0.2)';
  addCard.style.background = 'rgba(255, 255, 255, 0.02)';
  addCard.style.cursor = 'pointer';
  addCard.title = 'Dodaj novo priljubljeno stran ali multimedijo';
  addCard.innerHTML = `
    <span class="portal-mark" style="font-size: 1.8rem; color: var(--accent-mint);">➕</span>
    <span class="portal-title" style="color: var(--text-muted);">Dodaj stran</span>
  `;
  addCard.addEventListener('click', () => {
    openSidebar('add_portal');
  });
  grid.appendChild(addCard);
}

function openSidebar(serviceId) {
  if (window.webkit && window.webkit.messageHandlers && window.webkit.messageHandlers.safeer) {
    window.webkit.messageHandlers.safeer.postMessage({ action: 'open_sidebar', service: serviceId });
  } else {
    console.log(`Open sidebar: ${serviceId}`);
  }
}

// 4. Initialize
document.addEventListener('DOMContentLoaded', () => {
  updateClock();
  setInterval(updateClock, 1000);
  renderPortals();
});
