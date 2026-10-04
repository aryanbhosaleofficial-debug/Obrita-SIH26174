"""Small offline smoke runner: ``python -m 03_optimization``."""
from .pipeline import OptimizationPipeline

def main():
    pipeline = OptimizationPipeline()
    sample = [{"class_name": "person", "bbox": [0, 0, 100, 200], "confidence": .95, "track_id": 1}]
    print(pipeline.process(None, 0, 0.0, sample)["status"])

if __name__ == "__main__": main()
