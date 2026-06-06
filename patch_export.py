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

JS = """	/* -------------------------
	   MONITOR OVERLAY SYSTEM
	-------------------------- */
	window.updateMonitorOverlay = function (normX, normY, hAngle, vAngle, scaleFactor) {
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
		var FRAME_W = 420;
		var FRAME_H = 700;
		var left = anchorX - FRAME_W / 2;
		var top  = anchorY - FRAME_H / 2;
		var MAX_Y = 45; var MAX_X = 30;
		var ry = Math.max(-MAX_Y, Math.min(MAX_Y, -hAngle));
		var rx = Math.max(-MAX_X, Math.min(MAX_X,  vAngle));
		frame.style.left = left + 'px';
		frame.style.top  = top  + 'px';
		frame.style.transform = 'perspective(1200px) rotateY(' + ry + 'deg) rotateX(' + rx + 'deg) scale(' + scaleFactor + ')';
	};
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

    # Try every likely variation of the canvas tag
    candidates = [
        '<canvas id="canvas">',
        "<canvas id='canvas'>",
        '<canvas id="canvas" ',
        '<canvas id=canvas>',
    ]
    for candidate in candidates:
        if candidate in html:
            html = html.replace(candidate, HTML_DIV + "\n\t\t" + candidate, 1)
            print("  DIV: injected OK (matched: " + candidate + ")")
            return html

    # Fallback: find <canvas using regex
    match = re.search(r'<canvas\b[^>]*>', html, re.IGNORECASE)
    if match:
        canvas_tag = match.group(0)
        html = html.replace(canvas_tag, HTML_DIV + "\n\t\t" + canvas_tag, 1)
        print("  DIV: injected OK (regex match: " + canvas_tag + ")")
        return html

    # Last resort: inject after <body>
    if "<body>" in html:
        html = html.replace("<body>", "<body>\n" + HTML_DIV, 1)
        print("  DIV: injected OK (fallback: after <body>)")
        return html

    print("  DIV: ERROR - could not find any injection point")
    return html

def inject_js(html):
    if "updateMonitorOverlay" in html:
        print("   JS: already present, skipping")
        return html

    idx = html.find("const GODOT_CONFIG")
    if idx == -1:
        print("   JS: ERROR - could not find GODOT_CONFIG anchor")
        return html

    script_idx = html.rfind("<script>", 0, idx)
    if script_idx == -1:
        print("   JS: ERROR - could not find opening <script> tag")
        return html

    insert_at = script_idx + len("<script>")
    html = html[:insert_at] + "\n" + JS + "\n" + html[insert_at:]
    print("   JS: injected OK")
    return html

def verify(html):
    print("\nVerifying...")
    checks = [
        ("monitor-overlay CSS",  "#monitor-overlay"        ),
        ("monitor-frame CSS",    "#monitor-frame"          ),
        ("monitor-overlay DIV",  'id="monitor-overlay"'    ),
        ("monitor-frame DIV",    'id="monitor-frame"'      ),
        ("monitor-iframe DIV",   'id="monitor-iframe"'     ),
        ("JS function",          "updateMonitorOverlay"    ),
    ]
    all_ok = True
    for name, token in checks:
        if token in html:
            print("  OK      " + name)
        else:
            print("  MISSING " + name)
            all_ok = False
    return all_ok

print("=== patch_export.py ===\n")
check_file()
print("\nInjecting...")

html = read_file()
html = inject_css(html)
html = inject_div(html)
html = inject_js(html)
write_file(html)

ok = verify(html)

if ok:
    print("\n✅ All checks passed - index.html is ready!")
else:
    print("\n❌ Some items are missing - check the errors above.")