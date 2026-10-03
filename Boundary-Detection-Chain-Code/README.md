# Boundary Detection Using Chain Codes

## Introduction
This project is a beginner-friendly academic Digital Image Processing application built with Python, OpenCV, NumPy, Matplotlib, and Streamlit. It demonstrates how the boundary of an object in an image can be detected, traced, and converted into an 8-direction Freeman chain code.

The goal is to show a simple but clear image-processing workflow:

Image Input -> Grayscale -> Thresholding -> Boundary Detection -> Boundary Tracing -> Chain Code -> Visualization

## Problem Statement
Boundary representation is important in digital image processing because it helps describe the shape of objects. Instead of storing the entire image, we can store only the outline of the object. This representation is useful in shape analysis, object recognition, pattern detection, and computer vision tasks.

## Objectives
- Learn how to read and preprocess an image.
- Convert an image to grayscale and binary form.
- Detect the external boundary of an object.
- Trace the boundary manually using an 8-connected neighborhood.
- Generate an 8-direction Freeman chain code.
- Explain the idea of normalization and first-difference chain codes.
- Build a simple Streamlit interface for visualization.

## Technologies Used
- Python 3
- OpenCV
- NumPy
- Matplotlib
- Streamlit
- Pillow

## Methodology
1. Upload an image.
2. Convert to grayscale.
3. Apply thresholding.
4. Detect the object boundary.
5. Select the target object if multiple objects are present.
6. Trace the boundary manually.
7. Generate the chain code.
8. Normalize the chain code.
9. Display statistics and charts.
10. Show the results in a Streamlit UI.

## Algorithm
The project follows a simple manual boundary tracing approach:

1. Read the input image.
2. Convert it to grayscale.
3. Convert to binary using thresholding.
4. Detect the external contour using OpenCV.
5. Choose the largest contour or a selected object.
6. Find a starting boundary pixel.
7. Examine the 8 neighboring pixels around the current pixel.
8. Move to the next boundary pixel if it is valid.
9. Store the direction code from one pixel to the next.
10. Continue until the path returns to the start or reaches a safe loop limit.
11. Generate the chain code list and display it.

## Chain Code Direction Table
The 8-direction Freeman chain code uses the following directions:

- 0 = Right
- 1 = Bottom-Right
- 2 = Down
- 3 = Bottom-Left
- 4 = Left
- 5 = Top-Left
- 6 = Up
- 7 = Top-Right

## Installation
### 1. Create a virtual environment
```bash
python -m venv venv
```

### Windows activation
```bash
venv\Scripts\activate
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Run the project
```bash
streamlit run app.py
```

## Example
Consider a simple square. The boundary can be traced by moving along its edges. The sequence of directions forms a chain code such as:

```python
[0, 0, 2, 2, 4, 4, 6, 6]
```

This indicates a path moving right, right, down, down, left, left, up, up.

## Limitations
- Chain codes depend on the starting point.
- A simple first-difference code is not fully invariant to rotation.
- Boundary tracing can fail for noisy or disconnected objects.
- The technique is more suited to simple shape descriptions than complex natural scenes.

## Future Scope
Potential improvements include:
- Shape recognition systems
- Rotation normalization
- Scale normalization
- Multiple-object shape analysis
- Database of shape signatures
- Deployment as a web application

## Viva Questions and Answers
### Q1. What is boundary detection?
Boundary detection is the process of finding the outline of an object in an image.

### Q2. What is a chain code?
A chain code is a sequence of direction values that represents the movement along a boundary.

### Q3. What is Freeman chain code?
Freeman chain code is an 8-direction representation of boundary movement.

### Q4. Why are 8 directions used?
Because the boundary can move in 8 possible neighbor directions around a pixel.

### Q5. What is the difference between 4-connected and 8-connected chain codes?
4-connected uses 4 directions, while 8-connected uses 8 directions and is more precise.

### Q6. What is a binary image?
A binary image contains only two pixel values, usually 0 and 255.

### Q7. Why is thresholding required?
Thresholding separates object pixels from background based on intensity.

### Q8. What is a contour?
A contour is the connected set of boundary pixels of an object.

### Q9. What is the difference between contour detection and chain code representation?
Contour detection identifies the object boundary, while chain code describes the path direction along it.

### Q10. Why do we need a starting pixel?
A starting pixel gives a consistent reference point for tracing the boundary.

### Q11. How is the direction code calculated?
By comparing the difference between the current and next boundary pixel coordinates.

### Q12. What happens when the boundary reaches the starting point?
The tracing loop stops because the boundary is closed.

### Q13. What is chain-code normalization?
Normalization removes some dependence on absolute orientation by calculating the first difference.

### Q14. What is first-difference chain code?
It is computed as $(d[i] = (code[i+1] - code[i]) \mod 8)$.

### Q15. What are the limitations of chain codes?
They can be sensitive to noise, starting point, and scale.

### Q16. Where are chain codes used?
In shape analysis, object recognition, pattern matching, and image processing.

### Q17. Why use OpenCV?
OpenCV provides efficient image processing and computer vision functions.

### Q18. Why use Python?
Python is simple, readable, and suitable for learning and prototyping.

### Q19. What happens if no boundary is detected?
The app shows an error message and asks the user to adjust the threshold or upload a clearer image.

### Q20. How can this project be improved?
By adding rotation-invariant shape descriptors, better noise handling, and multiple-shape comparison features.

### Q21. What is the purpose of grayscale conversion?
It reduces the image to a single intensity channel and simplifies thresholding.

### Q22. Why do we convert to binary?
It converts the image into object and background regions so the boundary is easier to detect.

### Q23. What is an 8-connected neighborhood?
It means a pixel can be connected to neighbors in 8 directions, including diagonals.

### Q24. Why is boundary tracing important?
Because it converts raw object shape into a compact directional representation.

### Q25. Does chain code completely solve rotation invariance?
No. It helps reduce orientation dependence but does not fully solve all geometric invariance issues.

## Project Structure
```text
boundary-detection-chain-code/
├── app.py
├── main.py
├── preprocessing.py
├── boundary.py
├── chain_code.py
├── visualization.py
├── utils.py
├── requirements.txt
├── README.md
├── images/
├── output/
└── docs/
```

## File Purpose
- app.py: Streamlit web interface.
- main.py: Command-line pipeline for testing.
- preprocessing.py: Grayscale and threshold preprocessing.
- boundary.py: Boundary and contour detection logic.
- chain_code.py: Manual tracing and chain-code generation.
- visualization.py: Overlay and chart generation.
- utils.py: Helper functions.
- requirements.txt: Package dependencies.
- README.md: Project guide.
- images/: Example images used for demonstration.
- output/: Generated outputs such as PNG and text files.
- docs/: Academic documentation.

## Conclusion
This project shows how a simple object boundary can be translated into a chain-code representation using classical image-processing methods. It is suitable for academic study, beginner learning, and demonstration in a Digital Image Processing lab.
