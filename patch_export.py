# patch_export.py
# Run this after every Godot web export: python patch_export.py

import re

HTML_FILE = "index.html"

CSS_TO_ADD = """
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

HTML_TO_ADD = """
	<div id="monitor-overlay">
		<div id="monitor-frame">
			<iframe id="monitor-iframe" src="https://anselmo.blog" scrolling="no" frameborder="0"></iframe>
		</div>
	</div>
"""

JS_TO_ADD = """
/* -------------------------
   MONITOR OVERLAY SYSTEM
-------------------------- */
(function () {
	const frame = document.getElementById('monitor-frame');

	const FRAME_W = 420;
	const FRAME_H = 700;
	const MAX_ROTATE_Y = 45;
	const MAX_ROTATE_X = 30;

	window.updateMonitorOverlay = function (normX, normY, hAngle, vAngle, scaleFactor) {
		if (normX < 0) {
			frame.style.display = 'none';
			return;
		}
		frame.style.display = 'block';

		const canvas = document.getElementById('canvas');
		const cw = canvas ? canvas.clientWidth  : window.innerWidth;
		const ch = canvas ? canvas.clientHeight : window.innerHeight;

		const anchorX = normX * cw;
		const anchorY = normY * ch;

		const left = anchorX - FRAME_W / 2;
		const top  = anchorY - FRAME_H / 2;

		const ry = Math.max(-MAX_ROTATE_Y, Math.min(MAX_ROTATE_Y, -hAngle));
		const rx = Math.max(-MAX_ROTATE_X, Math.min(MAX_ROTATE_X,  vAngle));

		frame.style.left = left + 'px';
		frame.style.top  = top  + 'px';
		frame.style.transform = [
			'perspective(1200px)',
			'rotateY(' + ry + 'deg)',
			'rotateX(' + rx + 'deg)',
			'scale(' + scaleFactor + ')'
		].join(' ');
	};
}());

"""

with open(HTML_FILE, "r", encoding="utf-8") as f:
    html = f.read()

# 1. Inject CSS before closing </style>
if "MONITOR OVERLAY" not in html:
    html = html.replace("</style>", CSS_TO_ADD + "\n\t\t</style>", 1)
    print("✓ CSS injected")
else:
    print("⚠ CSS already present, skipping")

# 2. Inject HTML div after <body>
if "monitor-overlay" not in html:
    html = html.replace("<canvas id=\"canvas\">", HTML_TO_ADD + "\n\t\t<canvas id=\"canvas\">", 1)
    print("✓ HTML div injected")
else:
    print("⚠ HTML div already present, skipping")

# 3. Inject JS before the Godot loader
if "updateMonitorOverlay" not in html:
    html = html.replace("const GODOT_CONFIG", JS_TO_ADD + "const GODOT_CONFIG", 1)
    print("✓ JavaScript injected")
else:
    print("⚠ JavaScript already present, skipping")

with open(HTML_FILE, "w", encoding="utf-8") as f:
    f.write(html)

print("\n✅ Done! index.html patched successfully.")