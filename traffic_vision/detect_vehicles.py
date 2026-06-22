import cv2
from ultralytics import YOLO
import json
import os

def detect_vehicles(image_path, output_image_path, output_json_path):
    # Load the pre-trained YOLOv8 model (nano version for speed)
    print("Loading YOLOv8n model...")
    model = YOLO('yolov8n.pt')

    # Run inference on the image
    print(f"Running inference on {image_path}...")
    results = model(image_path)

    # Relevant classes for traffic: 0: person, 1: bicycle, 2: car, 3: motorcycle, 5: bus, 7: truck
    traffic_classes = [0, 1, 2, 3, 5, 7]

    detections = []
    
    # Process results
    for r in results:
        img_with_boxes = r.plot() # YOLO's built-in function to draw bounding boxes
        
        for box in r.boxes:
            cls_id = int(box.cls[0])
            if cls_id in traffic_classes:
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                conf = float(box.conf[0])
                class_name = model.names[cls_id]
                
                detections.append({
                    "class": class_name,
                    "confidence": round(conf, 4),
                    "bbox": [round(x1, 2), round(y1, 2), round(x2, 2), round(y2, 2)]
                })

        # Save the annotated image
        cv2.imwrite(output_image_path, img_with_boxes)

    # Save metadata to JSON
    with open(output_json_path, 'w') as f:
        json.dump({"timestamp": "2026-06-20T18:00:00Z", "detections": detections}, f, indent=4)
        
    print(f"Detection complete. Found {len(detections)} traffic objects.")
    print(f"Annotated image saved to {output_image_path}")
    print(f"Metadata saved to {output_json_path}")

if __name__ == "__main__":
    image_path = "sample_traffic.jpg"
    if not os.path.exists(image_path):
        print(f"Error: {image_path} not found.")
    else:
        detect_vehicles(image_path, "output_annotated.jpg", "output_metadata.json")
