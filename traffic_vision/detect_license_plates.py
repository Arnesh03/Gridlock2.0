import cv2
import easyocr
import json
import os

def detect_license_plates(image_path, output_image_path, output_json_path):
    print("Loading EasyOCR model...")
    # Initialize reader for English (add 'gpu=False' if M1/M2 macs have issues)
    reader = easyocr.Reader(['en'])
    
    # Run OCR on the image
    print(f"Running EasyOCR on {image_path}...")
    results = reader.readtext(image_path)
    
    img = cv2.imread(image_path)
    
    plates = []
    
    for (bbox, text, prob) in results:
        # EasyOCR returns bbox as a list of 4 points: [top-left, top-right, bottom-right, bottom-left]
        (tl, tr, br, bl) = bbox
        tl = (int(tl[0]), int(tl[1]))
        br = (int(br[0]), int(br[1]))
        
        # For MVP, just filter by confidence
        if prob > 0.2:
            plates.append({
                "text": text,
                "confidence": round(float(prob), 4),
                "bbox": [tl[0], tl[1], br[0], br[1]]
            })
            
            # Draw bbox and text
            cv2.rectangle(img, tl, br, (0, 255, 0), 2)
            cv2.putText(img, text, (tl[0], tl[1] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)

    cv2.imwrite(output_image_path, img)

    # Save metadata to JSON
    with open(output_json_path, 'w') as f:
        json.dump({"plates": plates}, f, indent=4)
        
    print(f"OCR complete. Found {len(plates)} potential text regions.")
    print(f"Annotated image saved to {output_image_path}")
    print(f"Metadata saved to {output_json_path}")

if __name__ == "__main__":
    image_path = "sample_traffic.jpg"
    if not os.path.exists(image_path):
        print(f"Error: {image_path} not found.")
    else:
        detect_license_plates(image_path, "output_plates_annotated.jpg", "output_plates_metadata.json")
