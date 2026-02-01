from ultralytics import YOLO

print("Downloading YOLO26n weights...")
model = YOLO('yolo26n.pt')
print("YOLO26n downloaded successfully!")
print(f"Model info: {model.model}")
