# STFC Cloud IrisCast — Energy Analysis
Tools for querying STFC Cloud - IPMI power data from an OpenSearch cluster, aggregating energy usage per hypervisor host and model, and producing Plotly visualisations.

## Project structure
- `main.py` — Queries OpenSearch and saves results to `results/`
- `model_energy_usage_plotly.py` — Interactive Plotly charts for per-model energy usage
- `monthly_energy_usage_plotly.py` — Interactive Plotly charts for monthly aggregated energy usage
- `models.yml` — Maps hypervisor model names to their hostnames
- `requirements.txt` — Python dependencies
- `results/` — JSON output files produced by main.py

## About the Results
Energy usage reports have already been generated and saved in `results/`. The data covers the period **July 2023 to January 2024** (inclusive). 
> **Note:** The OpenSearch cluster holds data beyond this period, but data outside July 2023 – January 2024 has been found to be inconsistent and unreliable. The results in `results/` represent the most reliable available data.

Unless you need to re-run the OpenSearch query (e.g. the data on the cluster has been corrected), you do not need to set up credentials or run `main.py`. Simply install the dependencies and view the charts.

## Quick Start - View Results
### Installation
Python 3.12.3
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```
### View interactive Plotly charts
Per-model energy usage (bar chart with avg/min/max per hypervisor, per month):
```bash
python3 model_energy_usage_plotly.py
```
Monthly aggregated energy usage:
```bash
python3 monthly_energy_usage_plotly.py
```

## Re-running the OpenSearch Query (Optional)
Only needed if you want to regenerate the results or the OpenSearch data has been updated.
This tool connects to a private OpenSearch instance.
1. Copy the example env file:
```bash
cp .env.opensearch.example .env.opensearch 
```
2. Fill in the credentials in `.env.opensearch`
``` 
OPENSEARCH_HOST=https://<host>:9200
OPENSEARCH_USER=<username>
OPENSEARCH_PASSWORD=<password>
```
3. To obtain credentials, contact the repository maintainer.

### Run the energy report
```bash
python3 main.py --year <YEAR> --month <MONTH>
```
Example - regenerate all months in the reliable data period:
```bash
for month in 7 8 9 10 11 12; do
    python3 main.py --year 2023 --month $month
done
python3 main.py --year 2024 --month 1
```
Results are saved to `results/YYYY_MM_model_energy_usage.json` and will overwrite existing files.

### All CLI options
```bash
--year          Year to process (required, e.g. 2024)
--month         Month to process (required, 1-12)
--host          OpenSearch host URL (default: $OPENSEARCH_HOST)
--user          OpenSearch username (default: $OPENSEARCH_USER)
--password      OpenSearch password (default: $OPENSEARCH_PASSWORD)
--index-pattern OpenSearch index pattern (default: cloud-iriscast-ipmi*)
--models-yml    Path to models.yml (default: models.yml)
--no-save       Print results to stdout instead of saving JSON
```

## Results Format
Each JSON file in `results/` contains a list of entries, one per hypervisor model:
```json
{
  "model": "Dell PowerEdge R640",
  "count": 12,
  "avg_month_wh": 123456.78,
  "min_month_wh": 110000.00,
  "max_month_wh": 135000.00,
  "std_month_wh": 8000.00,
  "avg_hour_wh": 166.99,
  "min_hour_wh": 148.92,
  "max_hour_wh": 182.26,
  "std_hour_wh": 10.81
}
```
Files under `results/Not use/` are archived data outside the reliable period and are excluded from plots.

## Dependencies

| Package | Version | Description |
|---|---|---|
| `dash` | 3.3.0 | Webs server for interactive dashboards |
| `numpy` | 2.3.5 | Numerical computations (median, min, max) |
| `plotly` | 6.5.0 | Interactive charting |
| `python-dateutil` | 2.9.0.post0 | Timestamp parsing |
| `python-dotenv` | 1.2.2 | Load credentials from `.env.opensearch` |
| `PyYAML` | 6.0.3 | Parse `models.yml` |
| `requests` | 2.32.5 | HTTP requests to OpenSearch |
| `urllib3` | 2.6.1 | HTTP connection management |

Full dependencies are listed in `requirements.txt`.

## Contact
For questions about these scripts or to request OpenSearch credentials, open a GitHub issue or contact the repository maintainer.