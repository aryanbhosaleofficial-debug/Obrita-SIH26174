# ORBITA GUI (SIH26174)

Offline PySide6 console for the BAS experiment monitor. One codebase, two uses:

1. **Standalone demo** – runs with built-in *sample* data, no pipeline modules.
2. **Embeddable module** – `ConsoleWidget` + `PipelineBridge` that your pipeline feeds.

Demo build, not flight software. All numbers in the demo (confidences, times, log lines,
step names) are placeholders. Accuracy, FPS and per-module timing are **not measured**.

## Run
```
pip install -r requirements.txt
python run_demo.py                                   # window with sample data
python run_demo.py --trial wrong --rotation 90       # start in a given state
QT_QPA_PLATFORM=offscreen python tests/test_smoke.py # layout + bridge checks, no display needed
python examples/embed_example.py                     # module fed from a worker thread (needs numpy)
```
Fonts (Overpass, Overpass Mono, SIL OFL) are bundled in `assets/fonts`; nothing is fetched online.
If they fail to load, a message is printed and system fonts are used.

## Layout of the package
| File | Role |
|---|---|
| `state.py` | `Snapshot` and friends: the only data the GUI draws (no Qt, thread-safe to build) |
| `console.py` | `ConsoleWidget`: whole screen, embed anywhere |
| `main_window.py` | `OrbitaWindow`, `make_app()` (loads fonts + stylesheet) |
| `bridge.py` | `PipelineBridge`: `push_snapshot()` / `push_frame()` from any thread |
| `adapters.py` | dict → `Snapshot`, OpenCV BGR → `QImage`. The only file that knows pipeline shapes |
| `mock.py` | sample data + `MockProvider` for the demo |
| `widgets/` | camera (16:9, painted), procedure list, tables, status bar, header |

## Embedding in the pipeline
```python
from orbita_gui.main_window import make_app
from orbita_gui import ConsoleWidget, PipelineBridge

app = make_app()
console = ConsoleWidget(show_demo_controls=False)   # hide demo-only Trial / Rotation buttons
console.show()
bridge = PipelineBridge(); bridge.attach(console)
bridge.voice_toggled.connect(my_pipeline.set_voice)  # GUI -> pipeline

# in the pipeline thread, every frame / every FSM change:
bridge.push_frame(bgr_frame)                          # ndarray from OpenCV
bridge.push_snapshot(snapshot_or_dict)                # see dict keys below
```
Run the Qt event loop in the main thread and the pipeline in a worker thread. Only the
newest frame is kept, so a slow GUI never slows capture.

### Snapshot dict contract
Missing keys fall back to defaults. Keys: `status_level` (nominal|caution|warning), `status_text`,
`spoken`, `met_seconds`, `stamp`, `steps` [{id,text,state(done|active|pending|skipped|wrong),time}],
`next_step` {number,head,text,note,progress 0..1,progress_label}, `readings` [{name,x,y,aspect,conf}],
`chain` [{stage,module,note,status}], `alerts` [{t,level,text}], `log` [{t,level,event,detail,conf}] (oldest first),
`log_path`, `scene` {simulated,rotation,main_box,objects,hands}, `recording`, `lan_streaming`,
`local_only`, `voice_on`, `footer`.
Detections use normalised frame coordinates (`cx, cy, w, h` in 0..1). Set `scene.simulated=False`
when you push real frames so the demo scene is not drawn.

**Assumption:** the real `core/contracts.py` status object was not available when this was
written, so the mapping is the dict above. Adapt `snapshot_from_dict` to your dataclass if needed.

## Design rules kept in code
- Voice alerts come from the FSM only; the GUI just shows what was spoken.
- Readings are rack-relative; "Camera up not used" is shown in the HUD (microgravity framing).
- Colour is used only for caution/warning plus one blue accent.
- Painted tables/rows have fixed heights, the camera is always 16:9, the footer is last in the scroll area.
