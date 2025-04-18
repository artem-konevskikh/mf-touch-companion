from picamzero import Camera
import requests
import io

# Initialize the Raspberry Pi camera
cam = Camera()

# Take a photo and save it to an in-memory buffer
image_stream = io.BytesIO()
cam.take_photo(image_stream)

# Get the binary data from the stream
image_stream.seek(0)
binary_jpeg_data = image_stream.read()

# Send the image to the API
res = requests.post("https://art.ycloud.eazify.net:8443/comp", binary_jpeg_data)

# Print the response text
print(res.json()["text"])

# Close the camera
cam.close()
