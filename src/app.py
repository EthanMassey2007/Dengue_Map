from flask import Flask, render_template_string, request
import folium
import json
import pandas as pd
import unicodedata
import copy
import os
from branca.colormap import linear

app = Flask(__name__)

# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------
def normalize_name(name):
    if not isinstance(name, str):
        return ""
    name = unicodedata.normalize("NFKD", name).encode("ASCII", "ignore").decode("ASCII")
    return name.lower().replace("-", " ").strip()

# ---------------------------------------------------------
# Paths (PythonAnywhere-safe)
# ---------------------------------------------------------


BASE_DIR = os.path.dirname(os.path.dirname(__file__))  # points to Dengue_Map/
DATA_DIR = os.path.join(BASE_DIR, "data")

geojson_file = os.path.join(DATA_DIR, "RJ.json")
CASES_FILE = os.path.join(DATA_DIR, "cases.csv")
TEMP_FILE = os.path.join(DATA_DIR, "temperature.csv")
HUMID_FILE = os.path.join(DATA_DIR, "humidity.csv")
RAIN_FILE = os.path.join(DATA_DIR, "rainfall.csv")
POP_FILE = os.path.join(DATA_DIR, "population.csv")
IDHM_FILE = os.path.join(DATA_DIR, "idhm.csv")

import os
print(CASES_FILE)
print(os.path.isfile(CASES_FILE))

# ---------------------------------------------------------
# Load GeoJSON
# ---------------------------------------------------------
with open(geojson_file, "r", encoding="utf-8") as f:
    base_geo_data = json.load(f)

# ---------------------------------------------------------
# Name corrections
# ---------------------------------------------------------
name_corrections = {
    "parati": "paraty",
    "niteroi": "niteroi",
    "sao goncalo": "sao goncalo",
    "nova iguacu": "nova iguacu",
    "mesquita": "mesquita",
    "trajanode morais": "trajano de moraes",
    "areal": "areal",
}

# ---------------------------------------------------------
# CSV loading helpers
# ---------------------------------------------------------
def load_csv_all(file, value_column):
    """Load CSV as dict[(municipio_norm, year, week)] = value"""
    df = pd.read_csv(file, encoding="utf-8-sig")  # safe on PythonAnywhere
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

# ---------------------------------------------------------
# Load CSVs once
# ---------------------------------------------------------
cases_dict = load_csv_all(CASES_FILE, "cases")
temperature_dict = load_csv_all(TEMP_FILE, "temperature")
humidity_dict = load_csv_all(HUMID_FILE, "humidity")
rainfall_dict = load_csv_all(RAIN_FILE, "rainfall")

population_dict = load_population_csv()
idhm_dict = load_idhm_csv()

# ---------------------------------------------------------
# Flask route
# ---------------------------------------------------------
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
        "cases": "cases_per_1000",
        "temperature": "temperature",
        "humidity": "humidity",
        "rainfall": "rainfall",
        "idhm": "idhm",
    }

    # Fill GeoJSON
    for feature in geo_data["features"]:
        name_geo = feature["properties"]["NOME"]
        name_norm = normalize_name(name_geo)
        name_norm = normalize_name(name_corrections.get(name_norm, name_norm))

        if metric == "idhm":
            feature["properties"]["idhm"] = idhm_dict.get(name_norm, 0)
            continue

        if metric == "cases":
            raw_cases = metric_sources["cases"].get((name_norm, year, week), 0)
            pop = population_dict.get(name_norm, None)
            per_1000 = (raw_cases / pop) * 1000 if pop else 0
            feature["properties"]["raw_cases"] = raw_cases
            feature["properties"]["population"] = pop
            feature["properties"]["cases_per_1000"] = round(per_1000, 3)
            continue

        val = metric_sources[metric].get((name_norm, year, week), 0)
        feature["properties"][metric] = val

    # Color scale
    prop = prop_map[metric]
    vals = [f["properties"].get(prop, 0) for f in geo_data["features"] if f["properties"].get(prop, 0) != 0]
    vmin, vmax = (min(vals), max(vals)) if vals else (0, 1)
    if vmin == vmax:
        vmin = 0
    colormap = linear.YlOrRd_09.scale(vmin, vmax)
    colormap.caption = f"{metric.capitalize()} (Week {week}/{year})"

    # Style function
    def style_function(feature):
        val = feature["properties"].get(prop, 0)
        if metric == "cases":
            return {"fillColor": colormap(val), "color": "black", "weight": 0.5, "fillOpacity": 0.7}
        if val == 0:
            return {"fillColor": "#C0C0C0", "color": "black", "weight": 0.5, "fillOpacity": 0.7}
        return {"fillColor": colormap(val), "color": "black", "weight": 0.5, "fillOpacity": 0.7}

    # Tooltip
    fields = ["NOME"]
    aliases = ["Municipality:"]
    if metric == "cases":
        fields += ["raw_cases", "population", "cases_per_1000"]
        aliases += ["Raw Cases:", "Population:", "Cases per 1,000:"]
    else:
        fields += [prop]
        aliases += [metric.capitalize() + ":"]

    # Build map
    m = folium.Map(location=[-22.9, -43.2], zoom_start=8)
    folium.GeoJson(
        geo_data,
        style_function=style_function,
        tooltip=folium.GeoJsonTooltip(fields=fields, aliases=aliases, localize=True),
    ).add_to(m)
    colormap.add_to(m)
    map_html = m.get_root().render()

    # HTML UI
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
    <style>
        body, html {{ margin:0; padding:0; height:100%; }}
        #map {{ height:100%; }}

        #dropdown {{
            position:fixed;
            top:10px;
            left:10px;
            z-index:9999;
            background:white;
            padding:10px;
            border:1px solid #ccc;
        }}

        #mitlogo {{
            position: fixed;
            bottom: 10px;
            left: 10px;
            width: 120px;
            z-index: 9999;
        }}
    </style>
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

    <img src="/static/mit_logo.png" id="mitlogo">

</body>
</html>
"""
    return render_template_string(template)


if __name__ == "__main__":
    app.run(debug=True)
