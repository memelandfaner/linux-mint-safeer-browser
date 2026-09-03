// Safeer Browser — Linux Mint Edition Start Page Logic

let currentEngine = 'google';
let currentHomeLang = 'sl';

const homeI18n = {
  sl: {
    locale: "sl-SI",
    app_title: "Safeer Browser",
    home_title: "Safeer Domača Stran",
    shield_subtitle: "Linux Mint Suverena Izdaja",
    shield_status: "🛡️ ZAŠČITA AKTIVNA",
    lbl_ads: "Blokirani oglasi",
    lbl_speed: "Odzivnost",
    lbl_oss: "Odprta koda",
    search_placeholder: "Iščite z Google ali vnesite spletni naslov...",
    search_submit: "Išči",
    quick_lbl: "Hitre možnosti:",
    quick_customizer: "🧩 Teme & Skripte",
    quick_toolbar: "⚙️ Uredi orodno vrstico",
    section_portals: "Priljubljene strani in multimedija",
    portals_note: "Brez oglasov • Zasebno • Hitro",
    btn_edit: "⚙️ Uredi",
    btn_add: "➕ Dodaj stran",
    add_site_tile: "Dodaj stran",
    btn_edit_title: "Upravljaj priljubljene strani",
    btn_add_title: "Dodaj novo bližnjico",
    add_site_title: "Dodaj novo priljubljeno stran ali multimedijo"
  },
  en: {
    locale: "en-US",
    app_title: "Safeer Browser",
    home_title: "Safeer Home",
    shield_subtitle: "Linux Mint Sovereign Edition",
    shield_status: "🛡️ SHIELD ACTIVE",
    lbl_ads: "Ads Blocked",
    lbl_speed: "Latency",
    lbl_oss: "Open Source",
    search_placeholder: "Search with Google or enter web address...",
    search_submit: "Search",
    quick_lbl: "Quick Options:",
    quick_customizer: "🧩 Themes & Scripts",
    quick_toolbar: "⚙️ Settings",
    section_portals: "Favorite Sites & Multimedia",
    portals_note: "No Ads • Private • Ultra Fast",
    btn_edit: "⚙️ Edit",
    btn_add: "➕ Add Site",
    add_site_tile: "Add Site",
    btn_edit_title: "Manage favorite sites",
    btn_add_title: "Add new site shortcut",
    add_site_title: "Add new favorite site or multimedia"
  },
  de: {
    locale: "de-DE",
    app_title: "Safeer Browser",
    home_title: "Safeer Startseite",
    shield_subtitle: "Linux Mint Souveräne Edition",
    shield_status: "🛡️ SCHUTZ AKTIV",
    lbl_ads: "Blockierte Werbung",
    lbl_speed: "Latenz",
    lbl_oss: "Open Source",
    search_placeholder: "Mit Google suchen oder Adresse eingeben...",
    search_submit: "Suchen",
    quick_lbl: "Schnellzugriff:",
    quick_customizer: "🧩 Themes & Skripte",
    quick_toolbar: "⚙️ Einstellungen",
    section_portals: "Favoriten & Multimedia",
    portals_note: "Werbefrei • Privat • Schnell",
    btn_edit: "⚙️ Bearbeiten",
    btn_add: "➕ Hinzufügen",
    add_site_tile: "Seite hinzufügen",
    btn_edit_title: "Favoriten verwalten",
    btn_add_title: "Neue Verknüpfung hinzufügen",
    add_site_title: "Neuen Favoriten oder Multimedia hinzufügen"
  },
  es: {
    locale: "es-ES",
    app_title: "Safeer Browser",
    home_title: "Página Principal Safeer",
    shield_subtitle: "Edición Soberana Linux Mint",
    shield_status: "🛡️ ESCUDO ACTIVO",
    lbl_ads: "Anuncios bloqueados",
    lbl_speed: "Latencia",
    lbl_oss: "Código Abierto",
    search_placeholder: "Buscar en Google o escribir dirección...",
    search_submit: "Buscar",
    quick_lbl: "Accesos rápidos:",
    quick_customizer: "🧩 Temas y Scripts",
    quick_toolbar: "⚙️ Configuración",
    section_portals: "Sitios Favoritos y Multimedia",
    portals_note: "Sin anuncios • Privado • Rápido",
    btn_edit: "⚙️ Editar",
    btn_add: "➕ Añadir",
    add_site_tile: "Añadir sitio",
    btn_edit_title: "Administrar sitios favoritos",
    btn_add_title: "Añadir nuevo acceso directo",
    add_site_title: "Añadir nuevo sitio favorito o multimedia"
  },
  fr: {
    locale: "fr-FR",
    app_title: "Safeer Browser",
    home_title: "Page d'accueil Safeer",
    shield_subtitle: "Édition Souveraine Linux Mint",
    shield_status: "🛡️ BOUCLIER ACTIF",
    lbl_ads: "Publicités bloquées",
    lbl_speed: "Latence",
    lbl_oss: "Open Source",
    search_placeholder: "Rechercher avec Google ou entrer une adresse...",
    search_submit: "Chercher",
    quick_lbl: "Outils rapides:",
    quick_customizer: "🧩 Thèmes & Scripts",
    quick_toolbar: "⚙️ Paramètres",
    section_portals: "Sites Favoris et Multimédia",
    portals_note: "Sans pub • Privé • Rapide",
    btn_edit: "⚙️ Modifier",
    btn_add: "➕ Ajouter",
    add_site_tile: "Ajouter un site",
    btn_edit_title: "Gérer les sites favoris",
    btn_add_title: "Ajouter un nouveau raccourci",
    add_site_title: "Ajouter un nouveau site favori ou multimédia"
  },
  it: {
    locale: "it-IT",
    app_title: "Safeer Browser",
    home_title: "Pagina iniziale Safeer",
    shield_subtitle: "Edizione Sovrana Linux Mint",
    shield_status: "🛡️ PROTEZIONE ATTIVA",
    lbl_ads: "Pubblicità bloccate",
    lbl_speed: "Latenza",
    lbl_oss: "Open Source",
    search_placeholder: "Cerca con Google o inserisci un indirizzo...",
    search_submit: "Cerca",
    quick_lbl: "Strumenti rapidi:",
    quick_customizer: "🧩 Temi e Script",
    quick_toolbar: "⚙️ Impostazioni",
    section_portals: "Siti Preferiti e Multimedia",
    portals_note: "Senza pubblicità • Privato • Veloce",
    btn_edit: "⚙️ Modifica",
    btn_add: "➕ Aggiungi",
    add_site_tile: "Aggiungi sito",
    btn_edit_title: "Gestisci i siti preferiti",
    btn_add_title: "Aggiungi nuova scorciatoia",
    add_site_title: "Aggiungi nuovo sito preferito o multimedia"
  }
};

