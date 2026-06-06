# patch_export.py
# Run after every Godot web export: python patch_export.py

import os
import sys
import re

HTML_FILE = "index.html"

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

# This goes in its OWN <script> tag BEFORE index.js loads
JS_EARLY = """<script>
	/* MONITOR OVERLAY - must be defined before Godot starts */
	globalThis.updateMonitorOverlay = function (normX, normY, hAngle, vAngle, scaleFactor) {
		var frame = document.getElementById('monitor-frame');
		if (!frame) { console.error('monitor-frame not found'); return; }
		if (normX < 0) {
			frame.style.display = 'none';
			return;
		}
		frame.style.display = 'block';
		var canvas = document.getElementById('canvas');
		var cw = canvas ? canvas.clientWidth  : window.innerWidth;
		var ch = canvas ? canvas.clientHeight : window.innerHeight;
		var anchorX = normX * cw;
		var anchorY = normY * ch;
		var left = anchorX - 210;
		var top  = anchorY - 350;
		var ry = Math.max(-45, Math.min(45, -hAngle));
		var rx = Math.max(-30, Math.min(30,  vAngle));
		frame.style.left = left + 'px';
		frame.style.top  = top  + 'px';
		frame.style.transform = 'perspective(1200px) rotateY(' + ry + 'deg) rotateX(' + rx + 'deg) scale(' + scaleFactor + ')';
	};
</script>
"""

def check_file():
    if not os.path.exists(HTML_FILE):
        print("ERROR: " + HTML_FILE + " not found in this folder.")
        print("Make sure patch_export.py is in the same folder as index.html")
        sys.exit(1)
    print("Found: " + HTML_FILE)

def read_file():
    with open(HTML_FILE, "r", encoding="utf-8") as f:
        return f.read()

def write_file(content):
    with open(HTML_FILE, "w", encoding="utf-8") as f:
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

def remove_old_js(html):
    """Remove any old inline updateMonitorOverlay from inside a <script> block"""
    if "updateMonitorOverlay" not in html:
        return html, False

    # If it's already in its own early <script> block before index.js, leave it
    early_marker = "<script>\n\t/* MONITOR OVERLAY"
    if early_marker in html:
        return html, True  # already in correct position

    # Find and remove the old function from wherever it is inside a script block
    pattern = r'\s*/\*[^*]*MONITOR OVERLAY[^*]*\*/\s*window\.updateMonitorOverlay\s*=\s*function\s*\([^)]*\)\s*\{[^}]*(?:\{[^}]*\}[^}]*)*\};\s*'
    cleaned = re.sub(pattern, '\n', html, flags=re.DOTALL)
    if cleaned != html:
        print("   JS: removed old inline version")
        return cleaned, False
    return html, False

def inject_js_early(html):
    if "updateMonitorOverlay" in html:
        # Check if it's already in the right place (before index.js src tag)
        js_pos = html.find("updateMonitorOverlay")
        # Find the index.js script tag
        index_js_patterns = [
            '<script src="index.js">',
            "<script src='index.js'>",
            '<script src="anselmo.blog.js">',
            "<script src='anselmo.blog.js'>",
        ]
        for pattern in index_js_patterns:
            src_pos = html.find(pattern)
            if src_pos != -1:
                if js_pos < src_pos:
                    print("   JS: already in correct position (before index.js), skipping")
                    return html
                else:
                    print("   JS: found but in wrong position, will re-inject")
                    # Remove old version first
                    html, _ = remove_old_js(html)
                    break

    # Find the index.js (or game js) script src tag to inject before it
    index_js_patterns = [
        '<script src="index.js">',
        "<script src='index.js'>",
        '<script src="anselmo.blog.js">',
        "<script src='anselmo.blog.js'>",
    ]
    for pattern in index_js_patterns:
        if pattern in html:
            html = html.replace(pattern, JS_EARLY + "\n\t\t" + pattern, 1)
            print("   JS: injected OK (own script tag before " + pattern + ")")
            return html

    # Fallback: inject before first <script src=
    match = re.search(r'<script\s+src=', html, re.IGNORECASE)
    if match:
        html = html[:match.start()] + JS_EARLY + "\n\t\t" + html[match.start():]
        print("   JS: injected OK (before first script src, fallback)")
        return html

    print("   JS: ERROR - could not find injection point")
    return html

def verify(html):
    print("\nVerifying...")
    checks = [
        ("monitor-overlay CSS",         "#monitor-overlay"        ),
        ("monitor-frame CSS",           "#monitor-frame"          ),
        ("monitor-overlay DIV",         'id="monitor-overlay"'    ),
        ("monitor-frame DIV",           'id="monitor-frame"'      ),
        ("monitor-iframe DIV",          'id="monitor-iframe"'     ),
        ("JS function exists",          "updateMonitorOverlay"    ),
    ]
    all_ok = True
    for name, token in checks:
        if token in html:
            print("  OK      " + name)
        else:
            print("  MISSING " + name)
            all_ok = False

    # Extra check: verify JS comes before index.js
    js_pos = html.find("updateMonitorOverlay")
    for pattern in ['<script src="index.js">', '<script src="anselmo.blog.js">']:
        src_pos = html.find(pattern)
        if src_pos != -1:
            if js_pos < src_pos:
                print("  OK      JS is before index.js (correct load order)")
            else:
                print("  WARNING JS is AFTER index.js - Godot may call it before it exists!")
                all_ok = False
            break

    return all_ok

print("=== patch_export.py ===\n")
check_file()
print("\nInjecting...")

html = read_file()
html = inject_css(html)
html = inject_div(html)
html = inject_js_early(html)
write_file(html)

ok = verify(html)

if ok:
    print("\n✅ All checks passed - index.html is ready!")
else:
    print("\n❌ Some items missing or in wrong order - check above.")