"""cartoplot_embed.py — embed trajectory layers into a Cartoplot HTML file.

The Cartoplot HTML has an empty data block:

    <script type="application/json" id="cartoplot-data"></script>

This helper writes JSON into that block, producing a self-contained HTML figure.
You never hand-write the JSON — pass arrays or a DataFrame and it builds the spec.

Quick start
-----------
    from cartoplot_embed import path_layer, embed

    layers = [
        path_layer(lons, lats, name="Flight 123",
                   color="#c1572e", width=1.6,
                   time=timestamps, altitude=altitudes),  # extra fields -> tooltips
    ]
    embed("cartoplot.html", layers, "cartoplot_flight.html")

From a pandas DataFrame
-----------------------
    from cartoplot_embed import layer_from_dataframe, embed
    layer = layer_from_dataframe(df, lon="lon", lat="lat", name="Track A")
    embed("cartoplot.html", [layer], "out.html")

Schema (scoped to trajectory layers; wrapped in an object so config can be
added later without breaking existing files):

    { "layers": [
        { "type": "path",                      # "path" (line) or "polygon" (filled)
          "name": "Flight 123",
          "coordinates": [[lon, lat], ...],    # NOTE: [lon, lat] order
          "winding": "ccw",                    # polygons only: "ccw" (default) |
                                               # "cw" — declares your vertex order
                                               # so d3 fills the enclosed region
          "style": {"color": "#c1572e", "width": 1.6, "opacity": 1,
                    "markers": false, "fillOpacity": 0.25},
          "data": {"time": [...], "altitude": [...]} }   # columnar, parallel to coords
    ] }
"""
import json
import re


def path_layer(lons, lats, name=None, color=None, width=None, opacity=None,
               markers=False, polygon=False, **point_fields):
    """Build one layer from parallel lon/lat sequences.

    Any extra keyword arrays (e.g. time=..., altitude=..., speed=...) are stored
    per-point and shown in the hover tooltip. They must match the point count.
    """
    lons = [float(x) for x in lons]
    lats = [float(y) for y in lats]
    if len(lons) != len(lats):
        raise ValueError("lons and lats must be the same length")

    layer = {
        "type": "polygon" if polygon else "path",
        "coordinates": [[x, y] for x, y in zip(lons, lats)],
    }
    if name is not None:
        layer["name"] = name

    style = {}
    if color is not None:   style["color"] = color
    if width is not None:   style["width"] = width
    if opacity is not None: style["opacity"] = opacity
    if markers:             style["markers"] = True
    if style:
        layer["style"] = style

    if point_fields:
        data = {}
        for key, values in point_fields.items():
            values = list(values)
            if len(values) != len(lons):
                raise ValueError(f"point field '{key}' has {len(values)} values, "
                                 f"expected {len(lons)}")
            data[key] = values
        layer["data"] = data

    return layer


def polygon_layer(lons, lats, name=None, color=None, width=None, opacity=None,
                  fill_opacity=None, markers=False, winding="ccw", **point_fields):
    """Build a filled polygon layer from a ring of lon/lat vertices.

    Like path_layer, but the layer is type "polygon" and its interior is filled.
    `fill_opacity` (0..1) controls the fill alpha. Extra keyword arrays become
    per-vertex tooltip data.

    `winding` ("ccw" default, or "cw") declares the order of your vertices.
    Cartoplot orients the ring for d3-geo accordingly so the region your ring
    *encloses* is the one that fills — a "cw" ring is used as-is, a "ccw" ring is
    reversed internally. Declare the winding your vertices are actually in; "ccw"
    is the default because that matches standard GeoJSON exterior rings. (If you
    ever want the complementary region filled instead — e.g. an area larger than
    a hemisphere — declare the opposite of your true winding.)
    """
    if winding not in ("cw", "ccw"):
        raise ValueError("winding must be 'cw' or 'ccw'")
    layer = path_layer(lons, lats, name=name, color=color, width=width,
                       opacity=opacity, markers=markers, polygon=True,
                       **point_fields)
    layer["winding"] = winding
    if fill_opacity is not None:
        layer.setdefault("style", {})["fillOpacity"] = fill_opacity
    return layer


def layer_from_dataframe(df, lon="lon", lat="lat", name=None, color=None,
                         width=None, extra=None, polygon=False):
    """Build a layer from a pandas DataFrame.

    Every column other than the lon/lat columns becomes per-point tooltip data,
    unless `extra` is given to restrict which columns to include.
    """
    cols = extra if extra is not None else [c for c in df.columns if c not in (lon, lat)]
    return path_layer(df[lon], df[lat], name=name, color=color, width=width,
                      polygon=polygon, **{c: df[c] for c in cols})


_BLOCK = re.compile(
    r'(<script type="application/json" id="cartoplot-data">)(.*?)(</script>)', re.S)


def embed(template_path, layers, out_path=None, config=None):
    """Inject `layers` into the Cartoplot template and write `out_path`.

    If out_path is omitted, the template is overwritten in place.

    `config` (optional dict) sets the figure's opening state — any of:
    type, res, rotate, bounds, showBorders, showGraticule, graticuleStep,
    plotAspect, plotSize, color, showLegend. Only the keys you pass are applied;
    everything else falls back to the figure's defaults.
    """
    with open(template_path, encoding="utf-8") as f:
        html = f.read()
    if not _BLOCK.search(html):
        raise ValueError("Could not find the <script id=\"cartoplot-data\"> block "
                         "in the template — is this a Cartoplot HTML file?")
    spec = {"layers": list(layers)}
    if config:
        spec["config"] = config
    # Compact JSON; escape '<' so an embedded string can never close the tag.
    payload = json.dumps(spec, separators=(",", ":")).replace("<", r"\u003c")
    html = _BLOCK.sub(lambda m: m.group(1) + payload + m.group(3), html, count=1)
    out_path = out_path or template_path
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    return out_path


if __name__ == "__main__":
    # Tiny demo: a great-circle-ish flight path NYC -> London with altitude.
    import math
    lons, lats, alt, t = [], [], [], []
    for k in range(25):
        f = k / 24
        lons.append(-73.8 + (-0.1 - (-73.8)) * f)
        lats.append(40.6 + (51.5 - 40.6) * f + 6 * math.sin(math.pi * f))  # arc-ish
        alt.append(round(11000 * math.sin(math.pi * f)))
        t.append(f"T+{int(f*7*60)}min")
    demo = path_layer(lons, lats, name="NYC -> LHR", color="#c1572e", width=1.8,
                      time=t, altitude=alt)
    embed("cartoplot.html", [demo], "cartoplot_demo.html")
    print("wrote cartoplot_demo.html")
