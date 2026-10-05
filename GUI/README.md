# SIH26174 Prototype GUI

Standalone offline desktop GUI for the SIH26174 AI Human Activity Recognition project.

## Requirements
- Python 3
- PySide6

## Run steps for Windows

```cmd
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

## Shortcuts
- `1`, `2`, `3`: Switch trial simulation.
- `R`: Cycle camera setup rotation.
- `M`: Toggle voice mute.

*This GUI uses a mock data provider and runs completely offline. No CDNs, web fonts, or live camera models are connected in this module.*
