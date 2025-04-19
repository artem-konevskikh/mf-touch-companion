import cv2
import requests
import time

# Initialize webcam (0 is usually the default camera)
cap = cv2.VideoCapture(0)

while cap.isOpened():
    ret, frame = cap.read()

    if not ret:
        break

    # Convert the captured frame to JPEG format in memory
    success, encoded_image = cv2.imencode('.jpg', frame)

    # Convert the numpy array to bytes (binary JPEG data)
    binary_jpeg_data = encoded_image.tobytes()
    print("captured")

    res = requests.post('https://art.ycloud.eazify.net:8443/comp',
                        binary_jpeg_data)
    
    print(res.json()['text'])

    time.sleep(5)

cap.release()