"""Import original photos into Aaron's Atlas.

Drop images into photos/inbox and run this file from the project root.
The importer creates browser-friendly JPEGs, reads EXIF metadata, updates
data/photos.json, archives originals, and maintains a CSV for manual details.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import ExifTags, Image, ImageOps

try:
    from pillow_heif import register_heif_opener

    register_heif_opener()
except ImportError:
    register_heif_opener = None


ROOT = Path(__file__).resolve().parents[1]
INBOX = ROOT / "photos" / "inbox"
WEB = ROOT / "photos" / "web"
ARCHIVE = ROOT / "photos" / "archive"
DATA = ROOT / "data"
PHOTOS_JSON = DATA / "photos.json"
OVERRIDES_CSV = DATA / "photo-details.csv"
INDEX_JSON = DATA / "import-index.json"

SUPPORTED = {".jpg", ".jpeg", ".png", ".heic", ".heif", ".dng", ".tif", ".tiff"}
CSV_FIELDS = ["source_file", "title", "location", "lat", "lng", "category", "caption"]


def ensure_layout() -> None:
    for folder in (INBOX, WEB, ARCHIVE, DATA):
        folder.mkdir(parents=True, exist_ok=True)
    if not OVERRIDES_CSV.exists():
        write_csv([])
    if not INDEX_JSON.exists():
        write_json(INDEX_JSON, {})


def read_json(path: Path, fallback: Any) -> Any:
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as error:
        raise RuntimeError(f"Could not read {path.name}: {error}") from error


def write_json(path: Path, value: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def read_csv() -> dict[str, dict[str, str]]:
    if not OVERRIDES_CSV.exists():
        return {}
    with OVERRIDES_CSV.open(newline="", encoding="utf-8-sig") as handle:
        return {row["source_file"]: row for row in csv.DictReader(handle) if row.get("source_file")}


def write_csv(rows: list[dict[str, str]]) -> None:
    temporary = OVERRIDES_CSV.with_suffix(".csv.tmp")
    with temporary.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(OVERRIDES_CSV)


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def slugify(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
    return value or "photo"


def unique_output_name(stem: str, fingerprint: str) -> str:
    return f"{slugify(stem)}-{fingerprint[:8]}.jpg"


def decimal_coordinate(values: Any, reference: str) -> float:
    degrees, minutes, seconds = (float(item) for item in values)
    coordinate = degrees + minutes / 60 + seconds / 3600
    return -coordinate if reference in {"S", "W"} else coordinate


def extract_metadata(image: Image.Image) -> dict[str, Any]:
    exif = image.getexif()
    exif_ifd = exif.get_ifd(0x8769) if 0x8769 in exif else {}
    gps_ifd = exif.get_ifd(0x8825) if 0x8825 in exif else {}
    gps = {ExifTags.GPSTAGS.get(key, key): value for key, value in gps_ifd.items()}

    lat = lng = None
    required = {"GPSLatitude", "GPSLatitudeRef", "GPSLongitude", "GPSLongitudeRef"}
    if required.issubset(gps):
        candidate_lat = decimal_coordinate(gps["GPSLatitude"], gps["GPSLatitudeRef"])
        candidate_lng = decimal_coordinate(gps["GPSLongitude"], gps["GPSLongitudeRef"])
        if candidate_lat or candidate_lng:
            lat, lng = round(candidate_lat, 7), round(candidate_lng, 7)

    captured = exif_ifd.get(36867) or exif.get(306)
    date = "Date Unknown"
    if captured:
        try:
            date = datetime.strptime(str(captured), "%Y:%m:%d %H:%M:%S").strftime("%B %-d, %Y")
        except ValueError:
            date = str(captured)
        except OSError:  # Windows does not support %-d.
            date = datetime.strptime(str(captured), "%Y:%m:%d %H:%M:%S").strftime("%B %d, %Y").replace(" 0", " ")

    make = str(exif.get(271, "")).strip()
    model = str(exif.get(272, "")).strip()
    camera = " ".join(part for part in (make, model) if part).strip() or "Unknown"
    lens = str(exif_ifd.get(42036, "Unknown"))

    return {"lat": lat, "lng": lng, "date": date, "camera": camera, "lens": lens}


def create_web_image(source: Path, destination: Path) -> dict[str, Any]:
    try:
        with Image.open(source) as original:
            metadata = extract_metadata(original)
            image = ImageOps.exif_transpose(original)
            if image.mode not in ("RGB", "L"):
                background = Image.new("RGB", image.size, "white")
                if "A" in image.getbands():
                    background.paste(image, mask=image.getchannel("A"))
                else:
                    background.paste(image)
                image = background
            elif image.mode == "L":
                image = image.convert("RGB")
            image.thumbnail((2400, 2400), Image.Resampling.LANCZOS)
            image.save(destination, "JPEG", quality=88, optimize=True, progressive=True)
            return metadata
    except Exception as error:
        if source.suffix.lower() in {".heic", ".heif"} and register_heif_opener is None:
            raise RuntimeError("HEIC support is missing. Run update-atlas.bat to install it.") from error
        raise RuntimeError(f"Could not process {source.name}: {error}") from error


def title_from_stem(stem: str) -> str:
    cleaned = re.sub(r"^(img|dsc)[-_ ]*\d+$", "New Photograph", stem, flags=re.IGNORECASE)
    cleaned = re.sub(r"[-_]+", " ", cleaned).strip()
    return cleaned.title() or "New Photograph"


def optional_float(value: str, fallback: float | None) -> float | None:
    if not value.strip():
        return fallback
    try:
        return round(float(value), 7)
    except ValueError:
        return fallback


def archive_source(source: Path) -> Path:
    destination = ARCHIVE / source.name
    counter = 2
    while destination.exists():
        destination = ARCHIVE / f"{source.stem}-{counter}{source.suffix.lower()}"
        counter += 1
    return Path(shutil.move(str(source), str(destination)))


def apply_saved_details(photos: list[dict[str, Any]], overrides: dict[str, dict[str, str]]) -> int:
    """Apply CSV edits to records that were imported on an earlier run."""
    updated = 0
    for photo in photos:
        source_file = photo.get("sourceFile")
        override = overrides.get(source_file, {})
        if not override:
            continue

        before = json.dumps(photo, sort_keys=True)
        for field in ("title", "location", "category", "caption"):
            value = override.get(field, "").strip()
            if value:
                photo[field] = value

        lat = optional_float(override.get("lat", ""), photo.get("lat"))
        lng = optional_float(override.get("lng", ""), photo.get("lng"))
        photo["lat"], photo["lng"] = lat, lng
        if lat is not None and lng is not None and photo.get("locationAccuracy") == "missing":
            photo["locationAccuracy"] = "manual"
        if json.dumps(photo, sort_keys=True) != before:
            updated += 1
    return updated


def main() -> int:
    ensure_layout()
    photos = read_json(PHOTOS_JSON, [])
    index = read_json(INDEX_JSON, {})
    overrides = read_csv()
    updated_details = apply_saved_details(photos, overrides)
    csv_rows = list(overrides.values())
    csv_by_name = {row["source_file"]: row for row in csv_rows}
    sources = sorted(path for path in INBOX.iterdir() if path.is_file() and path.suffix.lower() in SUPPORTED)

    if not sources:
        if updated_details:
            write_json(PHOTOS_JSON, photos)
            print(f"Updated details for {updated_details} existing photo(s).")
        print(f"No supported photos found in {INBOX.relative_to(ROOT)}")
        print("Drop original JPG, HEIC, DNG, PNG, or TIFF files there and run again.")
        return 0

    imported = skipped = needs_location = 0
    for source in sources:
        fingerprint = file_hash(source)
        if fingerprint in index:
            print(f"SKIP  {source.name} (already imported)")
            archive_source(source)
            skipped += 1
            continue

        web_name = unique_output_name(source.stem, fingerprint)
        web_path = WEB / web_name
        metadata = create_web_image(source, web_path)
        override = overrides.get(source.name, {})
        lat = optional_float(override.get("lat", ""), metadata["lat"])
        lng = optional_float(override.get("lng", ""), metadata["lng"])
        has_location = lat is not None and lng is not None

        photo = {
            "title": override.get("title", "").strip() or title_from_stem(source.stem),
            "location": override.get("location", "").strip() or ("GPS location" if has_location else "Location needed"),
            "lat": lat,
            "lng": lng,
            "locationAccuracy": "GPS" if metadata["lat"] is not None else ("manual" if has_location else "missing"),
            "category": override.get("category", "").strip() or "Uncategorized",
            "image": f"photos/web/{web_name}",
            "date": metadata["date"],
            "camera": metadata["camera"],
            "lens": metadata["lens"],
            "caption": override.get("caption", "").strip() or "Caption coming soon.",
            "sourceFile": source.name,
            "importId": fingerprint,
        }
        photos.append(photo)
        archived = archive_source(source)
        index[fingerprint] = {"source": archived.name, "web": web_name}
        imported += 1

        if not has_location:
            needs_location += 1
            if source.name not in csv_by_name:
                row = {
                    "source_file": source.name,
                    "title": photo["title"],
                    "location": "",
                    "lat": "",
                    "lng": "",
                    "category": photo["category"],
                    "caption": photo["caption"],
                }
                csv_rows.append(row)
                csv_by_name[source.name] = row

        print(f"ADD   {source.name} -> {web_name}" + ("" if has_location else " (location needed)"))

    write_json(PHOTOS_JSON, photos)
    write_json(INDEX_JSON, index)
    write_csv(csv_rows)
    print(
        f"\nImported: {imported} | Skipped: {skipped} | "
        f"Updated details: {updated_details} | Need location: {needs_location}"
    )
    if needs_location:
        print(f"Fill missing details in {OVERRIDES_CSV.relative_to(ROOT)} before the next import.")
    print("Atlas data is ready. Refresh the website to view mapped photos.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"\nERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
