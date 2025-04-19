from picamzero import Camera
import requests
import io

# Initialize the Raspberry Pi camera
cam = Camera()

# Take a photo and save it to a temporary file
import tempfile
import os

# Create a temporary file with .jpg extension
temp_file = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
temp_file.close()

# Take the photo and save it to the temporary file
cam.take_photo(temp_file.name)

# Read the file back as binary data
with open(temp_file.name, "rb") as f:
    binary_jpeg_data = f.read()

# Clean up by removing the temporary file
os.unlink(temp_file.name)

# Send the image to the API
res = requests.post("https://art.ycloud.eazify.net:8443/comp", binary_jpeg_data)

# Print the response text
print(res.json()["text"])