function changeHomeLanguage(lang, notifyBackend = true) {
  if (!homeI18n[lang]) lang = 'en';
  currentHomeLang = lang;
  try {
    localStorage.setItem('safeer_home_lang', lang);
  } catch(e) {}

  const dict = homeI18n[lang];
  document.title = dict.home_title || "Safeer Home";

  document.querySelectorAll('[data-i18n]').forEach(el => {
    const key = el.getAttribute('data-i18n');
    if (dict[key]) el.textContent = dict[key];
  });

  document.querySelectorAll('[data-i18n-title]').forEach(el => {
    const key = el.getAttribute('data-i18n-title');
    if (dict[key]) el.title = dict[key];
  });

  const searchInput = document.getElementById('searchInput');
  if (searchInput && dict.search_placeholder) {
    searchInput.placeholder = dict.search_placeholder;
  }

  document.querySelectorAll('.lang-pill').forEach(btn => {
    btn.classList.toggle('active', btn.getAttribute('data-lang') === lang);
  });

  const addTileTxt = document.querySelector('.portal-add-card .portal-title');
  if (addTileTxt) {
    addTileTxt.textContent = dict.add_site_tile || dict.btn_add;
  }
  const addTileCard = document.querySelector('.portal-add-card');
  if (addTileCard && dict.add_site_title) {
    addTileCard.title = dict.add_site_title;
  }

  updateClock();

  if (notifyBackend && window.webkit && window.webkit.messageHandlers && window.webkit.messageHandlers.safeer) {
    window.webkit.messageHandlers.safeer.postMessage({ action: 'set_language', language: lang });
  }
}

window.setAppLanguage = function(lang) {
  changeHomeLanguage(lang, false);
};

const searchUrls = {
  google: 'https://www.google.com/search?q=',
  duckduckgo: 'https://duckduckgo.com/?q=',
  brave: 'https://search.brave.com/search?q=',
  bing: 'https://www.bing.com/search?q=',
  ecosia: 'https://www.ecosia.org/search?q=',
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
  if (searchUrls[engine]) {
    currentEngine = engine;
  }
  document.querySelectorAll('.engine-pills .pill').forEach(p => p.classList.remove('active'));
  if (btn) {
    btn.classList.add('active');
  } else {
    const matchingBtn = document.querySelector(`.engine-pills .pill[data-engine="${engine}"]`);
    if (matchingBtn) matchingBtn.classList.add('active');
  }
  
  const input = document.getElementById('searchInput');
  if (input) input.focus();
}

window.setSearchEngine = function(engine) {
  setEngine(engine);
};

function performSearch(event) {
  if (event) event.preventDefault();
  const input = document.getElementById('searchInput');
  if (!input) return false;
  const query = input.value.trim();
  if (!query) return false;

  let targetUrl = '';
  if (query.startsWith('http://') || query.startsWith('https://') || query.startsWith('file://')) {
    targetUrl = query;
  } else if (query.startsWith('localhost:') || query === 'localhost' || query.startsWith('127.0.0.1:') || query === '127.0.0.1') {
    targetUrl = 'http://' + query;
  } else if (query.includes('.') && !query.includes(' ')) {
    targetUrl = 'https://' + query;
  } else {
    const baseSearch = searchUrls[currentEngine] || searchUrls.google;
    targetUrl = baseSearch + encodeURIComponent(query);
  }

  // Communicate with Safeer Python Host or direct navigate
  if (window.webkit && window.webkit.messageHandlers && window.webkit.messageHandlers.safeer) {
    window.webkit.messageHandlers.safeer.postMessage({ action: 'navigate', url: targetUrl });
  } else {
    window.location.href = targetUrl;
  }
  return false;
}

// Global aliases to ensure both form onsubmit="return handleSearch(event)" and programmatic calls work
window.handleSearch = performSearch;
window.performSearch = performSearch;

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
  const dict = homeI18n[currentHomeLang] || homeI18n.sl;
  addCard.title = dict.add_site_title || 'Dodaj novo priljubljeno stran ali multimedijo';
  addCard.innerHTML = `
    <span class="portal-mark" style="font-size: 1.8rem; color: var(--accent-mint);">➕</span>
    <span class="portal-title" data-i18n="add_site_tile" style="color: var(--text-muted);">${dict.add_site_tile || dict.btn_add}</span>
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
  renderPortals();
  const savedLang = localStorage.getItem('safeer_home_lang') || 'sl';
  changeHomeLanguage(savedLang, false);
  setInterval(updateClock, 1000);
});
