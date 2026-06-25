"""Embed 2-D series layers into a Plot2D HTML figure.

A Plot2D template contains an empty data block::

    <script type="application/json" id="plot2d-data"></script>

This module builds layer specs from a pandas DataFrame (or plain arrays) and
writes them into that block, producing a self-contained HTML figure. You never
hand-write the JSON.

Each layer carries a set of *named series* (parallel arrays) — for example
``time``, ``altitude``, ``velocity``. The figure lets the viewer choose which
series map to the x and y axes (defaulting to the first two), apply per-axis
scale multipliers, and set manual axis limits.

Quick start (DataFrame — the primary path)::

    from d3_2d_plot_embed import layer_from_dataframe, embed

    layer = layer_from_dataframe(df, name="Ascent")     # all columns become series
    embed("d3_2d_plot.html", [layer], "plot2d_ascent.html",
          config={"xKey": "time", "yKey": "altitude"})

From plain arrays::

    from d3_2d_plot_embed import path_layer, series_layer, embed

    a = path_layer(time, altitude, x_name="time", y_name="altitude",
                   name="Track A", velocity=vel)         # extra series too
    b = series_layer(name="Track B", time=t2, altitude=h2, velocity=v2)
    embed("d3_2d_plot.html", [a, b], "out.html")

Layer schema (built for you by the helpers; shown for reference)::

    { "layers": [
        { "name": "Ascent",
          "series": {"time": [...], "altitude": [...], "velocity": [...]},
          "style": {"color": "#c1572e", "width": 1.6, "opacity": 1,
                    "markers": false, "markerSize": 2,
                    "dash": "dash",              # solid|dash|dot|long-dash|long-dash-dot
                    "visible": true} }
    ] }
"""
import json
import os
import re
import urllib.request


_LINE_STYLES = ("solid", "dash", "dot", "long-dash", "long-dash-dot")
_RESERVED = {"series", "name", "color", "width", "opacity", "markers",
             "marker_size", "line_style"}


def _build_style(color, width, opacity, markers, marker_size, line_style):
    """Assemble a style dict, omitting unset fields so the figure can default.

    Args:
        color (str or None): CSS colour for the line.
        width (float or None): Line width in pixels.
        opacity (float or None): Stroke opacity in [0, 1].
        markers (bool): Draw a dot at every point.
        marker_size (float or None): Marker radius in pixels.
        line_style (str): One of :data:`_LINE_STYLES`.

    Returns:
        dict: The style block (possibly empty).

    Raises:
        ValueError: If ``line_style`` is unknown.
    """
    if line_style not in _LINE_STYLES:
        raise ValueError(f"line_style must be one of {_LINE_STYLES}")
    style = {}
    if color is not None:       style["color"] = color
    if width is not None:       style["width"] = width
    if opacity is not None:     style["opacity"] = opacity
    if markers:                 style["markers"] = True
    if marker_size is not None: style["markerSize"] = marker_size
    if line_style != "solid":   style["dash"] = line_style
    return style


def _clean_series(mapping):
    """Coerce a mapping of name -> sequence into JSON-ready float arrays.

    Args:
        mapping (dict): Series name -> sequence of numbers.

    Returns:
        dict: Series name -> list of floats.

    Raises:
        ValueError: If fewer than one series is given, or the series are not all
            the same length (they must be parallel arrays).
    """
    series = {}
    for key, values in mapping.items():
        series[str(key)] = [float(v) for v in values]
    if not series:
        raise ValueError("a layer needs at least one named series")
    lengths = {len(v) for v in series.values()}
    if len(lengths) > 1:
        raise ValueError(f"all series in a layer must be the same length, got {sorted(lengths)}")
    return series


