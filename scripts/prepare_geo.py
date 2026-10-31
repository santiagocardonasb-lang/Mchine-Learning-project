"""Build the geography files LocWaste needs from the raw Bogota open data.

Run from the project root:  python scripts/prepare_geo.py

Inputs (data/raw/):  loca.json, upz.json, pc.geojson (already downloaded);
sector_catastral.geojson and locality_population.csv are downloaded when missing.
Outputs: app/static/geo/{localities,upz,neighborhoods}.geojson and data/zone_stats.csv.
"""
import csv
import io
import json
import math
import re
import unicodedata
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from collections import defaultdict
from pathlib import Path

import numpy as np
import shapely
from shapely.geometry import Point, Polygon, mapping, shape
from shapely.geometry.polygon import orient
from shapely.ops import unary_union
from shapely.validation import make_valid

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
GEO_OUT = ROOT / "app" / "static" / "geo"

SECTOR_PACKAGE_API = "https://datosabiertos.bogota.gov.co/api/3/action/package_show?id=sector-catastral"
POPULATION_YEAR = 2026
POPULATION_URL = (
    "https://datosabiertos.bogota.gov.co/dataset/0f1fb76a-1595-43d5-9257-0abcc3db908a/resource/"
    "5669484f-dc1d-4457-b1d1-de0a3825b41c/download/"
    "202503_localidad_proyeccion_retroproyeccion_poblacion_2005_2035.ods"
)
RURAL_LOCALITY = "20"  # Sumapaz
SIMPLIFY_TOLERANCE = 0.0003  # degrees, about 33 m
# At Bogota's latitude one degree is 111.32 km in latitude and 111.32 * cos(lat) km in longitude.
KM2_PER_DEGREE2 = 111.32**2 * math.cos(math.radians(4.6))

WEEKDAYS = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]
SMALL_WORDS = {"de", "del", "la", "las", "los", "el", "y"}
ROMAN = re.compile(r"^(XL|L?X{0,3})(IX|IV|V?I{0,3})$")


def download(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "locwaste-prepare-geo"})
    with urllib.request.urlopen(request, timeout=300) as response:
        return response.read()


def display_name(raw: str) -> str:
    """Title-case an uppercase source name, keeping roman numerals and acronyms upper."""
    words = []
    for index, word in enumerate(raw.strip().split()):
        if word == "CAN" or ROMAN.match(word):
            words.append(word)
        elif index > 0 and word.lower() in SMALL_WORDS:
            words.append(word.lower())
        else:
            words.append(word.capitalize())
    return " ".join(words)


# ---------- geometry helpers ----------


def polygonal(geometry):
    """Keep only the polygon parts of a geometry (make_valid can return mixed collections)."""
    if geometry.geom_type in ("Polygon", "MultiPolygon"):
        return geometry
    parts = [g for g in getattr(geometry, "geoms", []) if g.geom_type in ("Polygon", "MultiPolygon")]
    return unary_union(parts) if parts else Polygon()


def esri_to_shape(rings):
    """Esri rings: clockwise = exterior, counter-clockwise = hole."""
    exteriors, holes = [], []
    for ring in rings:
        polygon = Polygon(ring)
        (holes if shapely.is_ccw(polygon.exterior) else exteriors).append(polygon)
    result = []
    for exterior in exteriors:
        inner = [h.exterior.coords for h in holes if exterior.contains(h.representative_point())]
        result.append(Polygon(exterior.exterior.coords, inner))
    geometry = result[0] if len(result) == 1 else unary_union([make_valid(p) for p in result])
    return polygonal(make_valid(geometry))


def finalize(geometry, simplify=True):
    """Simplify, round to 5 decimals, and return a valid, right-hand-oriented geometry."""
    simple = geometry.simplify(SIMPLIFY_TOLERANCE, preserve_topology=True) if simplify else geometry
    if simple.is_empty:
        simple = geometry
    rounded = shapely.transform(simple, lambda coords: np.round(coords, 5))
    rounded = polygonal(make_valid(rounded))
    if rounded.geom_type == "MultiPolygon":
        return shapely.MultiPolygon([orient(p, 1.0) for p in rounded.geoms])
    return orient(rounded, 1.0)


def feature(geometry, properties):
    return {"type": "Feature", "properties": properties, "geometry": mapping(geometry)}


