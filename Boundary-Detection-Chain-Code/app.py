"""Streamlit interface for the boundary detection and chain code project."""

from __future__ import annotations

import hashlib

import cv2
import numpy as np
import streamlit as st

from boundary_detection import detect_boundary, find_external_contours
from chain_code import direction_frequency, generate_chain_code, normalize_chain_code
from preprocessing import load_image, preprocess_image
from visualization import draw_boundary_overlay, plot_direction_frequencies, save_image_bytes


st.set_page_config(page_title="Boundary Detection and Chain Code", layout="wide")


def build_analysis(image: np.ndarray, threshold_value: int | None, use_blur: bool) -> dict:
    """Prepare an image and detect meaningful contours."""
    processed = preprocess_image(image, threshold_value=threshold_value, apply_blur=use_blur)
    contours = find_external_contours(processed["binary"])
    if not contours:
        raise ValueError("No object boundary was found. Try another image or adjust the threshold.")
    return {"processed": processed, "contours": contours}


def render_analysis_results(
    image: np.ndarray,
    processed: dict[str, np.ndarray],
    contours: list[np.ndarray],
    widget_key: str,
) -> None:
    """Render results from one ordered OpenCV contour and its matching chain code."""
    options = [
        f"Object {index + 1} · area {cv2.contourArea(contour):,.0f} px²"
        for index, contour in enumerate(contours)
    ]
    selected_label = st.selectbox("Primary object", options, key=f"object_{widget_key}")
    object_index = options.index(selected_label)
    try:
        boundary_info = detect_boundary(processed["binary"], object_index)
    except ValueError as exc:
        st.error(str(exc))
        return

    contour = boundary_info["selected_contour"]
    contour_points = [tuple(map(int, point)) for point in contour.reshape(-1, 2)]
    start_index = min(range(len(contour_points)), key=lambda index: (contour_points[index][1], contour_points[index][0]))
    traced_path = contour_points[start_index:] + contour_points[:start_index]
    start_point = traced_path[0]
    try:
        chain_code = generate_chain_code(traced_path)
    except ValueError as exc:
        st.error(f"The selected contour could not be traced continuously: {exc}")
        return

    normalized_chain = normalize_chain_code(chain_code)
    frequencies = direction_frequency(chain_code)
    chain_text = " ".join(str(code) for code in chain_code)
    height, width = image.shape[:2]

    st.markdown("#### Image review")
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Original Image")
        st.image(cv2.cvtColor(image, cv2.COLOR_BGR2RGB), width="stretch")
    with col2:
        st.subheader("Preprocessed Image")
        st.image(processed["binary"], channels="GRAY", width="stretch")

    boundary_overlay = draw_boundary_overlay(image, traced_path, start_point)
    st.subheader("Original + Detected Boundary + Starting Point")
    st.image(cv2.cvtColor(boundary_overlay, cv2.COLOR_BGR2RGB), width="stretch")

    st.markdown("#### Detection results")
    result_columns = st.columns(3)
    result_values = (
        ("Detection Status", "Successful"),
        ("Image Size", f"{width} × {height}"),
        ("Meaningful Contours", str(len(contours))),
        ("Contour Points", str(len(contour_points))),
        ("Boundary Points", str(len(traced_path))),
        ("Chain Code Length", str(len(chain_code))),
    )
    for index, (label, value) in enumerate(result_values):
        with result_columns[index % 3]:
            st.metric(label, value)
    st.metric("Starting Point (x, y)", f"({start_point[0]}, {start_point[1]})")

    st.markdown("#### Chain Code / Boundary Data")
    st.caption("Freeman 8-direction codes use the displayed contour, starting at its topmost-leftmost pixel.")
    st.code(chain_text or "No chain code generated", language="text")

    with st.expander(f"Boundary coordinates · {len(traced_path)} points"):
        st.dataframe(
            {
                "Point": list(range(1, len(traced_path) + 1)),
                "x": [point[0] for point in traced_path],
                "y": [point[1] for point in traced_path],
            },
            hide_index=True,
            width="stretch",
            height=300,
        )

    st.markdown("#### Downloads")
    boundary_bytes = save_image_bytes(boundary_overlay, ".png")
    report_lines = [
        "Boundary Detection and Freeman Chain Code Results",
        f"Detection Status: Successful",
        f"Image Size: {width} x {height}",
        f"Contour Points: {len(contour_points)}",
        f"Boundary Points: {len(traced_path)}",
        f"Chain Code Length: {len(chain_code)}",
        f"Starting Point: ({start_point[0]}, {start_point[1]})",
        "Chain Code:",
        chain_text,
        "Boundary Coordinates (x, y):",
        *(f"{x}, {y}" for x, y in traced_path),
    ]
    download_columns = st.columns(3)
    with download_columns[0]:
        st.download_button(
            "Download Result",
            data="\n".join(report_lines),
            file_name="boundary_detection_result.txt",
            mime="text/plain",
            key=f"result_{widget_key}",
            width="stretch",
        )
    with download_columns[1]:
        st.download_button(
            "Download Chain Code",
            data=chain_text,
            file_name="chain_code.txt",
            mime="text/plain",
            key=f"chain_{widget_key}",
            width="stretch",
        )
    with download_columns[2]:
        st.download_button(
            "Download Boundary Image",
            data=boundary_bytes,
            file_name="boundary_output.png",
            mime="image/png",
            key=f"image_{widget_key}",
            use_container_width=True,
        )

    with st.expander("Direction analysis"):
        normalized_text = " ".join(str(code) for code in normalized_chain)
        st.caption("First-difference normalized chain code")
        st.code(normalized_text or "No normalized code generated", language="text")
        st.write({f"Direction {direction}": frequencies.get(direction, 0) for direction in range(8)})
        st.pyplot(plot_direction_frequencies(frequencies), clear_figure=True)


