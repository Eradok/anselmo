# patch_export.py
# Run after every Godot web export: python patch_export.py

import os
import sys
import re

HTML_FILE = "index.html"
SW_FILE = "index.service.worker.js"

CSS = """
/* -------------------------
   MONITOR OVERLAY
-------------------------- */
#monitor-overlay {
	position: fixed;
	top: 0;
	left: 0;
	width: 100%;
	height: 100%;
	pointer-events: none;
	z-index: 10;
	overflow: hidden;
}
#monitor-frame {
	position: absolute;
	width: 420px;
	height: 700px;
	transform-origin: center center;
	pointer-events: auto;
	will-change: transform, left, top;
	background: #111;
	border-radius: 8px;
	padding: 10px;
	box-shadow: 0 0 40px rgba(0,0,0,0.8), inset 0 0 8px rgba(0,0,0,0.6);
	display: none;
}
#monitor-iframe {
	width: 100%;
	height: 100%;
	border: none;
	border-radius: 4px;
	display: block;
}
"""

HTML_DIV = """	<div id="monitor-overlay">
		<div id="monitor-frame">
			<iframe id="monitor-iframe" src="https://anselmo.blog" scrolling="no" frameborder="0"></iframe>
		</div>
	</div>
"""

JS_EARLY = """<script>
	/* MONITOR OVERLAY - polls a queue written by Godot via JavaScriptBridge.eval */
	window._monitorQueue = null;
	(function poll() {
		var q = window._monitorQueue;
		if (q) {
			window._monitorQueue = null;
			var normX = q[0], normY = q[1], hAngle = q[2], vAngle = q[3], scaleFactor = q[4];
			var frame = document.getElementById('monitor-frame');
			if (frame) {
				if (normX < 0) {
					frame.style.display = 'none';
				} else {
					frame.style.display = 'block';
					var canvas = document.getElementById('canvas');
					var cw = canvas ? canvas.clientWidth : window.innerWidth;
					var ch = canvas ? canvas.clientHeight : window.innerHeight;
					var left = (normX * cw) - 210;
					var top  = (normY * ch) - 350;
					var ry = Math.max(-45, Math.min(45, -hAngle));
					var rx = Math.max(-30, Math.min(30,  vAngle));
					frame.style.left = left + 'px';
					frame.style.top  = top  + 'px';
					frame.style.transform = 'perspective(1200px) rotateY(' + ry + 'deg) rotateX(' + rx + 'deg) scale(' + scaleFactor + ')';
				}
			}
		}
		requestAnimationFrame(poll);
	})();
</script>
"""

# ── HTML patching ─────────────────────────────────────

def check_file(path):
    if not os.path.exists(path):
        return False
    return True