def write_geojson(path: Path, features):
    path.parent.mkdir(parents=True, exist_ok=True)
    collection = {"type": "FeatureCollection", "features": features}
    path.write_text(json.dumps(collection, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")


# ---------- collection frequency ----------


def days_per_week(frequency: str) -> int:
    text = unicodedata.normalize("NFKD", frequency).encode("ascii", "ignore").decode().lower()
    times = re.search(r"(\d+)\s*veces", text)
    if times:
        return int(times.group(1))
    names = [name for name in WEEKDAYS if name in text]
    if " a " in text and len(names) == 2:
        return WEEKDAYS.index(names[1]) - WEEKDAYS.index(names[0]) + 1
    return len(names)


# ---------- downloads ----------


def ensure_sectors() -> Path:
    target = RAW / "sector_catastral.geojson"
    if target.exists():
        return target
    package = json.loads(download(SECTOR_PACKAGE_API))["result"]
    resource = next(r for r in package["resources"] if r["format"].lower() == "geojson")
    print(f"Downloading cadastral sectors: {resource['url']}")
    with zipfile.ZipFile(io.BytesIO(download(resource["url"]))) as archive:
        member = next(n for n in archive.namelist() if n.lower().endswith(".geojson"))
        target.write_bytes(archive.read(member))
    return target


def read_ods_rows(content: bytes):
    office = "urn:oasis:names:tc:opendocument:xmlns:office:1.0"
    table = "{urn:oasis:names:tc:opendocument:xmlns:table:1.0}"
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        root = ET.fromstring(archive.read("content.xml"))
    for row in root.iter(table + "table-row"):
        cells = []
        for cell in row.findall(table + "table-cell"):
            repeat = int(cell.get(table + "number-columns-repeated", "1"))
            value = cell.get(f"{{{office}}}value") or "".join(cell.itertext())
            if not value and repeat > 50:  # trailing blank cells
                break
            cells += [value] * repeat
        if any(cells):
            yield cells


def ensure_population() -> Path:
    target = RAW / "locality_population.csv"
    if target.exists():
        return target
    print(f"Downloading SDP population projection: {POPULATION_URL}")
    rows = read_ods_rows(download(POPULATION_URL))
    header = next(rows)
    col = {name: header.index(name) for name in ("Código Localidad", "Nombre Localidad", "AÑO", "Total")}
    totals, names = defaultdict(int), {}
    for row in rows:
        if int(row[col["AÑO"]]) != POPULATION_YEAR:
            continue
        code = str(int(row[col["Código Localidad"]]))
        names[code] = row[col["Nombre Localidad"]]
        totals[code] += round(float(row[col["Total"]]))  # urban + rural-area rows of the locality
    totals.pop(RURAL_LOCALITY)
    with open(target, "w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["code", "name", "population", "year", "source_url"])
        for code in sorted(totals, key=int):
            writer.writerow([code, names[code], totals[code], POPULATION_YEAR, POPULATION_URL])
    return target


# ---------- main steps ----------


def load_esri(name: str):
    return json.loads((RAW / name).read_text(encoding="utf-8"))["features"]


def build_localities():
    with open(ensure_population(), encoding="utf-8", newline="") as handle:
        names = {row["code"]: row["name"] for row in csv.DictReader(handle)}
    localities = {}
    for item in load_esri("loca.json"):
        code = str(int(item["attributes"]["LocCodigo"]))
        if code != RURAL_LOCALITY:
            localities[code] = (names[code], esri_to_shape(item["geometry"]["rings"]))
    return localities


def build_upzs(localities):
    upzs = {}
    for item in load_esri("upz.json"):
        attrs = item["attributes"]
        geometry = esri_to_shape(item["geometry"]["rings"])
        locality = max(localities, key=lambda c: geometry.intersection(localities[c][1]).area)
        upzs[str(attrs["CODIGO_UPZ"])] = {
            "name": display_name(attrs["NOMBRE"]),
            "geometry": geometry,
            "locality": locality,
            "public_space": attrs["EPE__m2_ha"],
            "points": [],
        }
    return upzs


def assign_critical_points(upzs):
    points = json.loads((RAW / "pc.geojson").read_text(encoding="utf-8"))["features"]
    for item in points:
        point = shape(item["geometry"])
        inside = [code for code, upz in upzs.items() if upz["geometry"].contains(point)]
        # Points outside every UPZ (or on a border) go to the nearest one so none is lost.
        code = inside[0] if inside else min(upzs, key=lambda c: upzs[c]["geometry"].distance(point))
        upzs[code]["points"].append(days_per_week(item["properties"]["Frecuencia"]))
    return len(points)


def write_zone_stats(localities, upzs):
    path = ROOT / "data" / "zone_stats.csv"
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "upz_code", "upz_name", "locality_code", "locality_name", "area_km2",
            "critical_points", "public_space_m2_per_inhabitant", "collection_days_per_week",
        ])
        for code in sorted(upzs, key=int):
            upz = upzs[code]
            days = upz["points"]
            writer.writerow([
                code, upz["name"], upz["locality"], localities[upz["locality"]][0],
                round(upz["geometry"].area * KM2_PER_DEGREE2, 3), len(days),
                "" if upz["public_space"] is None else round(upz["public_space"], 3),
                round(sum(days) / len(days), 2) if days else 0,
            ])


def write_neighborhoods():
    sectors = json.loads(ensure_sectors().read_text(encoding="utf-8"))["features"]
    features = []
    for item in sectors:
        props = item["properties"]
        if props["SCATIPO"] != 0:  # 0 = urban neighborhood; 1 and 2 are rural or mixed veredas
            continue
        geometry = finalize(make_valid(shape(item["geometry"])))
        features.append(feature(geometry, {"code": props["SCACODIGO"], "name": display_name(props["SCANOMBRE"])}))
    write_geojson(GEO_OUT / "neighborhoods.geojson", features)


def main():
    localities = build_localities()
    upzs = build_upzs(localities)
    total = assign_critical_points(upzs)
    assert sum(len(u["points"]) for u in upzs.values()) == total

    write_geojson(GEO_OUT / "localities.geojson", [
        feature(finalize(geometry), {"code": code, "name": name})
        for code, (name, geometry) in sorted(localities.items(), key=lambda kv: int(kv[0]))
    ])
    write_geojson(GEO_OUT / "upz.geojson", [
        feature(finalize(u["geometry"]), {"code": code, "name": u["name"], "locality_code": u["locality"]})
        for code, u in sorted(upzs.items(), key=lambda kv: int(kv[0]))
    ])
    write_zone_stats(localities, upzs)
    write_neighborhoods()
    print(f"{len(localities)} localities, {len(upzs)} UPZ, {total} critical points assigned.")


if __name__ == "__main__":
    main()
