from ultralytics import YOLO
import ultralytics

print(f"Ultralytics version: {ultralytics.__version__}")
print("\nAvailable YOLO models:")
print("  - YOLOv5 (older)")
print("  - YOLOv8 (current production)")
print("  - YOLO11 (latest, most advanced)")
print("\nNote: There is no YOLO26. YOLO11 is the newest version.")
print("YOLO11 improvements over YOLOv8:")
print("  - Better accuracy")
print("  - Faster inference")
print("  - Improved architecture")