def read_file(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def write_file(path, content):
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

def inject_css(html):
    if "#monitor-overlay" in html:
        print("  CSS: already present, skipping")
        return html
    if "</style>" not in html:
        print("  CSS: ERROR - could not find </style> tag")
        return html
    html = html.replace("</style>", CSS + "\n\t\t</style>", 1)
    print("  CSS: injected OK")
    return html

def inject_div(html):
    if 'id="monitor-overlay"' in html:
        print("  DIV: already present, skipping")
        return html
    candidates = [
        '<canvas id="canvas">',
        "<canvas id='canvas'>",
        '<canvas id="canvas" ',
        '<canvas id=canvas>',
    ]
    for candidate in candidates:
        if candidate in html:
            html = html.replace(candidate, HTML_DIV + "\n\t\t" + candidate, 1)
            print("  DIV: injected OK")
            return html
    match = re.search(r'<canvas\b[^>]*>', html, re.IGNORECASE)
    if match:
        canvas_tag = match.group(0)
        html = html.replace(canvas_tag, HTML_DIV + "\n\t\t" + canvas_tag, 1)
        print("  DIV: injected OK (regex)")
        return html
    if "<body>" in html:
        html = html.replace("<body>", "<body>\n" + HTML_DIV, 1)
        print("  DIV: injected OK (after <body>)")
        return html
    print("  DIV: ERROR - could not find injection point")
    return html

def inject_js_early(html):
    if "_monitorQueue" in html:
        js_pos = html.find("_monitorQueue")
        for pattern in ['<script src="index.js">', "<script src='index.js'>",
                        '<script src="anselmo.blog.js">', "<script src='anselmo.blog.js'>"]:
            src_pos = html.find(pattern)
            if src_pos != -1:
                if js_pos < src_pos:
                    print("   JS: already in correct position, skipping")
                    return html
                else:
                    print("   JS: found but in wrong position, re-injecting")
                    html = re.sub(
                        r'<script>\s*/\* MONITOR OVERLAY.*?</script>\s*',
                        '', html, flags=re.DOTALL
                    )
                    break
        else:
            print("   JS: already present, skipping")
            return html

    index_js_patterns = [
        '<script src="index.js">',
        "<script src='index.js'>",
        '<script src="anselmo.blog.js">',
        "<script src='anselmo.blog.js'>",
    ]
    for pattern in index_js_patterns:
        if pattern in html:
            html = html.replace(pattern, JS_EARLY + "\n\t\t" + pattern, 1)
            print("   JS: injected OK (before " + pattern + ")")
            return html

    match = re.search(r'<script\s+src=', html, re.IGNORECASE)
    if match:
        html = html[:match.start()] + JS_EARLY + "\n\t\t" + html[match.start():]
        print("   JS: injected OK (fallback)")
        return html

    print("   JS: ERROR - could not find injection point")
    return html

# ── Service worker patching ───────────────────────────

# The new fetch handler that skips COEP headers for cross-origin requests
# and also skips the broken preloadResponse for navigate requests to cross-origin URLs
SW_FETCH_REPLACEMENT = '''self.addEventListener(
	'fetch',
	/**
	 * Triggered on fetch
	 * @param {FetchEvent} event
	 */
	(event) => {
		const isNavigate = event.request.mode === 'navigate';
		const url = event.request.url || '';
		const referrer = event.request.referrer || '';
		const base = referrer.slice(0, referrer.lastIndexOf('/') + 1);
		const local = url.startsWith(base) ? url.replace(base, '') : '';
		const isCacheable = FULL_CACHE.some((v) => v === local) || (base === referrer && base.endsWith(CACHED_FILES[0]));

		// Let cross-origin requests pass through completely untouched.
		// This allows the iframe to load without COEP interference.
		if (!url.startsWith(self.location.origin)) {
			return;
		}

		if (isNavigate || isCacheable) {
			event.respondWith((async () => {
				const cache = await caches.open(CACHE_NAME);
				if (isNavigate) {
					const fullCache = await Promise.all(FULL_CACHE.map((name) => cache.match(name)));
					const missing = fullCache.some((v) => v === undefined);
					if (missing) {
						try {
							const response = await fetchAndCache(event, cache, isCacheable);
							return response;
						} catch (e) {
							console.error('Network error: ', e); // eslint-disable-line no-console
							return caches.match(OFFLINE_URL);
						}
					}
				}
				let cached = await cache.match(event.request);
				if (cached != null) {
					if (ENSURE_CROSSORIGIN_ISOLATION_HEADERS) {
						cached = ensureCrossOriginIsolationHeaders(cached);
					}
					return cached;
				}
				const response = await fetchAndCache(event, cache, isCacheable);
				return response;
			})());
		} else if (ENSURE_CROSSORIGIN_ISOLATION_HEADERS) {
			event.respondWith((async () => {
				let response = await fetch(event.request);
				response = ensureCrossOriginIsolationHeaders(response);
				return response;
			})());
		}
	}
);'''

# Also fix fetchAndCache to not use preloadResponse for cross-origin requests
FETCH_AND_CACHE_REPLACEMENT = '''async function fetchAndCache(event, cache, isCacheable) {
	const url = event.request.url || '';
	/** @type { Response } */
	let response;
	// Only use preloadResponse for same-origin requests
	if (url.startsWith(self.location.origin)) {
		response = await event.preloadResponse;
	}
	if (response == null) {
		response = await self.fetch(event.request);
	}

	if (ENSURE_CROSSORIGIN_ISOLATION_HEADERS) {
		response = ensureCrossOriginIsolationHeaders(response);
	}

	if (isCacheable) {
		cache.put(event.request, response.clone());
	}

	return response;
}'''

def patch_service_worker(sw):
    changed = False

    # Fix fetchAndCache
    if "// Only use preloadResponse for same-origin requests" in sw:
        print("   SW fetchAndCache: already patched, skipping")
    else:
        old = re.search(
            r'async function fetchAndCache\(event, cache, isCacheable\).*?^}',
            sw, flags=re.DOTALL | re.MULTILINE
        )
        if old:
            sw = sw[:old.start()] + FETCH_AND_CACHE_REPLACEMENT + sw[old.end():]
            print("   SW fetchAndCache: patched OK")
            changed = True
        else:
            print("   SW fetchAndCache: ERROR - could not find function to patch")

    # Fix fetch listener
    if "Let cross-origin requests pass through completely untouched" in sw:
        print("   SW fetch listener: already patched, skipping")
    else:
        old = re.search(
            r"self\.addEventListener\(\s*'fetch'.*?\);",
            sw, flags=re.DOTALL
        )
        if old:
            sw = sw[:old.start()] + SW_FETCH_REPLACEMENT + sw[old.end():]
            print("   SW fetch listener: patched OK")
            changed = True
        else:
            print("   SW fetch listener: ERROR - could not find listener to patch")

    return sw, changed

# ── Verify ───────────────────────────────────────────

def verify_html(html):
    print("\nVerifying index.html...")
    checks = [
        ("monitor-overlay CSS",   "#monitor-overlay"      ),
        ("monitor-frame CSS",     "#monitor-frame"        ),
        ("monitor-overlay DIV",   'id="monitor-overlay"'  ),
        ("monitor-frame DIV",     'id="monitor-frame"'    ),
        ("monitor-iframe DIV",    'id="monitor-iframe"'   ),
        ("JS queue system",       "_monitorQueue"         ),
        ("JS poll loop",          "requestAnimationFrame" ),
    ]
    all_ok = True
    for name, token in checks:
        if token in html:
            print("  OK      " + name)
        else:
            print("  MISSING " + name)
            all_ok = False

    js_pos = html.find("_monitorQueue")
    for pattern in ['<script src="index.js">', '<script src="anselmo.blog.js">']:
        src_pos = html.find(pattern)
        if src_pos != -1:
            if js_pos != -1 and js_pos < src_pos:
                print("  OK      JS queue is before index.js (correct load order)")
            else:
                print("  WARNING JS queue is AFTER index.js!")
                all_ok = False
            break
    return all_ok

def verify_sw(sw):
    print("\nVerifying " + SW_FILE + "...")
    checks = [
        ("cross-origin passthrough", "Let cross-origin requests pass through completely untouched"),
        ("preloadResponse fix",      "Only use preloadResponse for same-origin requests"),
    ]
    all_ok = True
    for name, token in checks:
        if token in sw:
            print("  OK      " + name)
        else:
            print("  MISSING " + name)
            all_ok = False
    return all_ok

# ── RUN ──────────────────────────────────────────────

print("=== patch_export.py ===\n")

# HTML
if not check_file(HTML_FILE):
    print("ERROR: " + HTML_FILE + " not found. Run this from the export folder.")
    sys.exit(1)
print("Found: " + HTML_FILE)
print("\nPatching HTML...")
html = read_file(HTML_FILE)
html = inject_css(html)
html = inject_div(html)
html = inject_js_early(html)
write_file(HTML_FILE, html)
html_ok = verify_html(html)

# Service worker
print("")
if not check_file(SW_FILE):
    print("WARNING: " + SW_FILE + " not found - skipping service worker patch")
    sw_ok = False
else:
    print("Found: " + SW_FILE)
    print("\nPatching service worker...")
    sw = read_file(SW_FILE)
    sw, sw_changed = patch_service_worker(sw)
    if sw_changed:
        write_file(SW_FILE, sw)
        print("   SW: saved OK")
    sw_ok = verify_sw(sw)

print("")
if html_ok and sw_ok:
    print("✅ All checks passed - index.html and service worker are ready!")
elif html_ok:
    print("✅ HTML ready. ⚠️  Service worker had issues - check above.")
else:
    print("❌ Some items missing - check above.")