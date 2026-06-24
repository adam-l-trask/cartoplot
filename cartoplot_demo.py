#!/usr/bin/env python3
"""cartoplot_demo.py — generate a batch of trajectories and bake them into a
self-contained Cartoplot HTML figure.

What it does
------------
Builds ~20 great-circle airline routes between real airports, each carrying
per-point tooltip data (elapsed minutes, altitude, ground speed), plus one
filled polygon to show the "polygon" layer type, then embeds everything into the
Cartoplot template and writes a ready-to-open HTML file with the legend turned on.

Usage
-----
    python cartoplot_demo.py                         # template: ./cartoplot.html  ->  ./cartoplot_demo.html
    python cartoplot_demo.py cartoplot.html out.html   # explicit template / output

It writes two figures: the normal CDN-backed one, and — if the offline assets
are available (it offers to download them once) — a fully self-contained
"cartoplot_demo_offline.html" that opens with no internet. See the offline notes
in cartoplot_embed.embed() / download_offline_assets().

It only needs the standard library. (The cartoplot_embed helper also accepts
pandas DataFrames via layer_from_dataframe if you'd rather feed it a frame.)
"""
import math
import os
import sys

# Make sure we can import the sibling helper regardless of the working directory.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cartoplot_embed import (path_layer, polygon_layer, embed,
                             download_offline_assets, OFFLINE_ASSETS,
                             ASSET_DIR_DEFAULT)


# --- airports: name -> (lon, lat) ------------------------------------------
AIRPORTS = {
    "New York":     (-73.78,  40.64),
    "London":       ( -0.46,  51.47),
    "Tokyo":        (139.78,  35.55),
    "Los Angeles":  (-118.41, 33.94),
    "Sydney":       (151.18, -33.95),
    "Singapore":    (103.99,   1.36),
    "Sao Paulo":    (-46.47, -23.43),
    "Johannesburg": ( 28.23, -26.13),
    "Dubai":        ( 55.36,  25.25),
    "San Francisco":(-122.38, 37.62),
    "Paris":        (  2.55,  49.01),
    "Buenos Aires": (-58.54, -34.82),
    "Hong Kong":    (113.91,  22.31),
    "Moscow":       ( 37.41,  55.97),
    "Beijing":      (116.60,  40.08),
    "Chicago":      (-87.90,  41.98),
    "Frankfurt":    (  8.57,  50.03),
    "Cairo":        ( 31.41,  30.11),
    "Mumbai":       ( 72.87,  19.09),
    "Vancouver":    (-123.18, 49.19),
    "Anchorage":    (-149.99, 61.17),
    "Reykjavik":    (-22.61,  63.98),
    "Istanbul":     ( 28.81,  41.26),
    "Delhi":        ( 77.10,  28.57),
    "Toronto":      (-79.63,  43.68),
    "Seattle":      (-122.31, 47.45),
    "Santiago":     (-70.79, -33.39),
    "Auckland":     (174.79, -37.01),
}

# --- routes: (origin, destination) -----------------------------------------
ROUTES = [
    ("New York",     "London"),
    ("Tokyo",        "Los Angeles"),
    ("Sydney",       "Singapore"),
    ("Sao Paulo",    "Johannesburg"),
    ("Dubai",        "New York"),
    ("San Francisco","Tokyo"),
    ("Paris",        "Buenos Aires"),
    ("Hong Kong",    "London"),
    ("Moscow",       "Beijing"),
    ("Chicago",      "Frankfurt"),
    ("Cairo",        "Mumbai"),
    ("Vancouver",    "Sydney"),      # crosses the Pacific / antimeridian
    ("Anchorage",    "Tokyo"),
    ("Reykjavik",    "New York"),
    ("Los Angeles",  "Sydney"),      # crosses the antimeridian
    ("Istanbul",     "Sao Paulo"),
    ("Delhi",        "Toronto"),     # near-polar
    ("Seattle",      "Dubai"),       # near-polar
    ("Santiago",     "Auckland"),    # crosses the antimeridian
    ("Tokyo",        "Paris"),       # near-polar
]


