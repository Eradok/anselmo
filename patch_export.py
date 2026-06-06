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

def read_file(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def write_file(path, content):
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

# ── HTML patches ──────────────────────────────────────

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
                    print("   JS: wrong position, re-injecting")
                    html = re.sub(r'<script>\s*/\* MONITOR OVERLAY.*?</script>\s*', '', html, flags=re.DOTALL)
                    break
        else:
            print("   JS: already present, skipping")
            return html

    for pattern in ['<script src="index.js">', "<script src='index.js'>",
                    '<script src="anselmo.blog.js">', "<script src='anselmo.blog.js'>"]:
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

# ── Service worker patch ──────────────────────────────

def patch_service_worker(sw):
    changed = False

    # Patch 1: disable navigationPreload
    marker1 = "/* PATCHED: navigationPreload disabled */"
    if marker1 not in sw:
        old = "return ('navigationPreload' in self.registration) ? self.registration.navigationPreload.enable() : Promise.resolve();"
        new = marker1 + "\n\t\treturn ('navigationPreload' in self.registration) ? self.registration.navigationPreload.disable() : Promise.resolve();"
        if old in sw:
            sw = sw.replace(old, new, 1)
            print("   SW: navigationPreload disabled OK")
            changed = True
        else:
            print("   SW: WARNING - could not find navigationPreload line")
    else:
        print("   SW: navigationPreload already patched, skipping")

    # Patch 2: bypass fetch handler for cross-origin (iframe) requests
    marker2 = "/* PATCHED: cross-origin bypass */"
    if marker2 not in sw:
        # Find the fetch event listener and inject a bypass at the top of its handler
        # Godot SW looks like: self.addEventListener('fetch', function(e) { ... })
        fetch_pattern = re.search(
            r"(self\.addEventListener\s*\(\s*['\"]fetch['\"].*?function\s*\([^)]*\)\s*\{)",
            sw, re.DOTALL
        )
        if fetch_pattern:
            insert_after = fetch_pattern.group(0)
            bypass_code = (
                insert_after
                + "\n\t\t" + marker2
                + "\n\t\tif (!e.request.url.startsWith(self.location.origin)) { return; }"
            )
            sw = sw.replace(insert_after, bypass_code, 1)
            print("   SW: cross-origin bypass injected OK")
            changed = True
        else:
            print("   SW: WARNING - could not find fetch handler to inject bypass")
    else:
        print("   SW: cross-origin bypass already patched, skipping")

    return sw, changed

# ── Verify ────────────────────────────────────────────

def verify_html(html):
    print("\nVerifying index.html...")
    checks = [
        ("monitor-overlay CSS",  "#monitor-overlay"      ),
        ("monitor-frame CSS",    "#monitor-frame"        ),
        ("monitor-overlay DIV",  'id="monitor-overlay"'  ),
        ("monitor-frame DIV",    'id="monitor-frame"'    ),
        ("monitor-iframe DIV",   'id="monitor-iframe"'   ),
        ("JS queue system",      "_monitorQueue"         ),
        ("JS poll loop",         "requestAnimationFrame" ),
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
    ok = True
    if "navigationPreload disabled" in sw:
        print("  OK      navigationPreload disabled")
    else:
        print("  MISSING navigationPreload patch")
        ok = False
    if "cross-origin bypass" in sw:
        print("  OK      cross-origin bypass present")
    else:
        print("  MISSING cross-origin bypass")
        ok = False
    return ok

# ── RUN ──────────────────────────────────────────────

print("=== patch_export.py ===\n")

if not os.path.exists(HTML_FILE):
    print("ERROR: index.html not found. Run this from the export folder.")
    sys.exit(1)

print("Found: " + HTML_FILE)
print("\nPatching HTML...")
html = read_file(HTML_FILE)
html = inject_css(html)
html = inject_div(html)
html = inject_js_early(html)
write_file(HTML_FILE, html)
html_ok = verify_html(html)

print("")
if not os.path.exists(SW_FILE):
    print("WARNING: " + SW_FILE + " not found, skipping")
    sw_ok = False
else:
    print("Found: " + SW_FILE)
    print("\nPatching service worker...")
    sw = read_file(SW_FILE)
    sw, changed = patch_service_worker(sw)
    if changed:
        write_file(SW_FILE, sw)
    sw_ok = verify_sw(sw)

print("")
if html_ok and sw_ok:
    print("✅ All checks passed - ready to deploy!")
else:
    print("❌ Some items need attention - check above.")