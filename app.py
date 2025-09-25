from flask import Flask, render_template_string, request
import requests
import folium
import json
from branca.colormap import linear
import math
from concurrent.futures import ThreadPoolExecutor
import copy

app = Flask(__name__)

# -----------------------------
# Step 1: Get all municipalities in RJ once
# -----------------------------
ibge_url = "https://servicodados.ibge.gov.br/api/v1/localidades/estados/33/municipios"
response = requests.get(ibge_url)
municipalities = response.json()
municipalities_info = [{"name": m["nome"], "geocode": m["id"]} for m in municipalities]

# -----------------------------
# Step 2: Load GeoJSON once
# -----------------------------
geojson_file = "RJ.json"  # Make sure this file exists in the same folder
with open(geojson_file, "r", encoding="utf-8") as f:
    base_geo_data = json.load(f)

# -----------------------------
# Step 3: Municipality name corrections
# -----------------------------
name_corrections = {
    "Parati": "Paraty",
    "Niteroi": "Niterói",
    "Sao Goncalo": "São Gonçalo",
    "Nova Iguacu": "Nova Iguaçu",
    "Mesquita": "Mesquita",
    "Rio de Janeiro": "Rio de Janeiro",
    "Trajano de Morais": "Trajano de Moraes",
    "Areal": "Areal",
}

# -----------------------------
# Step 4: Function to fetch dengue cases
# -----------------------------
def fetch_cases_for_municipio(municipio, latest_week, latest_year):
    api_url = "https://info.dengue.mat.br/api/alertcity"
    params = {
        "geocode": municipio["geocode"],
        "disease": "dengue",
        "format": "json",
        "ew_start": latest_week,
        "ew_end": latest_week,
        "ey_start": latest_year,
        "ey_end": latest_year,
    }
    try:
        r = requests.get(api_url, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        if data and "casos" in data[0]:
            return municipio['name'], int(data[0]['casos'])
        print(f"Retrieved data for {municipio['name']}: {cases} cases")
        return municipio['name'], 0
    except:
        return municipio['name'], 0

# -----------------------------
# Step 5: Flask route
# -----------------------------
@app.route("/", methods=["GET"])
def index():
    selected_week = int(request.args.get("week", 1))
    selected_year = int(request.args.get("year", 2025))

    with ThreadPoolExecutor(max_workers=10) as executor:
        results = executor.map(lambda m: fetch_cases_for_municipio(m, selected_week, selected_year), municipalities_info)
    dengue_cases = dict(results)

    geo_data = copy.deepcopy(base_geo_data)
    for feature in geo_data["features"]:
        geo_name = feature["properties"]["NOME"].strip()
        api_name = name_corrections.get(geo_name, geo_name)
        feature["properties"]["cases"] = dengue_cases.get(api_name, 0)

    m = folium.Map(location=[-22.9, -43.2], zoom_start=8)

    all_log_cases = [math.log1p(f["properties"]["cases"]) for f in geo_data["features"]]
    colormap = linear.YlOrRd_09.scale(min(all_log_cases), max(all_log_cases))
    colormap.caption = f"Weekly Dengue Cases (Week {selected_week}/{selected_year})"
    colormap.add_to(m)

    def style_function(feature):
        cases = feature["properties"]["cases"]
        log_cases = math.log1p(cases)
        return {"fillColor": colormap(log_cases), "color": "black", "weight": 0.5, "fillOpacity": 0.7}

    folium.GeoJson(
        geo_data,
        style_function=style_function,
        tooltip=folium.GeoJsonTooltip(
            fields=["NOME", "cases"], aliases=["Municipality:", "Weekly Cases:"], localize=True
        )
    ).add_to(m)

    map_html = m.get_root().render()

    week_options = "".join([f'<option value="{i}" {"selected" if i==selected_week else ""}>Week {i}</option>' for i in range(1, 53)])
    year_options = "".join([f'<option value="{y}" {"selected" if y==selected_year else ""}>{y}</option>' for y in range(20, 2026)])

    template = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>Dengue Map RJ</title>
        <style>
            body, html {{ margin:0; padding:0; height:100%; }}
            #map {{ height:100%; }}
            #dropdown {{
                position: fixed;
                top: 10px;
                left: 50px;
                z-index: 9999;
                background: white;
                padding: 10px;
                border: 1px solid #ccc;
            }}
            #loadingOverlay {{
                display:none;
                position: fixed;
                top:0; left:0;
                width:100%; height:100%;
                background: rgba(255,255,255,0.8);
                z-index:10000;
                text-align:center;
                font-size: 24px;
                padding-top: 20%;
            }}
            #logoBox {{
                position: fixed;
                bottom: 10px;
                left: 10px;
                z-index: 9999;
                background: white;
                padding: 8px;
                border: 1px solid #ccc;
                border-radius: 8px;
            }}
            #logoBox img {{
                height: 100px;  /* larger logo */
                width: auto;
                display: block;
            }}
        </style>
    </head>
    <body>
        <div id="dropdown">
            <form method="get" onsubmit="showLoading()">
                Select Year: 
                <select name="year">{year_options}</select><br><br>
                Select Week: 
                <select name="week">{week_options}</select><br><br>
                <input type="submit" value="Update Map">
            </form>
        </div>
        <div id="loadingOverlay">Updating map, please wait...</div>
        <div id="map">{map_html}</div>
        <div id="logoBox">
            <a href="https://senseable.mit.edu" target="_blank">
                <img src="/static/mit_logo.png" alt="MIT Senseable City Lab">
            </a>
        </div>
        <script>
            function showLoading() {{
                document.getElementById('loadingOverlay').style.display = 'block';
            }}
        </script>
    </body>
    </html>
    """

    return render_template_string(template)

# -----------------------------
# Step 6: Run Flask
# -----------------------------
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5001)
