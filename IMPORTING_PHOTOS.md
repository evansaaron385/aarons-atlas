# Importing photos into Aaron's Atlas

## Normal workflow

1. Copy original photos into `photos/inbox`.
2. Double-click `update-atlas.bat`.
3. Wait for **Update complete**.
4. Refresh the portfolio in the browser.

The first run creates a private Python environment and installs the image readers. Later runs are faster.

## What the importer does

- Reads GPS, capture date, camera, and lens metadata.
- Converts JPG, JPEG, HEIC, HEIF, DNG, PNG, and TIFF files into optimized web JPEGs.
- Places web images in `photos/web`.
- Moves original files safely into `photos/archive`.
- Adds new records to `data/photos.json`.
- Prevents the same image from being imported twice.

## Missing locations or descriptions

If a photo has no GPS data, it is added to `data/photo-details.csv`. Open that CSV in Excel and complete any known fields. Keep latitude and longitude in decimal-degree format, such as `30.3322` and `-81.6557`. Save the CSV and run `update-atlas.bat` again to apply your edits.

The importer never invents coordinates. Photos without coordinates remain in the data but are not placed on the map until valid coordinates are supplied.

For polished titles, categories, and captions, add a row to `data/photo-details.csv` using the photo's original filename before importing it.
