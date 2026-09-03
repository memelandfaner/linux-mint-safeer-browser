// Safeer Browser — Linux Mint Edition Start Page Logic

let currentEngine = 'google';
let currentHomeLang = 'sl';

const homeI18n = {
  sl: {
    locale: "sl-SI",
    lbl_oss: "Odprta koda",
    search_placeholder: "Iščite z Google ali vnesite spletni naslov...",
    search_submit: "Išči",
    quick_lbl: "Hitre možnosti:",
    quick_customizer: "🧩 Teme & Skripte",
    quick_toolbar: "⚙️ Uredi orodno vrstico",
    section_portals: "Priljubljene strani in multimedija",
    portals_note: "Brez oglasov • Zasebno • Hitro",
    btn_edit: "⚙️ Uredi",
    btn_add: "➕ Dodaj stran"
  },
  en: {
    locale: "en-US",
    lbl_oss: "Open Source",
    search_placeholder: "Search with Google or enter web address...",
    search_submit: "Search",
    quick_lbl: "Quick Options:",
    quick_customizer: "🧩 Themes & Scripts",
    quick_toolbar: "⚙️ Settings",
    section_portals: "Favorite Sites & Multimedia",
    portals_note: "No Ads • Private • Ultra Fast",
    btn_edit: "⚙️ Edit",
    btn_add: "➕ Add Site"
  },
  de: {
    locale: "de-DE",
    lbl_oss: "Open Source",
    search_placeholder: "Mit Google suchen oder Adresse eingeben...",
    search_submit: "Suchen",
    quick_lbl: "Schnellzugriff:",
    quick_customizer: "🧩 Themes & Skripte",
    quick_toolbar: "⚙️ Einstellungen",
    section_portals: "Favoriten & Multimedia",
    portals_note: "Werbefrei • Privat • Schnell",
    btn_edit: "⚙️ Bearbeiten",
    btn_add: "➕ Hinzufügen"
  },
  es: {
    locale: "es-ES",
    lbl_oss: "Código Abierto",
    search_placeholder: "Buscar en Google o escribir dirección...",
    search_submit: "Buscar",
    quick_lbl: "Accesos rápidos:",
    quick_customizer: "🧩 Temas y Scripts",
    quick_toolbar: "⚙️ Configuración",
    section_portals: "Sitios Favoritos y Multimedia",
    portals_note: "Sin anuncios • Privado • Rápido",
    btn_edit: "⚙️ Editar",
    btn_add: "➕ Añadir"
  },
  fr: {
    locale: "fr-FR",
    lbl_oss: "Open Source",
    search_placeholder: "Rechercher avec Google ou entrer une adresse...",
    search_submit: "Chercher",
    quick_lbl: "Outils rapides:",
    quick_customizer: "🧩 Thèmes & Scripts",
    quick_toolbar: "⚙️ Paramètres",
    section_portals: "Sites Favoris et Multimédia",
    portals_note: "Sans pub • Privé • Rapide",
    btn_edit: "⚙️ Modifier",
    btn_add: "➕ Ajouter"
  },
  it: {
    locale: "it-IT",
    lbl_oss: "Open Source",
    search_placeholder: "Cerca con Google o inserisci un indirizzo...",
    search_submit: "Cerca",
    quick_lbl: "Strumenti rapidi:",
    quick_customizer: "🧩 Temi e Script",
    quick_toolbar: "⚙️ Impostazioni",
    section_portals: "Siti Preferiti e Multimedia",
    portals_note: "Senza pubblicità • Privato • Veloce",
    btn_edit: "⚙️ Modifica",
    btn_add: "➕ Aggiungi"
  }
};

function changeHomeLanguage(lang) {
  if (!homeI18n[lang]) lang = 'en';
  currentHomeLang = lang;
  try {
    localStorage.setItem('safeer_home_lang', lang);
  } catch(e) {}

  const dict = homeI18n[lang];
  document.querySelectorAll('[data-i18n]').forEach(el => {
    const key = el.getAttribute('data-i18n');
    if (dict[key]) el.textContent = dict[key];
  });

  const searchInput = document.getElementById('searchInput');
  if (searchInput && dict.search_placeholder) {
    searchInput.placeholder = dict.search_placeholder;
  }

  document.querySelectorAll('.lang-pill').forEach(btn => {
    btn.classList.toggle('active', btn.getAttribute('data-lang') === lang);
  });

  updateClock();
}

window.setAppLanguage = function(lang) {
  changeHomeLanguage(lang);
};

const searchUrls = {
  google: 'https://www.google.com/search?q=',
  duckduckgo: 'https://duckduckgo.com/?q=',
  brave: 'https://search.brave.com/search?q=',
  youtube: 'https://www.youtube.com/results?search_query='
};

// 1. Live Clock & Date localized
function updateClock() {
  const now = new Date();
  const hours = String(now.getHours()).padStart(2, '0');
  const minutes = String(now.getMinutes()).padStart(2, '0');
  
  const timeEl = document.getElementById('clockTime');
  if (timeEl) timeEl.textContent = `${hours}:${minutes}`;

  const dateEl = document.getElementById('clockDate');
  if (dateEl) {
    const dict = homeI18n[currentHomeLang] || homeI18n.sl;
    const loc = dict.locale || 'sl-SI';
    const options = { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' };
    dateEl.textContent = now.toLocaleDateString(loc, options);
  }
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
  const savedLang = localStorage.getItem('safeer_home_lang') || 'sl';
  changeHomeLanguage(savedLang);
  setInterval(updateClock, 1000);
  renderPortals();
});
