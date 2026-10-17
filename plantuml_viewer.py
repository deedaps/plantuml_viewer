#!/usr/bin/env python3
"""
PlantUML Viewer – Desktop GUI with pywebview & optional browser mode.
"""
import argparse
import threading
import zlib
import sys
import os
import webbrowser

try:
    from flask import Flask, request, jsonify, render_template_string
except ImportError:
    print("Error: Flask is not installed. Install it with: pip install flask", file=sys.stderr)
    sys.exit(1)

# ----------------------------------------------------------------------
# PlantUML encoding (deflate + custom base64)
# ----------------------------------------------------------------------
def encode_plantuml(text: str) -> str:
    """
    Encode PlantUML source text to the compressed format expected by
    the public server (https://www.plantuml.com/plantuml/svg/...).
    """
    # PlantUML expects raw DEFLATE bytes (no zlib header/checksum),
    # then a custom 64-character encoding.
    compressed = zlib.compress(text.encode("utf-8"))[2:-4]

    def encode6bit(b: int) -> str:
        if b < 10:
            return chr(48 + b)
        b -= 10
        if b < 26:
            return chr(65 + b)
        b -= 26
        if b < 26:
            return chr(97 + b)
        b -= 26
        if b == 0:
            return "-"
        return "_"

    def append3bytes(b1: int, b2: int, b3: int) -> str:
        c1 = b1 >> 2
        c2 = ((b1 & 0x3) << 4) | (b2 >> 4)
        c3 = ((b2 & 0xF) << 2) | (b3 >> 6)
        c4 = b3 & 0x3F
        return encode6bit(c1 & 0x3F) + encode6bit(c2 & 0x3F) + encode6bit(c3 & 0x3F) + encode6bit(c4 & 0x3F)

    out = []
    i = 0
    while i < len(compressed):
        b1 = compressed[i]
        b2 = compressed[i + 1] if i + 1 < len(compressed) else 0
        b3 = compressed[i + 2] if i + 2 < len(compressed) else 0
        out.append(append3bytes(b1, b2, b3))
        i += 3

    return "".join(out)


# ----------------------------------------------------------------------
# Flask application (shared backend)
# ----------------------------------------------------------------------
app = Flask(__name__)

# Global variable to store the initial file content
INITIAL_SOURCE = ""


HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>PlantUML Viewer</title>
    <style>
        body { font-family: sans-serif; margin: 0; display: flex; height: 100vh; }
        #editor { width: 40%; padding: 10px; box-sizing: border-box; display: flex; flex-direction: column; }
        #preview { width: 60%; padding: 10px; overflow: auto; background: #f5f5f5; }
        body.editor-hidden #editor { display: none; }
        body.editor-hidden #preview { width: 100%; }
        textarea { flex: 1; font-family: monospace; font-size: 14px; }
        .controls { margin-top: 10px; display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
        button { padding: 8px 16px; }
        .control-group { display: flex; align-items: center; gap: 6px; }
        .control-group input[type="range"] { width: 140px; }
        #diagramViewport { overflow: auto; }
        #diagramCanvas { display: inline-block; transform-origin: top left; }
        img { display: block; max-width: none; }
    </style>
</head>
<body>
    <div id="editor">
        <textarea id="source" placeholder="Enter PlantUML code...">{{ initial_source }}</textarea>
        <div class="controls">
            <button onclick="renderDiagram()">Render</button>
            <button id="togglePaneBtn" onclick="toggleSourcePane()">Hide Source</button>
        </div>
    </div>
    <div id="preview">
        <div class="controls">
            <button id="togglePaneBtnPreview" onclick="toggleSourcePane()" style="display:none;">Show Source</button>
            <div class="control-group">
                <label for="viewerZoom">Zoom</label>
                <input id="viewerZoom" type="range" min="0.5" max="3" step="0.1" value="1" oninput="applyViewerZoom()">
                <span id="viewerZoomValue">100%</span>
            </div>
            <div class="control-group">
                <label for="serverScale">Server Scale</label>
                <input id="serverScale" type="range" min="0.5" max="3" step="0.1" value="1" oninput="applyServerScale()">
                <span id="serverScaleValue">1.0x</span>
            </div>
        </div>
        <div id="diagramViewport">
            <div id="diagramCanvas">
                <img id="diagram" src="" alt="Rendered diagram will appear here">
            </div>
        </div>
    </div>

    <script>
        let lastEncoded = '';

        function getServerScale() {
            return parseFloat(document.getElementById('serverScale').value);
        }

        function updateDiagramUrl() {
            if (!lastEncoded) {
                return;
            }
            const scale = getServerScale();
            const img = document.getElementById('diagram');
            img.src = 'https://www.plantuml.com/plantuml/svg/' + lastEncoded + '?scale=' + encodeURIComponent(scale.toFixed(1));
        }

        function syncDiagramCanvasSize() {
            const img = document.getElementById('diagram');
            const canvas = document.getElementById('diagramCanvas');
            const zoom = parseFloat(document.getElementById('viewerZoom').value);
            if (img.naturalWidth && img.naturalHeight) {
                canvas.style.width = (img.naturalWidth * zoom) + 'px';
                canvas.style.height = (img.naturalHeight * zoom) + 'px';
            }
        }

        function renderDiagram() {
            const source = document.getElementById('source').value;
            fetch('/render', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({source: source})
            })
            .then(res => res.json())
            .then(data => {
                lastEncoded = data.encoded;
                updateDiagramUrl();
            })
            .catch(err => console.error(err));
        }

        function applyViewerZoom() {
            const zoom = parseFloat(document.getElementById('viewerZoom').value);
            const zoomValue = document.getElementById('viewerZoomValue');
            const canvas = document.getElementById('diagramCanvas');
            zoomValue.textContent = Math.round(zoom * 100) + '%';
            canvas.style.transform = 'scale(' + zoom + ')';
            syncDiagramCanvasSize();
        }

        function applyServerScale() {
            const scale = getServerScale();
            document.getElementById('serverScaleValue').textContent = scale.toFixed(1) + 'x';
            updateDiagramUrl();
        }

        function toggleSourcePane() {
            const body = document.body;
            const isHidden = body.classList.toggle('editor-hidden');
            const toggleBtn = document.getElementById('togglePaneBtn');
            const previewToggleBtn = document.getElementById('togglePaneBtnPreview');

            toggleBtn.textContent = isHidden ? 'Show Source' : 'Hide Source';
            previewToggleBtn.style.display = isHidden ? 'inline-block' : 'none';
        }

        // Auto-render on page load if there is initial content
        window.addEventListener('DOMContentLoaded', () => {
            const img = document.getElementById('diagram');
            img.addEventListener('load', syncDiagramCanvasSize);
            applyViewerZoom();
            applyServerScale();

            if (document.getElementById('source').value.trim() !== '') {
                renderDiagram();
            }
        });
    </script>
