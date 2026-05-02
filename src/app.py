from flask import Flask, render_template_string, request
import folium
import json
import pandas as pd
import unicodedata
import copy
import os
import math
from branca.colormap import linear
from branca.element import MacroElement, Template

app = Flask(__name__)

def normalize_name(name):
    if not isinstance(name, str):
        return ""
    name = unicodedata.normalize("NFKD", name).encode("ASCII", "ignore").decode("ASCII")
    return name.lower().replace("-", " ").strip()

BASE_DIR = os.path.dirname(os.path.dirname(__file__))  # points to Dengue_Map/
DATA_DIR = os.path.join(BASE_DIR, "data")


geojson_file = os.path.join(DATA_DIR, "RJ.json")
CASES_FILE = os.path.join(DATA_DIR, "cases.csv")
TEMP_FILE = os.path.join(DATA_DIR, "temperature.csv")
HUMID_FILE = os.path.join(DATA_DIR, "humidity.csv")
RAIN_FILE = os.path.join(DATA_DIR, "rainfall.csv")
POP_FILE = os.path.join(DATA_DIR, "population.csv")
IDHM_FILE = os.path.join(DATA_DIR, "idhm.csv")


with open(geojson_file, "r", encoding="utf-8") as f:
    base_geo_data = json.load(f)

name_corrections = {
    "parati": "paraty",
    "niteroi": "niteroi",
    "sao goncalo": "sao goncalo",
    "nova iguacu": "nova iguacu",
    "mesquita": "mesquita",
    "trajanode morais": "trajano de moraes",
    "areal": "areal",
}

def load_csv_all(file, value_column):
    df = pd.read_csv(file, encoding="utf-8-sig")
    df.columns = [c.lower().strip() for c in df.columns]

    if "municipio" not in df.columns or "year" not in df.columns or "week" not in df.columns:
        raise ValueError(f"CSV {file} missing required columns")

    df["municipio_norm"] = df["municipio"].apply(normalize_name)
    d = {}

    for _, r in df.iterrows():
        try:
            key = (r["municipio_norm"], int(r["year"]), int(r["week"]))
            d[key] = float(r.get(value_column, 0))
        except:
            continue

    return d

def load_population_csv():
    df = pd.read_csv(POP_FILE, encoding="utf-8-sig")
    df.columns = [c.lower().strip() for c in df.columns]
    df = df.dropna(subset=["municipio", "population"])
    return dict(zip(df["municipio"].apply(normalize_name), df["population"].astype(float)))

def load_idhm_csv():
    df = pd.read_csv(IDHM_FILE, encoding="utf-8-sig")
    df.columns = [c.lower().strip() for c in df.columns]
    df = df.dropna(subset=["municipio", "idhm"])
    return dict(zip(df["municipio"].apply(normalize_name), df["idhm"].astype(float)))

