from src.inference.detector_openvino import DeerDetectorOpenVINO
import cv2
import time

print('Initializing OpenVINO detector...')
detector = DeerDetectorOpenVINO(
    model_path='models/production/openvino/best_fp16.xml',
    conf_threshold=0.75
)

test_image = 'data/training_datasets/v1.0_2026-01-baseline/images/val/frame_001989_89b5a548296edb74.jpg'
print(f'Testing on: {test_image}')

img = cv2.imread(test_image)
print(f'Image shape: {img.shape}')

start = time.perf_counter()
detections, annotated = detector.detect(img, return_annotated=True)
end = time.perf_counter()

print(f'\n=== Detection Results ===')
print(f'Inference time: {(end - start) * 1000:.1f} ms')
print(f'Detections found: {len(detections)}')

for i, det in enumerate(detections):
    conf = det['confidence']
    print(f'  Detection {i+1}: conf={conf:.3f}')

if annotated is not None:
    output_path = 'test_openvino_output.jpg'
    cv2.imwrite(output_path, annotated)
    print(f'\nAnnotated image saved: {output_path}')

print('\nOpenVINO detector test complete!')