def series_layer(series=None, name=None, color=None, width=None, opacity=None,
                 markers=False, marker_size=None, line_style="solid", **named_series):
    """Build a layer from named series arrays.

    Provide the series either as a single ``series`` dict (best when names might
    collide with the style keywords) or as keyword arrays, for example
    ``series_layer(time=t, altitude=alt, velocity=v, name="Ascent")``. All series
    must be the same length. The figure lets the viewer choose which series map
    to the x and y axes.

    Args:
        series (dict, optional): Mapping of series name -> sequence of numbers.
        name (str, optional): Layer name shown in the legend and tooltip.
        color (str, optional): CSS colour for the line. If omitted, the figure
            auto-assigns a palette colour.
        width (float, optional): Line width in pixels.
        opacity (float, optional): Stroke opacity in [0, 1].
        markers (bool): Draw a dot at every point. Defaults to False.
        marker_size (float, optional): Marker radius in pixels.
        line_style (str): One of ``"solid"`` (default), ``"dash"``, ``"dot"``,
            ``"long-dash"`` or ``"long-dash-dot"``.
        **named_series (Sequence): Series passed as keyword arrays. Merged with
            ``series`` (explicit ``series`` keys win on conflict).

    Returns:
        dict: A layer spec ready to pass to :func:`embed`.

    Raises:
        ValueError: If no series are given, the series differ in length, or
            ``line_style`` is unknown.
    """
    merged = dict(named_series)
    if series:
        merged.update(series)
    layer = {"series": _clean_series(merged)}
    if name is not None:
        layer["name"] = name
    style = _build_style(color, width, opacity, markers, marker_size, line_style)
    if style:
        layer["style"] = style
    return layer


def path_layer(x, y, name=None, x_name="x", y_name="y", color=None, width=None,
               opacity=None, markers=False, marker_size=None, line_style="solid",
               **extra_series):
    """Convenience builder for a single x-vs-y line.

    ``x`` and ``y`` are stored as named series (``x_name`` and ``y_name``), and
    any extra keyword arrays are added as further series the viewer can switch
    an axis to. This is just :func:`series_layer` with two of the series named
    for you.

    Args:
        x (Sequence[float]): Values for the default x series.
        y (Sequence[float]): Values for the default y series. Same length as ``x``.
        name (str, optional): Layer name shown in the legend and tooltip.
        x_name (str): Series name to store ``x`` under. Defaults to ``"x"``.
        y_name (str): Series name to store ``y`` under. Defaults to ``"y"``.
        color (str, optional): CSS colour for the line.
        width (float, optional): Line width in pixels.
        opacity (float, optional): Stroke opacity in [0, 1].
        markers (bool): Draw a dot at every point. Defaults to False.
        marker_size (float, optional): Marker radius in pixels.
        line_style (str): Line style; see :func:`series_layer`.
        **extra_series (Sequence): Additional named series (each the same length
            as ``x``).

    Returns:
        dict: A layer spec ready to pass to :func:`embed`.

    Raises:
        ValueError: If ``x_name`` equals ``y_name``, or validation from
            :func:`series_layer` fails.
    """
    if x_name == y_name:
        raise ValueError("x_name and y_name must differ")
    data = {x_name: x, y_name: y}
    data.update(extra_series)
    return series_layer(series=data, name=name, color=color, width=width,
                        opacity=opacity, markers=markers, marker_size=marker_size,
                        line_style=line_style)


def layer_from_dataframe(df, name=None, columns=None, color=None, width=None,
                         opacity=None, markers=False, marker_size=None,
                         line_style="solid"):
    """Build a layer from a pandas DataFrame.

    Every column (or the subset named in ``columns``) becomes a series, so the
    viewer can map any column to either axis. This is the primary way to feed
    data in: a DataFrame *is* a table of named, parallel series.

    Args:
        df (pandas.DataFrame): Source frame. Columns must be numeric.
        name (str, optional): Layer name shown in the legend and tooltip.
        columns (Sequence[str], optional): Columns to include, in order. If
            omitted, all columns are used (the first two become the default x
            and y axes).
        color (str, optional): CSS colour for the line.
        width (float, optional): Line width in pixels.
        opacity (float, optional): Stroke opacity in [0, 1].
        markers (bool): Draw a dot at every point. Defaults to False.
        marker_size (float, optional): Marker radius in pixels.
        line_style (str): Line style; see :func:`series_layer`.

    Returns:
        dict: A layer spec ready to pass to :func:`embed`.

    Raises:
        ValueError: If validation from :func:`series_layer` fails.
    """
    cols = list(columns) if columns is not None else list(df.columns)
    series = {str(c): list(df[c]) for c in cols}
    return series_layer(series=series, name=name, color=color, width=width,
                        opacity=opacity, markers=markers, marker_size=marker_size,
                        line_style=line_style)