class PublicationMapElements(MacroElement):
    def __init__(self):
        super().__init__()
        self._template = Template("""
        {% macro script(this, kwargs) %}
        var map = {{this._parent.get_name()}};

        function formatLon(lon) {
            var absVal = Math.abs(lon);
            var deg = Math.floor(absVal);
            var min = Math.round((absVal - deg) * 60);
            if (min === 60) {
                deg += 1;
                min = 0;
            }
            return deg + "°" + String(min).padStart(2, "0") + "'" + (lon < 0 ? "W" : "E");
        }

        function formatLat(lat) {
            var absVal = Math.abs(lat);
            var deg = Math.floor(absVal);
            var min = Math.round((absVal - deg) * 60);
            if (min === 60) {
                deg += 1;
                min = 0;
            }
            return deg + "°" + String(min).padStart(2, "0") + "'" + (lat < 0 ? "S" : "N");
        }

        function niceNumber(value) {
            var exponent = Math.floor(Math.log10(value));
            var fraction = value / Math.pow(10, exponent);
            var niceFraction;

            if (fraction <= 1) {
                niceFraction = 1;
            } else if (fraction <= 2) {
                niceFraction = 2;
            } else if (fraction <= 5) {
                niceFraction = 5;
            } else {
                niceFraction = 10;
            }

            return niceFraction * Math.pow(10, exponent);
        }

        function metersPerPixelAtLatitude(lat, zoom) {
            return 156543.03392 * Math.cos(lat * Math.PI / 180) / Math.pow(2, zoom);
        }

        function drawPublicationElements() {
            var container = map.getContainer();

            container.querySelectorAll(
                ".pub-coord-label, .pub-tick, .pub-scale-wrapper"
            ).forEach(function(el) {
                el.remove();
            });

            var size = map.getSize();
            var bounds = map.getBounds();

            var bottomTicks = 5;
            for (var i = 0; i < bottomTicks; i++) {
                var ratio = i / (bottomTicks - 1);
                var lon = bounds.getWest() + ratio * (bounds.getEast() - bounds.getWest());
                var point = map.latLngToContainerPoint([bounds.getSouth(), lon]);

                var tick = document.createElement("div");
                tick.className = "pub-tick pub-bottom-tick";
                tick.style.left = point.x + "px";
                tick.style.bottom = "-10px";
                container.appendChild(tick);

                var label = document.createElement("div");
                label.className = "pub-coord-label pub-bottom-label";
                label.innerHTML = formatLon(lon);
                label.style.left = point.x + "px";
                label.style.bottom = "-38px";
                container.appendChild(label);
            }

            var rightTicks = 5;
            for (var j = 0; j < rightTicks; j++) {
                var ratioY = j / (rightTicks - 1);
                var lat = bounds.getSouth() + ratioY * (bounds.getNorth() - bounds.getSouth());
                var pointY = map.latLngToContainerPoint([lat, bounds.getEast()]);

                var tickY = document.createElement("div");
                tickY.className = "pub-tick pub-right-tick";
                tickY.style.top = pointY.y + "px";
                tickY.style.right = "-10px";
                container.appendChild(tickY);

                var labelY = document.createElement("div");
                labelY.className = "pub-coord-label pub-right-label";
                labelY.innerHTML = formatLat(lat);
                labelY.style.top = pointY.y + "px";
                labelY.style.right = "-78px";
                container.appendChild(labelY);
            }

            var center = map.getCenter();
            var mpp = metersPerPixelAtLatitude(center.lat, map.getZoom());
            var targetPx = 340;
            var rawKm = (mpp * targetPx) / 1000;
            var scaleKm = niceNumber(rawKm);
            var scalePx = (scaleKm * 1000) / mpp;

            var wrapper = document.createElement("div");
            wrapper.className = "pub-scale-wrapper";

            var bar = document.createElement("div");
            bar.className = "pub-scale-bar";
            bar.style.width = scalePx + "px";

            for (var s = 0; s < 4; s++) {
                var seg = document.createElement("div");
                seg.className = "pub-scale-segment";
                seg.style.width = (scalePx / 4) + "px";
                seg.style.background = s % 2 === 0 ? "#111" : "#fff";
                bar.appendChild(seg);
            }

            var labels = document.createElement("div");
            labels.className = "pub-scale-labels";
            labels.style.width = scalePx + "px";

            var values = [0, scaleKm / 4, scaleKm / 2, 3 * scaleKm / 4, scaleKm];
            for (var k = 0; k < values.length; k++) {
                var lab = document.createElement("span");
                lab.innerHTML = values[k] % 1 === 0 ? values[k].toFixed(0) : values[k].toFixed(1);
                lab.style.left = (k * scalePx / 4) + "px";
                labels.appendChild(lab);
            }

            var unit = document.createElement("div");
            unit.className = "pub-scale-unit";
            unit.innerHTML = "Kilometers";
            unit.style.left = (scalePx + 8) + "px";

            wrapper.appendChild(bar);
            wrapper.appendChild(labels);
            wrapper.appendChild(unit);
            container.appendChild(wrapper);
        }

        L.Control.NorthArrow = L.Control.extend({
            onAdd: function(map) {
                var div = L.DomUtil.create("div", "pub-north-arrow");
                div.innerHTML = `
                    <div class="pub-north-letter">N</div>
                    <svg width="70" height="94" viewBox="0 0 70 94">
                        <polygon points="35,4 55,74 35,55 15,74" fill="black" stroke="black" stroke-width="1"/>
                        <polygon points="35,14 44,62 35,50" fill="white"/>
                    </svg>
                `;
                return div;
            }
        });

        L.control.northArrow = function(opts) {
            return new L.Control.NorthArrow(opts);
        };

        L.control.northArrow({ position: "topright" }).addTo(map);

        map.whenReady(drawPublicationElements);
        map.on("moveend zoomend resize", drawPublicationElements);
        {% endmacro %}
        """)