</body>
</html>
"""


@app.route("/")
def index():
    """Serve the main page with the initial PlantUML source."""
    return render_template_string(HTML_TEMPLATE, initial_source=INITIAL_SOURCE)


@app.route("/render", methods=["POST"])
def render():
    """Receive PlantUML source, return encoded string for the server URL."""
    data = request.get_json()
    if not data or "source" not in data:
        return jsonify({"error": "Missing 'source' in request"}), 400
    try:
        encoded = encode_plantuml(data["source"])
        return jsonify({"encoded": encoded})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ----------------------------------------------------------------------
# Main entry point
# ----------------------------------------------------------------------
def find_free_port():
    """Find an available port on localhost."""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


def start_flask(port):
    """Run Flask server in a background thread."""
    app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)


def main():
    parser = argparse.ArgumentParser(description="PlantUML Viewer")
    parser.add_argument(
        "file",
        nargs="?",
        help="Path to a PlantUML (.puml) file to view",
    )
    parser.add_argument(
        "--web",
        action="store_true",
        help="Run as a web server only (no desktop window)",
    )
    args = parser.parse_args()

    # Load initial source from file if provided
    global INITIAL_SOURCE
    if args.file:
        if not os.path.isfile(args.file):
            print(f"Error: file not found: {args.file}", file=sys.stderr)
            sys.exit(1)
        with open(args.file, "r", encoding="utf-8") as f:
            INITIAL_SOURCE = f.read()
    else:
        # If no file given, start with empty source
        INITIAL_SOURCE = ""

    # Find a free port for the Flask server
    port = find_free_port()

    # Start Flask in a daemon thread
    flask_thread = threading.Thread(target=start_flask, args=(port,), daemon=True)
    flask_thread.start()

    if args.web:
        # Browser mode: just print the URL
        print(f"PlantUML Viewer running at http://127.0.0.1:{port}")
        print("Press Ctrl+C to stop.")
        try:
            # Keep the main thread alive
            while True:
                input()
        except KeyboardInterrupt:
            print("\nShutting down.")
            sys.exit(0)
    else:
        # Desktop mode: open pywebview window
        import webview
        from webview.errors import WebViewException

        viewer_url = f"http://127.0.0.1:{port}"
        try:
            window = webview.create_window(
                "PlantUML Viewer",
                viewer_url,
                width=1200,
                height=700,
            )
            # Force Qt backend to avoid requiring GTK (gi) on Linux.
            webview.start(gui="qt")
            # After the window is closed, the Flask thread will end when the process exits
            sys.exit(0)
        except WebViewException as exc:
            print("Desktop GUI backend is unavailable.", file=sys.stderr)
            print("Install dependencies from requirements.txt and retry:", file=sys.stderr)
            print("  pip install -r requirements.txt", file=sys.stderr)
            print(f"pywebview error: {exc}", file=sys.stderr)
            print(f"Falling back to browser mode at {viewer_url}", file=sys.stderr)
            webbrowser.open(viewer_url)
            print("Press Ctrl+C to stop.")
            try:
                while True:
                    input()
            except KeyboardInterrupt:
                print("\nShutting down.")
                sys.exit(0)


if __name__ == "__main__":
    main()