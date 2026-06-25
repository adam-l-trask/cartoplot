#!/usr/bin/env python3
"""d3_2d_plot_demo.py — minimal, readable example of building a Plot2D figure.

It shows the public surface of d3_2d_plot_embed:

  * layer_from_dataframe() — a layer straight from a pandas DataFrame (primary)
  * series_layer()         — a layer from named arrays (no pandas needed)
  * embed()                — bake layers into the HTML template (online build)
  * download_offline_assets() + embed(offline=...) — a self-contained build

The demo plots two projectile trajectories. Each layer carries several named
series — time, downrange, altitude, speed — so in the figure you can switch
either axis between them (try downrange-vs-altitude for the flight profile, or
time-vs-altitude), apply a scale multiplier (e.g. the m -> ft preset on the
altitude axis), and set manual axis limits.

Usage:
    python d3_2d_plot_demo.py                          # ./d3_2d_plot.html -> ./d3_2d_plot_demo.html
    python d3_2d_plot_demo.py d3_2d_plot.html out.html # explicit template / output

Standard library only (pandas is used if present, otherwise a fallback path is
taken). Writes an online figure always, and an offline, fully self-contained
figure when the offline asset (d3) is available.
"""
import math
import os
import sys

# Import the sibling helper regardless of the current working directory.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from d3_2d_plot_embed import (series_layer, layer_from_dataframe, embed,
                              download_offline_assets, ASSET_DIR_DEFAULT)

G = 9.81  # m/s^2

# Two launches at the same speed, different angles -> two legend entries.
LAUNCHES = [
    {"name": "45\u00b0 launch", "speed": 95.0, "angle_deg": 45, "color": "#c1572e", "dash": "solid"},
    {"name": "60\u00b0 launch", "speed": 95.0, "angle_deg": 60, "color": "#2f6f9e", "dash": "dash"},
]


def trajectory(speed, angle_deg, n=80):
    """Sample a drag-free projectile flight.

    Args:
        speed (float): Launch speed in m/s.
        angle_deg (float): Launch angle above horizontal, in degrees.
        n (int): Number of samples along the flight.

    Returns:
        dict: Parallel series ``time`` (s), ``downrange`` (m), ``altitude`` (m),
        ``speed`` (m/s).
    """
    ang = math.radians(angle_deg)
    vx, vy = speed * math.cos(ang), speed * math.sin(ang)
    flight = 2 * vy / G
    t = [flight * k / n for k in range(n + 1)]
    return {
        "time":      t,
        "downrange": [vx * tk for tk in t],
        "altitude":  [vy * tk - 0.5 * G * tk * tk for tk in t],
        "speed":     [math.hypot(vx, vy - G * tk) for tk in t],
    }


def build_layers():
    """Build the demo's two trajectory layers.

    Uses :func:`layer_from_dataframe` when pandas is available (the primary,
    DataFrame-first path) and falls back to :func:`series_layer` otherwise. Both
    produce the same layer spec.
    """
    try:
        import pandas as pd
        use_df = True
    except ImportError:
        use_df = False

    layers = []
    for spec in LAUNCHES:
        s = trajectory(spec["speed"], spec["angle_deg"])
        if use_df:
            import pandas as pd
            # A DataFrame IS a table of named, parallel series — column order sets
            # the default axes (here: downrange -> x, altitude -> y).
            df = pd.DataFrame({"downrange": s["downrange"], "altitude": s["altitude"],
                               "time": s["time"], "speed": s["speed"]})
            layers.append(layer_from_dataframe(
                df, name=spec["name"], color=spec["color"],
                width=1.8, line_style=spec["dash"]))
        else:
            layers.append(series_layer(
                name=spec["name"], color=spec["color"], width=1.8,
                line_style=spec["dash"],
                downrange=s["downrange"], altitude=s["altitude"],
                time=s["time"], speed=s["speed"]))
    return layers


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    template = sys.argv[1] if len(sys.argv) > 1 else os.path.join(here, "d3_2d_plot.html")
    out      = sys.argv[2] if len(sys.argv) > 2 else os.path.join(here, "d3_2d_plot_demo.html")

    layers = build_layers()
    # Open on the flight profile (downrange vs altitude) with the legend shown.
    config = {"xKey": "downrange", "yKey": "altitude", "showLegend": True}

    # 1) Online figure — small file; fetches d3 from a CDN on open.
    embed(template, layers, out, config=config)
    print(f"online  -> {out}  ({len(layers)} layers)")

    # 2) Offline figure — fully self-contained (opens with no network). Populate
    #    the assets folder once (needs internet); thereafter it inlines from disk.
    assets_dir  = os.path.join(here, ASSET_DIR_DEFAULT)
    offline_out = os.path.join(here, "d3_2d_plot_demo_offline.html")
    try:
        download_offline_assets(assets_dir)   # no-op once d3.min.js is present
        embed(template, layers, offline_out, config=config, offline=assets_dir)
        print(f"offline -> {offline_out}  (self-contained)")
    except Exception as e:                     # offline with assets not yet downloaded
        print(f"offline -> skipped ({e.__class__.__name__}: {e})")
        print("           populate the asset once with internet:")
        print(f"           python -c \"import d3_2d_plot_embed as c; "
              f"c.download_offline_assets('{ASSET_DIR_DEFAULT}')\"")


if __name__ == "__main__":
    main()
