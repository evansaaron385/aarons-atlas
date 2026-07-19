import sys

import exifread

photo_path = sys.argv[1] if len(sys.argv) > 1 else "../photos/meridian-sunset.jpg"

with open(photo_path, "rb") as image:
    tags = exifread.process_file(image)

interesting_tags = [
    "Image Make",
    "Image Model",
    "EXIF DateTimeOriginal",
    "EXIF LensModel",
    "EXIF FNumber",
    "EXIF ExposureTime",
    "EXIF ISOSpeedRatings",
    "GPS GPSLatitude",
    "GPS GPSLongitude"
]

print("=" * 50)

for tag in interesting_tags:
    print(f"{tag}: {tags.get(tag, 'Not Found')}")