_BLOCK = re.compile(
    r'(<script type="application/json" id="plot2d-data">)(.*?)(</script>)', re.S)

# ---------------------------------------------------------------------------
# Offline support
#
# Online, the template loads d3 from a CDN. A 2-D plot needs no basemap, so an
# offline (fully self-contained) figure only has to inline the one library —
# there is no atlas to embed. The asset lives in a folder you populate once
# (download_offline_assets, which needs internet) or fill in by hand.
# ---------------------------------------------------------------------------
ASSET_DIR_DEFAULT = "d3_2d_plot_assets"

# logical name -> (local filename, CDN url). The d3 version must match the
# template's CDN <script> tag so the offline build behaves identically.
OFFLINE_ASSETS = {
    "d3": ("d3.min.js", "https://cdnjs.cloudflare.com/ajax/libs/d3/7.9.0/d3.min.js"),
}

_LIBS_BLOCK = re.compile(r"<!-- plot2d:libs.*?-->.*?<!-- /plot2d:libs -->", re.S)


def download_offline_assets(dest_dir=ASSET_DIR_DEFAULT, overwrite=False):
    """Download the offline asset (d3) so figures can be fully self-contained.

    Fetches the entries in :data:`OFFLINE_ASSETS` into ``dest_dir`` so that
    ``embed(..., offline=True)`` needs no network. Run this once on a machine
    with internet; the file may also be placed in ``dest_dir`` by hand.

    Args:
        dest_dir (str): Folder to populate, created if missing. Defaults to
            :data:`ASSET_DIR_DEFAULT`.
        overwrite (bool): Re-fetch files that already exist. Defaults to False.

    Returns:
        str: ``dest_dir``.

    Raises:
        urllib.error.URLError: If a download fails (for example, no internet).
    """
    os.makedirs(dest_dir, exist_ok=True)
    for _name, (fn, url) in OFFLINE_ASSETS.items():
        dest = os.path.join(dest_dir, fn)
        if os.path.exists(dest) and not overwrite:
            continue
        req = urllib.request.Request(url, headers={"User-Agent": "d3-2d-plot-offline/1.0"})
        with urllib.request.urlopen(req, timeout=60) as r:
            data = r.read()
        with open(dest, "wb") as f:
            f.write(data)
    return dest_dir


def _read_asset(assets_dir, filename):
    """Read an offline asset's text, with a helpful error if it is missing.

    Args:
        assets_dir (str): Folder holding the offline assets.
        filename (str): Asset file name within ``assets_dir``.

    Returns:
        str: The file's UTF-8 text.

    Raises:
        FileNotFoundError: If the asset is absent, with guidance on obtaining it.
    """
    path = os.path.join(assets_dir, filename)
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Offline asset missing: {path}\n"
            f"Run download_offline_assets({assets_dir!r}) on a machine with internet, "
            f"or place the file there yourself (see OFFLINE_ASSETS for the source URL).")
    with open(path, encoding="utf-8") as f:
        return f.read()


def _inline_libraries(html, assets_dir):
    """Replace the template's CDN library block with an inline ``<script>``.

    Args:
        html (str): Template HTML.
        assets_dir (str): Folder holding ``d3.min.js``.

    Returns:
        str: HTML with d3 inlined.

    Raises:
        ValueError: If the ``plot2d:libs`` marker block is absent.
        FileNotFoundError: If the d3 asset is missing.
    """
    d3_js = _read_asset(assets_dir, OFFLINE_ASSETS["d3"][0])
    # A literal </script> inside library text would close the tag early; neutralise it.
    esc = d3_js.replace("</script>", r"<\/script>")
    inline = ("<!-- plot2d:libs (inlined for offline use) -->\n"
              "<script>" + esc + "</script>\n"
              "<!-- /plot2d:libs -->")
    if not _LIBS_BLOCK.search(html):
        raise ValueError("libs marker block not found — template too old for offline embedding.")
    return _LIBS_BLOCK.sub(lambda m: inline, html, count=1)


