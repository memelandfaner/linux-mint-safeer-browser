# ==============================================================================
# Safeer Browser — Linux Mint Edition: Reader Mode Engine
# Distraction-Free Article Extraction, Typographic Rendering & Themes
# ==============================================================================

READER_MODE_JS = r"""
(function() {
    if (window.__safeerReaderActive) {
        if (typeof window.__safeerExitReader === 'function') {
            window.__safeerExitReader();
        } else {
            window.location.reload();
        }
        return;
    }

    try {
        window.__safeerOriginalHtml = document.documentElement.innerHTML;
        const pageTitle = document.querySelector('meta[property="og:title"]')?.content ||
                          document.querySelector('h1')?.innerText ||
                          document.title || 'Članek';

        const pageAuthor = document.querySelector('meta[name="author"]')?.content ||
                           document.querySelector('[rel="author"]')?.innerText ||
                           document.querySelector('.byline, .author, .entry-author, .article-author')?.innerText || '';

        const pageDate = document.querySelector('meta[property="article:published_time"]')?.content ||
                         document.querySelector('time')?.innerText || '';

        const leadImg = document.querySelector('meta[property="og:image"]')?.content || '';

        // Find candidate article content container
        const candidates = document.querySelectorAll('article, [role="main"], main, .article-body, .article-content, .post-content, .entry-content, .story-body, .content-body');
        let bestContainer = null;
        let maxScore = -1;

        if (candidates.length > 0) {
            candidates.forEach(el => {
                const pCount = el.querySelectorAll('p').length;
                const txtLen = el.innerText.length;
                const score = (pCount * 25) + txtLen;
                if (score > maxScore) {
                    maxScore = score;
                    bestContainer = el;
                }
            });
        }

        if (!bestContainer || maxScore < 100) {
            // Fallback: scan all divs & sections
            document.querySelectorAll('div, section').forEach(el => {
                const pCount = el.querySelectorAll('p').length;
                if (pCount >= 3) {
                    const txtLen = el.innerText.length;
                    const score = (pCount * 30) + txtLen;
                    if (score > maxScore) {
                        maxScore = score;
                        bestContainer = el;
                    }
                }
            });
        }

        if (!bestContainer) {
            bestContainer = document.body;
        }

        // Clone and sanitize content
        const clone = bestContainer.cloneNode(true);

        // Remove junk elements
        const junk = clone.querySelectorAll(
            'script, style, noscript, nav, header, footer, aside, form, iframe, button, ' +
            '[role="navigation"], [role="banner"], [role="complementary"], ' +
            '.ad, .advertisement, .ad-box, .banner, .social, .share, .comments, ' +
            '.related, .sidebar, .popup, .newsletter, .cookie, .hidden'
        );
        junk.forEach(j => j.remove());

        // Strip inline styles and classes to guarantee clean typography
        clone.querySelectorAll('*').forEach(el => {
            el.removeAttribute('style');
            el.removeAttribute('class');
            el.removeAttribute('id');
        });

        // HTML Escape helper to prevent XSS injection
        function escapeHtml(str) {
            if (!str) return '';
            return String(str)
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/"/g, '&quot;')
                .replace(/'/g, '&#039;');
        }

        const safeTitle = escapeHtml(pageTitle);
        const safeAuthor = escapeHtml(pageAuthor);
        const safeDate = escapeHtml(pageDate);

        // Compute estimated reading time
        const fullText = clone.innerText || '';
        const wordCount = fullText.trim().split(/\s+/).filter(Boolean).length;
        const readMinutes = Math.max(1, Math.round(wordCount / 200));

        // Format lead image HTML
        let imgHtml = '';
        if (leadImg && !leadImg.includes('logo') && !leadImg.includes('icon')) {
            const safeImg = escapeHtml(leadImg);
            imgHtml = `<div class="reader-lead-img"><img src="${safeImg}" alt="Lead Image" /></div>`;
        }

        // Reader Mode Full HTML
        const readerHtml = `
<!DOCTYPE html>
<html lang="sl" data-reader-theme="dark">
<head>
    <meta charset="UTF-8">
    <title>📖 ${safeTitle} — Safeer Reader</title>
    <style>
        :root {
            --reader-bg: #141720;
            --reader-text: #e2e8f0;
            --reader-muted: #94a3b8;
            --reader-card: #1e2230;
            --reader-accent: #38bdf8;
            --reader-border: rgba(255, 255, 255, 0.1);
            --reader-font-size: 19px;
            --reader-line-height: 1.8;
            --reader-max-w: 720px;
        }
        [data-reader-theme="sepia"] {
            --reader-bg: #f4ecd8;
            --reader-text: #443224;
            --reader-muted: #7d6b5a;
            --reader-card: #e9dec4;
            --reader-accent: #8b5cf6;
            --reader-border: rgba(0, 0, 0, 0.1);
        }
        [data-reader-theme="amoled"] {
            --reader-bg: #000000;
            --reader-text: #f1f5f9;
            --reader-muted: #64748b;
            --reader-card: #121212;
            --reader-accent: #38bdf8;
            --reader-border: rgba(255, 255, 255, 0.12);
        }
        [data-reader-theme="light"] {
            --reader-bg: #ffffff;
            --reader-text: #1e293b;
            --reader-muted: #64748b;
            --reader-card: #f8fafc;
            --reader-accent: #0284c7;
            --reader-border: rgba(0, 0, 0, 0.08);
        }

        * { box-sizing: border-box; }
        html, body {
            margin: 0;
            padding: 0;
            background: var(--reader-bg) !important;
            color: var(--reader-text) !important;
            font-family: -apple-system, BlinkMacSystemFont, "Plus Jakarta Sans", "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            font-size: var(--reader-font-size);
            line-height: var(--reader-line-height);
            transition: background 150ms ease, color 150ms ease;
            -webkit-font-smoothing: antialiased;
        }

        /* Top Navigation Bar */
        .reader-toolbar {
            position: sticky;
            top: 0;
            z-index: 99999;
            background: var(--reader-card);
            border-bottom: 1px solid var(--reader-border);
            padding: 10px 20px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            backdrop-filter: blur(12px);
            box-shadow: 0 4px 16px rgba(0,0,0,0.15);
        }
        .reader-left {
            display: flex;
            align-items: center;
            gap: 12px;
        }
        .reader-badge {
            background: rgba(56, 189, 248, 0.15);
            color: var(--reader-accent);
            padding: 4px 10px;
            border-radius: 9999px;
            font-size: 13px;
            font-weight: 700;
            display: flex;
            align-items: center;
            gap: 6px;
        }
        .reader-meta-tag {
            color: var(--reader-muted);
            font-size: 13.5px;
            font-weight: 500;
        }
        .reader-controls {
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .reader-btn {
            background: var(--reader-bg);
            color: var(--reader-text);
            border: 1px solid var(--reader-border);
            border-radius: 6px;
            padding: 6px 12px;
            font-size: 13.5px;
            font-weight: 600;
            cursor: pointer;
            transition: all 120ms ease;
            user-select: none;
        }
        .reader-btn:hover {
            border-color: var(--reader-accent);
            color: var(--reader-accent);
            transform: translateY(-1px);
        }
        .reader-btn-exit {
            background: #ef4444;
            color: #ffffff;
            border: none;
        }
        .reader-btn-exit:hover {
            background: #dc2626;
            color: #ffffff;
        }

        /* Container & Typography */
        .reader-article-wrap {
            max-width: var(--reader-max-w);
            margin: 40px auto 100px auto;
            padding: 0 24px;
        }
        h1.reader-title {
            font-size: 2.3rem;
            line-height: 1.25;
            font-weight: 800;
            margin: 0 0 16px 0;
            color: var(--reader-text);
            letter-spacing: -0.02em;
        }
        .reader-byline {
            color: var(--reader-muted);
            font-size: 14.5px;
            margin-bottom: 28px;
            display: flex;
            flex-wrap: wrap;
            gap: 12px;
            border-bottom: 1px solid var(--reader-border);
            padding-bottom: 16px;
        }
        .reader-lead-img {
            margin: 24px 0 32px 0;
            border-radius: 12px;
            overflow: hidden;
            box-shadow: 0 8px 24px rgba(0,0,0,0.25);
        }
        .reader-lead-img img {
            width: 100%;
            height: auto;
            display: block;
            object-fit: cover;
        }
        .reader-body p {
            margin: 0 0 1.5em 0;
        }
        .reader-body h2, .reader-body h3, .reader-body h4 {
            color: var(--reader-text);
            margin-top: 1.8em;
            margin-bottom: 0.6em;
            line-height: 1.35;
        }
        .reader-body img {
            max-width: 100%;
            height: auto;
            border-radius: 8px;
            margin: 20px auto;
            display: block;
        }
        .reader-body blockquote {
            border-left: 4px solid var(--reader-accent);
            margin: 1.5em 0;
            padding: 8px 20px;
            font-style: italic;
            color: var(--reader-muted);
            background: rgba(255,255,255,0.02);
            border-radius: 0 8px 8px 0;
        }
        .reader-body a {
            color: var(--reader-accent);
            text-decoration: underline;
            text-underline-offset: 3px;
        }
        .reader-body ul, .reader-body ol {
            margin: 0 0 1.5em 0;
            padding-left: 28px;
        }
        .reader-body li {
            margin-bottom: 0.5em;
        }
    </style>
</head>
<body>
    <div class="reader-toolbar">
        <div class="reader-left">
            <span class="reader-badge">🍃 Safeer Reader</span>
            <span class="reader-meta-tag">⏱️ ${readMinutes} min branja • ${wordCount} besed</span>
        </div>
        <div class="reader-controls">
            <button type="button" class="reader-btn" onclick="adjustFont(-1)" title="Pomanjšaj pisavo">A-</button>
            <button type="button" class="reader-btn" onclick="adjustFont(1)" title="Povečaj pisavo">A+</button>
            <button type="button" class="reader-btn" onclick="setTheme('dark')" title="Temna tema">🌙</button>
            <button type="button" class="reader-btn" onclick="setTheme('sepia')" title="Sepia topla tema">📜</button>
            <button type="button" class="reader-btn" onclick="setTheme('amoled')" title="Čista črna OLED">🖤</button>
            <button type="button" class="reader-btn" onclick="setTheme('light')" title="Svetla tema">☀️</button>
            <button type="button" class="reader-btn reader-btn-exit" onclick="exitReader()" title="Zapri bralnik (Izhod)">✕ Izhod</button>
        </div>
    </div>

    <article class="reader-article-wrap">
        <h1 class="reader-title">${safeTitle}</h1>
        <div class="reader-byline">
            ${safeAuthor ? `<span>✍️ <b>${safeAuthor}</b></span>` : ''}
            ${safeDate ? `<span>📅 ${safeDate}</span>` : ''}
            <span>🛡️ Brez oglasov in sledilcev</span>
        </div>
        ${imgHtml}
        <div class="reader-body">
            ${clone.innerHTML}
        </div>
    </article>

    <script>
        let currentSize = 19;
        function adjustFont(delta) {
            currentSize = Math.max(14, Math.min(32, currentSize + delta));
            document.documentElement.style.setProperty('--reader-font-size', currentSize + 'px');
            try { localStorage.setItem('safeer_reader_font', currentSize); } catch(e){}
        }

        function setTheme(theme) {
            document.documentElement.setAttribute('data-reader-theme', theme);
            try { localStorage.setItem('safeer_reader_theme', theme); } catch(e){}
        }

        function exitReader() {
            if (window.__safeerOriginalHtml) {
                document.documentElement.innerHTML = window.__safeerOriginalHtml;
                window.__safeerReaderActive = false;
                window.location.reload();
            } else {
                window.location.reload();
            }
        }

        window.__safeerExitReader = exitReader;

        try {
            const savedTheme = localStorage.getItem('safeer_reader_theme');
            if (savedTheme) setTheme(savedTheme);
            const savedFont = parseInt(localStorage.getItem('safeer_reader_font'), 10);
            if (savedFont) {
                currentSize = savedFont;
                document.documentElement.style.setProperty('--reader-font-size', currentSize + 'px');
            }
        } catch(e){}
    <\/script>
</body>
</html>
        `;

        document.open();
        document.write(readerHtml);
        document.close();
        window.__safeerReaderActive = true;

    } catch (e) {
        console.error('[Safeer Reader] Napaka pri aktivaciji bralnega načina:', e);
    }
})();
"""