cases_dict = load_csv_all(CASES_FILE, "cases")
temperature_dict = load_csv_all(TEMP_FILE, "temperature")
humidity_dict = load_csv_all(HUMID_FILE, "humidity")
rainfall_dict = load_csv_all(RAIN_FILE, "rainfall")

population_dict = load_population_csv()
idhm_dict = load_idhm_csv()

@app.route("/", methods=["GET"])
def index():
    week = int(request.args.get("week", 1))
    year = int(request.args.get("year", 2021))
    metric = request.args.get("metric", "cases")

    geo_data = copy.deepcopy(base_geo_data)

    metric_sources = {
        "cases": cases_dict,
        "temperature": temperature_dict,
        "humidity": humidity_dict,
        "rainfall": rainfall_dict,
    }

    prop_map = {
        "cases": "log_cases",
        "temperature": "temperature",
        "humidity": "humidity",
        "rainfall": "rainfall",
        "idhm": "idhm",
    }

    for feature in geo_data["features"]:
        name_geo = feature["properties"]["NOME"]
        name_norm = normalize_name(name_geo)
        name_norm = normalize_name(name_corrections.get(name_norm, name_norm))

        if metric == "idhm":
            feature["properties"]["idhm"] = idhm_dict.get(name_norm, 0)
            continue

        if metric == "cases":
            raw_cases = metric_sources["cases"].get((name_norm, year, week), 0)
            feature["properties"]["raw_cases"] = raw_cases
            feature["properties"]["log_cases"] = math.log1p(raw_cases)
            continue

        val = metric_sources[metric].get((name_norm, year, week), 0)
        feature["properties"][metric] = val

    prop = prop_map[metric]

    vals = [
        f["properties"].get(prop, 0)
        for f in geo_data["features"]
        if f["properties"].get(prop, 0) != 0
    ]

    vmin, vmax = (min(vals), max(vals)) if vals else (0, 1)
    if vmin == vmax:
        vmin = 0

    colormap = linear.YlOrRd_09.scale(vmin, vmax)

    if metric == "cases":
        colormap.caption = f"Log-scaled cases (Week {week}/{year})"
    else:
        colormap.caption = f"{metric.capitalize()} (Week {week}/{year})"

    def style_function(feature):
        val = feature["properties"].get(prop, 0)

        if metric != "cases" and val == 0:
            return {
                "fillColor": "#C0C0C0",
                "color": "black",
                "weight": 0.6,
                "fillOpacity": 0.78,
            }

        return {
            "fillColor": colormap(val),
            "color": "black",
            "weight": 0.6,
            "fillOpacity": 0.78,
        }

    fields = ["NOME"]
    aliases = ["Municipality:"]

    if metric == "cases":
        fields += ["raw_cases"]
        aliases += ["Cases:"]
    else:
        fields += [prop]
        aliases += [metric.capitalize() + ":"]

    m = folium.Map(
        location=[-22.9, -43.2],
        zoom_start=8,
        tiles="cartodbpositron",
        zoom_control=False,
        control_scale=False,
    )

    folium.GeoJson(
        geo_data,
        style_function=style_function,
        tooltip=folium.GeoJsonTooltip(fields=fields, aliases=aliases, localize=True),
    ).add_to(m)

    colormap.add_to(m)
    m.add_child(PublicationMapElements())

    m.get_root().html.add_child(folium.Element("""
    <style>
    html, body {
        margin: 0;
        padding: 0;
        width: 100%;
        height: 100%;
        background: #ffffff;
        overflow: hidden;
        font-family: Arial, sans-serif;
    }

    #map {
        position: fixed;
        left: 24px;
        top: 24px;
        width: calc(100vw - 138px);
        height: calc(100vh - 92px);
        border: 3px solid #111;
        box-sizing: border-box;
        background: white;
        overflow: visible !important;
    }

    .leaflet-container {
        background: white !important;
        overflow: visible !important;
        font-family: Arial, sans-serif;
    }

    .leaflet-control-attribution {
        font-size: 10px !important;
        background: rgba(255, 255, 255, 0.75) !important;
    }

    .pub-north-arrow {
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
        text-align: center;
        margin-top: 14px !important;
        margin-right: 22px !important;
    }

    .pub-north-letter {
        font-size: 26px;
        font-weight: 700;
        line-height: 24px;
        color: #111;
    }

    .pub-tick {
        position: absolute;
        background: #111;
        z-index: 900;
        pointer-events: none;
    }

    .pub-bottom-tick {
        width: 2px;
        height: 12px;
        transform: translateX(-1px);
    }

    .pub-right-tick {
        width: 12px;
        height: 2px;
        transform: translateY(-1px);
    }

    .pub-coord-label {
        position: absolute;
        z-index: 901;
        pointer-events: none;
        color: #111;
        background: white;
        font-size: 14px;
        font-weight: 600;
        line-height: 16px;
        white-space: nowrap;
    }

    .pub-bottom-label {
        transform: translateX(-50%);
    }

    .pub-right-label {
        transform: translateY(-50%);
    }

    .pub-scale-wrapper {
        position: absolute;
        left: 58px;
        bottom: 48px;
        z-index: 950;
        pointer-events: none;
        color: #111;
        font-family: Arial, sans-serif;
    }

    .pub-scale-bar {
        height: 16px;
        display: flex;
        border: 2px solid #111;
        box-sizing: border-box;
        background: white;
    }

    .pub-scale-segment {
        height: 100%;
        box-sizing: border-box;
        border-right: 1px solid #111;
    }

    .pub-scale-segment:last-child {
        border-right: none;
    }

    .pub-scale-labels {
        position: relative;
        height: 24px;
        margin-top: 4px;
    }

    .pub-scale-labels span {
        position: absolute;
        transform: translateX(-50%);
        font-size: 14px;
        font-weight: 600;
    }

    .pub-scale-unit {
        position: absolute;
        top: -2px;
        font-size: 15px;
        font-weight: 600;
        white-space: nowrap;
    }

    .leaflet-control.color-map {
        background: rgba(255, 255, 255, 0.96) !important;
        padding: 18px 22px !important;
        border: 2px solid #111 !important;
        box-shadow: none !important;
        margin-right: 34px !important;
        margin-bottom: 54px !important;
        font-size: 22px !important;
    }

    .leaflet-control.color-map::before {
        content: "Legend";
        display: block;
        font-size: 32px;
        font-weight: 700;
        color: #111;
        margin-bottom: 12px;
    }

    .leaflet-control.color-map svg {
        width: 560px !important;
        height: 95px !important;
    }

    .leaflet-control.color-map .caption {
        font-size: 24px !important;
        font-weight: 700 !important;
    }

    #dropdown {
        position: fixed;
        top: 36px;
        left: 36px;
        z-index: 9999;
        background: rgba(255,255,255,0.95);
        padding: 10px;
        border: 1px solid #999;
        font-size: 14px;
    }
    </style>
    """))

    map_html = m.get_root().render()

    week_opts = "".join(
        f'<option value="{i}" {"selected" if i == week else ""}>Week {i}</option>'
        for i in range(1, 53)
    )

    year_opts = "".join(
        f'<option value="{y}" {"selected" if y == year else ""}>{y}</option>'
        for y in range(2010, 2026)
    )

    metric_opts = "".join(
        f'<option value="{m}" {"selected" if m == metric else ""}>{m.capitalize()}</option>'
        for m in ["cases", "temperature", "humidity", "rainfall", "idhm"]
    )

    template = f"""
    <html>
    <head>
        <meta charset="utf-8">
        <title>RJ Map</title>
    </head>
    <body>
        <div id="dropdown">
            <form method="get">
                Year:<select name="year">{year_opts}</select><br><br>
                Week:<select name="week">{week_opts}</select><br><br>
                Metric:<select name="metric">{metric_opts}</select><br><br>
                <input type="submit" value="Update Map">
            </form>
        </div>
        <div id="map">{map_html}</div>
    </body>
    </html>
    """

    return render_template_string(template)


if __name__ == "__main__":
    app.run(debug=True)