def render_analysis(image: np.ndarray, threshold_value: int | None, use_blur: bool) -> None:
    """Run and display the same boundary analysis for a live camera frame."""
    try:
        analysis = build_analysis(image, threshold_value, use_blur)
    except (ValueError, cv2.error) as exc:
        st.error(str(exc))
        return
    render_analysis_results(image, analysis["processed"], analysis["contours"], "camera")


@st.fragment(run_every=0.5)
def render_live_camera(threshold_value: int, use_blur: bool) -> None:
    """Refresh camera frames and analyze each frame without blocking the app."""
    capture = st.session_state.get("camera_capture")
    if capture is None or not st.session_state.get("camera_active", False):
        st.info("Select Start camera to begin live boundary detection.")
        return

    success, image = capture.read()
    if not success:
        st.error("OpenCV could not read a frame from the camera.")
        return

    st.subheader("Live Camera")
    st.image(cv2.cvtColor(image, cv2.COLOR_BGR2RGB), channels="RGB")
    render_analysis(image, threshold_value, use_blur)


def release_camera() -> None:
    """Release the active OpenCV camera, if any."""
    capture = st.session_state.get("camera_capture")
    if capture is not None:
        capture.release()
    st.session_state.camera_capture = None
    st.session_state.camera_active = False


def render_page() -> None:
    """Render the complete Streamlit dashboard."""
    st.markdown(
        """<style>
        .stApp { background: #f4f6f6; color: #18313a; }
        .block-container { max-width: 1320px; padding: 2rem 2.4rem 3rem; }
        h1, h2, h3 { color: #18313a; }
        [data-testid="stMetric"] { background: #ffffff; border: 1px solid #d9e1e2; padding: 0.8rem 1rem; border-radius: 6px; }
        .stButton > button, .stDownloadButton > button { min-height: 2.65rem; border-radius: 5px; border: 1px solid #b9c9cb; font-weight: 600; }
        .stButton > button[kind="primary"] { background: #176b68; border-color: #176b68; }
        @media (max-width: 760px) { .block-container { padding: 1.25rem 1rem 2rem; } }
        </style>""",
        unsafe_allow_html=True,
    )
    st.title("Boundary Detection & Chain Code")
    st.caption("Computer Vision Project · Freeman 8-direction boundary representation")

    if "camera_capture" not in st.session_state:
        st.session_state.camera_capture = None
        st.session_state.camera_active = False
    if "uploader_generation" not in st.session_state:
        st.session_state.uploader_generation = 0

    source = st.radio("Image source", ["Upload Image", "Live Camera"], horizontal=True)
    option_columns = st.columns(2)
    with option_columns[0]:
        automatic_threshold = st.checkbox("Automatic threshold (Otsu)", value=True)
    with option_columns[1]:
        use_blur = st.checkbox("Reduce image noise", value=True)
    threshold_value = None
    if not automatic_threshold:
        threshold_value = st.slider("Manual threshold", min_value=0, max_value=255, value=127, step=1)

    if source == "Live Camera":
        camera_index = st.number_input("Camera index", min_value=0, value=0, step=1)
        start_col, stop_col = st.columns(2)
        with start_col:
            if st.button("Start camera", type="primary"):
                release_camera()
                capture = cv2.VideoCapture(int(camera_index))
                capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                if capture.isOpened():
                    st.session_state.camera_capture = capture
                    st.session_state.camera_active = True
                else:
                    capture.release()
                    st.error(f"Could not open camera {int(camera_index)}. Check that it is connected and not in use by another application.")
        with stop_col:
            if st.button("Stop camera"):
                release_camera()

        st.caption("OpenCV uses a camera connected to the computer running this Streamlit app.")
        render_live_camera(threshold_value, use_blur)
        return

    if st.session_state.get("camera_active", False):
        release_camera()

    st.markdown("#### Image upload")
    uploader_key = f"uploaded_image_{st.session_state.uploader_generation}"
    uploaded_file = st.file_uploader(
        "Choose a PNG or JPEG image",
        type=["png", "jpg", "jpeg"],
        key=uploader_key,
    )
    if uploaded_file is None:
        st.info("Upload an image to preview it and start boundary detection.")
        return

    try:
        uploaded_file.seek(0)
        image = load_image(uploaded_file=uploaded_file)
    except (ValueError, cv2.error) as exc:
        st.error(f"This image could not be opened. Choose a valid PNG or JPEG file. Details: {exc}")
        return

    image_id = hashlib.sha256(uploaded_file.getvalue()).hexdigest()
    analysis = st.session_state.get("upload_analysis")
    settings = (threshold_value, use_blur)
    if analysis and (analysis["image_id"] != image_id or analysis["settings"] != settings):
        st.session_state.pop("upload_analysis", None)
        analysis = None

    st.subheader("Original Image")
    st.image(cv2.cvtColor(image, cv2.COLOR_BGR2RGB), width="stretch")
    action_columns = st.columns([1, 1, 4])
    with action_columns[0]:
        detect_clicked = st.button("Detect Boundary", type="primary", width="stretch")
    with action_columns[1]:
        reset_clicked = st.button("Reset", width="stretch")

    if reset_clicked:
        st.session_state.pop("upload_analysis", None)
        st.session_state.uploader_generation += 1
        st.rerun()

    if detect_clicked:
        st.session_state.pop("upload_analysis", None)
        try:
            with st.spinner("Preprocessing image and tracing contours…"):
                result = build_analysis(image, threshold_value, use_blur)
            st.session_state.upload_analysis = {
                "image_id": image_id,
                "settings": settings,
                "image": image,
                **result,
            }
        except (ValueError, cv2.error) as exc:
            st.error(f"Boundary detection failed. Try another threshold or a clearer image. Details: {exc}")

    analysis = st.session_state.get("upload_analysis")
    if analysis and analysis["image_id"] == image_id and analysis["settings"] == settings:
        st.divider()
        render_analysis_results(
            analysis["image"],
            analysis["processed"],
            analysis["contours"],
            image_id[:12],
        )


if __name__ == "__main__":
    render_page()
