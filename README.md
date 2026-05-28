# Dengue Map

An interactive Flask web application for visualizing dengue-related socioeconomic and environmental data across municipalities in Rio de Janeiro, Brazil.

The app displays a choropleth map of Rio de Janeiro municipalities and allows users to switch by year, epidemiological week, and metric. Supported metrics include dengue cases, temperature, humidity, rainfall, and IDHM.

## Features

- Interactive municipality-level map of Rio de Janeiro
- Year and week selection from 2010 through 2025
- Metric selector for:
  - Dengue cases
  - Temperature
  - Humidity
  - Rainfall
  - IDHM
- Log-scaled coloring for dengue cases
- Tooltip values for each municipality
- Publication-style map elements:
  - North arrow
  - Scale bar
  - Coordinate labels
  - Enlarged legend

## Project Structure

```text
Dengue_Map/
├── data/
│   ├── RJ.json
│   ├── cases.csv
│   ├── humidity.csv
│   ├── idhm.csv
│   ├── population.csv
│   ├── rainfall.csv
│   └── temperature.csv
├── src/
│   ├── app.py
│   └── static/
│       └── mit_logo.png
└── README.md
```

## Data Format

Each CSV file should contain municipality, year, and week columns, plus one metric column.

Required files:

```text
data/cases.csv
data/humidity.csv
data/idhm.csv
data/population.csv
data/rainfall.csv
data/temperature.csv
data/RJ.json
```

Expected CSV columns:

```text
cases.csv: municipio,year,week,cases
humidity.csv: municipio,year,week,humidity
idhm.csv: municipio,year,week,idhm
population.csv: municipio,year,week,population
rainfall.csv: municipio,year,week,rainfall
temperature.csv: municipio,year,week,temperature
```

The GeoJSON file `RJ.json` must contain Rio de Janeiro municipality boundaries and a municipality name property called `NOME`.

## Installation

Clone the repository:

```bash
git clone https://github.com/YOUR-USERNAME/YOUR-REPOSITORY.git
cd YOUR-REPOSITORY
```

Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

On Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install the required packages:

```bash
python -m pip install flask folium pandas branca
```

## Running the App

From the repository root, run:

```bash
python src/app.py
```

Then open the local URL shown in the terminal, usually:

```text
http://127.0.0.1:5000
```

## How to Use

Use the dropdown controls in the upper-left corner of the map to select:

- Year
- Epidemiological week
- Metric

Click **Update Map** to refresh the visualization.

Hover over a municipality to view its value for the selected metric.

## Notes on Case Scaling

Dengue cases are displayed using a log scale:

```text
log(1 + cases)
```

This makes large case differences easier to visualize while still preserving municipalities with zero cases.

The tooltip shows the actual raw case count.

## Deployment Notes

The app uses relative paths based on the repository structure, so it expects the `data` folder to remain at the repository root:

```text
Dengue_Map/data/
```

If deploying to a service such as PythonAnywhere, keep the same folder structure or update the paths in `src/app.py`.

For production deployment, set `debug=False` or run the app with a production WSGI server.

## Requirements

Main Python dependencies:

```text
Flask
Folium
Pandas
Branca
```

## License and Data Sources

This project uses dengue, climate, socioeconomic, and geographic data for Rio de Janeiro municipalities. If publishing the repository publicly, include citations or links for the original data sources used to generate the CSV and GeoJSON files.