def embed(template_path, layers, out_path=None, config=None,
          offline=False, assets_dir=ASSET_DIR_DEFAULT):
    """Inject series layers into a Plot2D template and write the figure.

    Args:
        template_path (str): Path to a Plot2D HTML template (the file containing
            the empty ``plot2d-data`` block).
        layers (Sequence[dict]): Layer specs from :func:`series_layer`,
            :func:`path_layer`, or :func:`layer_from_dataframe`.
        out_path (str, optional): Where to write the result. If omitted, the
            template is overwritten in place.
        config (dict, optional): Opening figure state. Recognised keys:
            ``xKey``/``yKey`` (series names for the axes; default first/second),
            ``xMult``/``yMult`` (display multipliers), ``xUnit``/``yUnit`` (unit
            labels appended to the axis titles), ``xlim``/``ylim`` (``[min, max]``
            in display units, i.e. after the multiplier; omit for auto-fit),
            ``showGrid``, ``plotSize``, ``color`` (``{"grid": ..., "axis": ...}``),
            ``showLegend``, ``theme`` (``"light"`` or ``"dark"``) and
            ``legendLoc``. ``legendLoc`` is the legend placement: a named string
            — ``"right-outside"`` or ``"left-outside"`` (reserves a strip beside
            the plot), or an inside corner (``"top-left"``, ``"top-right"``,
            ``"bottom-left"``, ``"bottom-right"``) — or a normalized ``[x, y]``
            top-left relative to the plot box for a free placement. Only the keys
            you pass are applied. Passing ``theme="dark"`` without an explicit
            ``color`` also switches the grid/axis palette to the dark preset;
            series colours are never changed.
        offline (bool or str): Make the output fully self-contained (no network
            at view time) by inlining d3. ``True`` uses ``assets_dir``; a path
            string uses that folder instead. Populate the folder once with
            :func:`download_offline_assets`.
        assets_dir (str): Folder of offline assets, used when ``offline`` is set.
            Defaults to :data:`ASSET_DIR_DEFAULT`.

    Returns:
        str: The path written (``out_path``, or ``template_path`` if overwritten).

    Raises:
        ValueError: If the template lacks the ``plot2d-data`` block.
        FileNotFoundError: If ``offline`` is requested but an asset is missing.
    """
    with open(template_path, encoding="utf-8") as f:
        html = f.read()
    if not _BLOCK.search(html):
        raise ValueError("Could not find the <script id=\"plot2d-data\"> block "
                         "in the template — is this a Plot2D HTML file?")
    spec = {"layers": list(layers)}
    if config:
        spec["config"] = config
    # Compact JSON; escape '<' so an embedded string can never close the tag.
    payload = json.dumps(spec, separators=(",", ":")).replace("<", r"\u003c")
    html = _BLOCK.sub(lambda m: m.group(1) + payload + m.group(3), html, count=1)

    if offline:
        adir = offline if isinstance(offline, str) else assets_dir
        html = _inline_libraries(html, adir)

    out_path = out_path or template_path
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    return out_path


if __name__ == "__main__":
    # Tiny demo: a projectile arc with several series (time, x, height, speed).
    import math
    g, v0, ang = 9.81, 90.0, math.radians(55)
    vx, vy = v0 * math.cos(ang), v0 * math.sin(ang)
    flight = 2 * vy / g
    t = [flight * k / 60 for k in range(61)]
    x = [vx * tk for tk in t]
    h = [vy * tk - 0.5 * g * tk * tk for tk in t]
    spd = [math.hypot(vx, vy - g * tk) for tk in t]
    demo = series_layer(name="Projectile", color="#c1572e", width=1.8,
                        time=t, downrange=x, height=h, speed=spd)
    embed("d3_2d_plot.html", [demo], "d3_2d_plot_demo.html",
          config={"xKey": "downrange", "yKey": "height", "showLegend": True})
    print("wrote d3_2d_plot_demo.html")
