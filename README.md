# PlantUML Viewer

A lightweight desktop application for writing and previewing [PlantUML](https://plantuml.com/) diagrams. It runs a small local Flask server and displays the editor/preview UI either in a native desktop window (via `pywebview`) or in your browser.

Diagram rendering is delegated to the public PlantUML server (`https://www.plantuml.com/plantuml/svg/...`), so an internet connection is required.

## Features

- Split view with a PlantUML source editor and live diagram preview
- Render button to update the diagram
- Show/hide the source pane for a full-width preview
- Viewer zoom (0.5x–3x) applied client-side
- Server scale (0.5x–3x) passed to the PlantUML server for sharper output
- Open a `.puml` file directly on startup
- Browser-only mode for environments without a desktop GUI backend

## Requirements

- Python 3.8+
- Dependencies listed in `requirements.txt`:
  - `flask`
  - `requests`
  - `PyQt5`
  - `PyQtWebEngine`
  - `qtpy`
  - `pywebview`

## Installation

```bash
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Usage

Start with an empty editor:

```bash
python plantuml_viewer.py
```

Open a specific PlantUML file:

```bash
python plantuml_viewer.py diagram.puml
```

Run in browser mode (no desktop window):

```bash
python plantuml_viewer.py --web
```

The app picks a free port on `127.0.0.1` automatically and prints the URL. Press `Ctrl+C` in the terminal to stop it.

If the desktop GUI backend fails to initialize, the app automatically falls back to opening the viewer in your default browser.

## How It Works

`plantuml_viewer.py` starts a Flask app in a background thread and then opens the UI in a `pywebview` window (using the Qt backend) or the browser. When you click **Render**, the source is sent to the local `/render` endpoint, encoded with PlantUML's DEFLATE + custom base64 scheme, and the resulting string is used to load the SVG from the public PlantUML server.

## Notes

- No PlantUML installation is needed locally.
- Diagram content is sent to the public PlantUML server for rendering; avoid using it for confidential diagrams.
- The `venv/` directory is ignored by Git.

## License

No license file is included in this repository.