def great_circle(lon1, lat1, lon2, lat2, n=80):
    """Densely sample the great-circle path between two points (slerp on the
    sphere). Returns n+1 [lon, lat] pairs in [-180, 180]."""
    f1, l1, f2, l2 = map(math.radians, (lat1, lon1, lat2, lon2))
    # central angle between the endpoints
    d = 2 * math.asin(math.sqrt(
        math.sin((f2 - f1) / 2) ** 2 +
        math.cos(f1) * math.cos(f2) * math.sin((l2 - l1) / 2) ** 2))
    if d == 0:
        return [[lon1, lat1], [lon2, lat2]]
    pts = []
    for i in range(n + 1):
        f = i / n
        a = math.sin((1 - f) * d) / math.sin(d)
        b = math.sin(f * d) / math.sin(d)
        x = a * math.cos(f1) * math.cos(l1) + b * math.cos(f2) * math.cos(l2)
        y = a * math.cos(f1) * math.sin(l1) + b * math.cos(f2) * math.sin(l2)
        z = a * math.sin(f1) + b * math.sin(f2)
        lat = math.degrees(math.atan2(z, math.hypot(x, y)))
        lon = math.degrees(math.atan2(y, x))
        pts.append([round(lon, 4), round(lat, 4)])
    return pts


def haversine_km(lon1, lat1, lon2, lat2):
    f1, f2 = math.radians(lat1), math.radians(lat2)
    df = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(df / 2) ** 2 + math.cos(f1) * math.cos(f2) * math.sin(dl / 2) ** 2
    return 6371.0 * 2 * math.asin(math.sqrt(a))


def flight_profile(n, dist_km):
    """Per-point elapsed minutes, altitude (ft) and ground speed (kt) along a
    flight: climb, cruise, descend. Lists are parallel to the n+1 path points."""
    total_min = dist_km / 880.0 * 60.0 + 30.0    # +pad for taxi/climb/descent
    cruise_ft, cruise_kt = 36000, 480
    elapsed, alt, spd = [], [], []
    for i in range(n + 1):
        f = i / n
        elapsed.append(round(f * total_min, 1))
        # altitude: ramp up over the first 12%, hold, ramp down over the last 12%
        if f < 0.12:
            alt.append(round(cruise_ft * (f / 0.12)))
        elif f > 0.88:
            alt.append(round(cruise_ft * ((1 - f) / 0.12)))
        else:
            alt.append(cruise_ft)
        # ground speed: 150kt near the ends ramping to cruise
        if f < 0.08:
            spd.append(round(150 + (cruise_kt - 150) * (f / 0.08)))
        elif f > 0.92:
            spd.append(round(150 + (cruise_kt - 150) * ((1 - f) / 0.08)))
        else:
            spd.append(cruise_kt)
    return elapsed, alt, spd


def hsl_hex(h, s, l):
    """h,s,l in [0,1] -> #rrggbb."""
    def hue(p, q, t):
        t %= 1
        if t < 1 / 6: return p + (q - p) * 6 * t
        if t < 1 / 2: return q
        if t < 2 / 3: return p + (q - p) * (2 / 3 - t) * 6
        return p
    q = l * (1 + s) if l < 0.5 else l + s - l * s
    p = 2 * l - q
    r, g, b = hue(p, q, h + 1 / 3), hue(p, q, h), hue(p, q, h - 1 / 3)
    return "#%02x%02x%02x" % (round(r * 255), round(g * 255), round(b * 255))


