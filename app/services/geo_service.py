import json
import unicodedata
from dataclasses import asdict, dataclass
from functools import cache
from pathlib import Path

from shapely import STRtree, points
from shapely.geometry import shape

GEO_DIR = Path(__file__).resolve().parent.parent / "static" / "geo"


@dataclass(frozen=True)
class ZoneMatch:
    locality_code: str
    locality_name: str
    upz_code: str
    upz_name: str
    neighborhood: str | None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class _Layer:
    props: list[dict]
    geoms: list
    tree: STRtree


def _load_features(name: str) -> list[dict]:
    with open(GEO_DIR / f"{name}.geojson", encoding="utf-8") as f:
        return json.load(f)["features"]


def _build_layer(name: str) -> _Layer:
    features = _load_features(name)
    geoms = [shape(f["geometry"]) for f in features]
    return _Layer([f["properties"] for f in features], geoms, STRtree(geoms))


@cache
def _upz_layer() -> _Layer:
    return _build_layer("upz")


@cache
def _neighborhood_layer() -> _Layer:
    return _build_layer("neighborhoods")


@cache
def _locality_names() -> dict[str, str]:
    return {f["properties"]["code"]: f["properties"]["name"] for f in _load_features("localities")}


@cache
def _neighborhood_index() -> list[tuple[str, str, float, float]]:
    """(name, normalized name, lat, lon) for every sector, using an interior point."""
    layer = _neighborhood_layer()
    index = []
    for props, geom in zip(layer.props, layer.geoms):
        # representative_point is guaranteed to lie inside the polygon, unlike the centroid.
        p = geom.representative_point()
        index.append((props["name"], _normalize(props["name"]), p.y, p.x))
    return index


def _normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).casefold().strip()


def _containing(layer: _Layer, point) -> dict | None:
    hits = layer.tree.query(point, predicate="within")
    if len(hits) == 0:
        return None
    # Borders can touch; take the lowest index so the answer is deterministic.
    return layer.props[int(min(hits))]


def locate(lat: float, lon: float) -> ZoneMatch | None:
    point = points(lon, lat)
    upz = _containing(_upz_layer(), point)
    if upz is None:
        return None
    sector = _containing(_neighborhood_layer(), point)
    locality_code = str(upz["locality_code"])
    return ZoneMatch(
        locality_code=locality_code,
        locality_name=_locality_names().get(locality_code, ""),
        upz_code=str(upz["code"]),
        upz_name=upz["name"],
        neighborhood=sector["name"] if sector else None,
    )


def search_neighborhoods(q: str, limit: int = 8) -> list[dict]:
    needle = _normalize(q)
    if len(needle) < 2:
        return []
    matches = [row for row in _neighborhood_index() if needle in row[1]]
    matches.sort(key=lambda row: (not row[1].startswith(needle), row[1]))
    return [{"name": name, "lat": lat, "lon": lon} for name, _, lat, lon in matches[:limit]]
