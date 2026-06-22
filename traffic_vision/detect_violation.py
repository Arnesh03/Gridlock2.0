import cv2
from ultralytics import YOLO
import json
import os

def detect_stopline_violation(image_path, output_image_path, output_json_path):
    print("Loading YOLOv8n model...")
    model = YOLO('yolov8n.pt')

    print(f"Running inference on {image_path}...")
    results = model(image_path)
    
    img = cv2.imread(image_path)
    height, width, _ = img.shape

    # Define a mock stop line (e.g., lower 30% of the image)
    stop_line_y = int(height * 0.7)
    
    # Draw the stop line
    cv2.line(img, (0, stop_line_y), (width, stop_line_y), (0, 0, 255), 3)
    cv2.putText(img, "STOP LINE (MOCK RED LIGHT)", (10, stop_line_y - 10), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

    # Relevant classes for vehicles crossing stop lines
    traffic_classes = [2, 3, 5, 7] # car, motorcycle, bus, truck

    violations = []
    
    for r in results:
        for box in r.boxes:
            cls_id = int(box.cls[0])
            if cls_id in traffic_classes:
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                conf = float(box.conf[0])
                class_name = model.names[cls_id]
                
                # Check if vehicle crossed the stop line (bottom edge y2 > stop_line_y)
                # This assumes a top-down or slight angle view
                if y2 > stop_line_y:
                    color = (0, 0, 255) # Red box for violation
                    label = f"VIOLATION: {class_name} {conf:.2f}"
                    
                    violations.append({
                        "class": class_name,
                        "confidence": round(conf, 4),
                        "bbox": [round(x1, 2), round(y1, 2), round(x2, 2), round(y2, 2)],
                        "violation_type": "Stop Line Crossing"
                    })
                else:
                    color = (0, 255, 0) # Green box for safe
                    label = f"{class_name} {conf:.2f}"
                
                # Draw bounding box
                cv2.rectangle(img, (int(x1), int(y1)), (int(x2), int(y2)), color, 2)
                cv2.putText(img, label, (int(x1), int(y1) - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

    cv2.imwrite(output_image_path, img)

    with open(output_json_path, 'w') as f:
        json.dump({"timestamp": "2026-06-20T18:00:00Z", "violations": violations}, f, indent=4)
        
    print(f"Violation detection complete. Found {len(violations)} violations.")
    print(f"Annotated image saved to {output_image_path}")
    print(f"Metadata saved to {output_json_path}")

if __name__ == "__main__":
    image_path = "sample_traffic.jpg"
    if not os.path.exists(image_path):
        print(f"Error: {image_path} not found.")
    else:
        detect_stopline_violation(image_path, "output_violation_annotated.jpg", "output_violation_metadata.json")