def build_layers():
    layers = []
    n = len(ROUTES)
    for i, (origin, dest) in enumerate(ROUTES):
        lon1, lat1 = AIRPORTS[origin]
        lon2, lat2 = AIRPORTS[dest]
        coords = great_circle(lon1, lat1, lon2, lat2, n=80)
        dist = haversine_km(lon1, lat1, lon2, lat2)
        elapsed, alt, spd = flight_profile(80, dist)
        color = hsl_hex((i / n) % 1.0, 0.58, 0.45)
        styles = ("solid", "dash", "dot", "long-dash", "long-dash-dot")
        layers.append(path_layer(
            [c[0] for c in coords], [c[1] for c in coords],
            # name=f"{origin} \u2192 {dest}",
            name=f"Phase_{i}",
            color=color, width=1.5, line_style=styles[i % len(styles)],
            elapsed_min=elapsed, alt_ft=alt, speed_kt=spd,
        ))

    # One filled polygon, via the dedicated polygon_layer helper. These vertices
    # are wound counter-clockwise, which we declare so Cartoplot orders the ring
    # for d3 and fills the enclosed area (not the rest of the globe).
    ring = [(-45, 40), (-15, 45), (-10, 60), (-50, 58)]
    # layers.append(polygon_layer(
    #     [p[0] for p in ring], [p[1] for p in ring],
    #     name="N. Atlantic watch area",
    #     color="#37506b", width=1.2, opacity=0.9, fill_opacity=0.12,
    #     winding="ccw",
    # ))
    return layers


def _assets_ready(assets_dir):
    """True when all four offline assets are present in assets_dir."""
    return all(os.path.exists(os.path.join(assets_dir, fn))
               for fn, _url in OFFLINE_ASSETS.values())


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    template = sys.argv[1] if len(sys.argv) > 1 else os.path.join(here, "cartoplot.html")
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(here, "cartoplot_demo.html")

    layers = build_layers()
    # Open with the legend shown (there are enough routes that it scrolls on a
    # short window) on an equirectangular 2:1 figure.
    config = {"type": "equirectangular", "showLegend": True, "showGraticule": True}

    # ---- 1. ONLINE figure -------------------------------------------------
    # The default build. Small file; pulls d3/topojson/atlas from a CDN when
    # opened, so it needs internet on first view.
    embed(template, layers, out, config=config)
    pts = sum(len(L["coordinates"]) for L in layers)
    print(f"Wrote {out}  (online: {len(layers)} layers, {pts} points)")

    # ---- 2. OFFLINE figure ------------------------------------------------
    # A fully self-contained build: d3 + topojson are inlined and the world-atlas
    # vectors are embedded, so the HTML opens with no network at all.
    #
    # Step one (run once, needs internet) populates an assets folder next to the
    # template; step two embeds from it. Here we auto-download if it's missing and
    # skip gracefully if there's no connection.
    assets_dir = os.path.join(here, ASSET_DIR_DEFAULT)
    offline_out = os.path.join(here, "cartoplot_demo_offline.html")

    if not _assets_ready(assets_dir):
        print(f"Fetching offline assets into {assets_dir}{os.sep} (needs internet)…")
        try:
            download_offline_assets(assets_dir)
        except Exception as e:                       # noqa: BLE001 — keep the demo runnable offline
            print(f"  could not download assets ({e.__class__.__name__}): {e}")

    if _assets_ready(assets_dir):
        embed(template, layers, offline_out, config=config, offline=True)
        size_mb = os.path.getsize(offline_out) / 1_048_576
        print(f"Wrote {offline_out}  (offline: self-contained, {size_mb:.1f} MB)")
    else:
        print("Skipped offline build — populate the assets folder first, e.g.:")
        print(f"    python -c \"import cartoplot_embed as c; c.download_offline_assets('{assets_dir}')\"")
        print("  (or drop d3.min.js, topojson.min.js, countries-110m.json and "
              "countries-50m.json in by hand — see OFFLINE_ASSETS for source URLs).")

    print(f"  template: {template}")


if __name__ == "__main__":
    main()
