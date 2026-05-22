import requests
from requests.auth import HTTPBasicAuth
import json
import urllib3
import yaml
from collections import defaultdict
from dateutil import parser
import statistics
import plotly.graph_objects as go
import json
import os
import glob
import argparse
from dotenv import load_dotenv
load_dotenv(".env.opensearch")

class IriscastOpensearch:
    def __init__(self, host, user, password, index_pattern):
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        self.host = host
        self.auth = HTTPBasicAuth(user, password)
        self.headers = {"Content-Type": "application/json"}
        self.index_pattern = index_pattern

    def initial_search(self, start_date, end_date, size=10000, scroll='5m'):
        url = f"{self.host}/{self.index_pattern}/_search?scroll={scroll}"
        query = {
            "size": size,
            "query": {
                "range": {
                    "@timestamp": {
                        "gte": start_date,
                        "lt": end_date
                    }
                }
            }
        }
        response = requests.post(url, auth=self.auth, headers=self.headers, verify=False, data=json.dumps(query))
        return response.json()

    def scroll_search(self, scroll_id, scroll='5m'):
        url = f"{self.host}/_search/scroll"
        scroll_query = {
            "scroll": scroll,
            "scroll_id": scroll_id
        }
        response = requests.post(url, auth=self.auth, headers=self.headers, verify=False, data=json.dumps(scroll_query))
        return response.json()

    def aggregate_energy_usage(self, start_date, end_date):
        data = self.initial_search(start_date, end_date)
        scroll_id = data.get('_scroll_id')
        total_watt_hours = 0.0
        total_watts = 0.0
        total_docs = 0
        batch_num = 0

        while True:
            hits = data.get("hits", {}).get("hits", [])
            if not hits:
                print("No more hits, exiting scroll loop.")
                break
            for hit in hits:
                source = hit.get("_source", {})
                total_watt_hours += source.get("watt_hours", 0.0)
                watts = source.get("watts", 0.0)
                if watts is not None:
                    total_watts += watts
            total_docs += len(hits)
            batch_num += 1
            latest_time = max((hit.get("_source", {}).get("@timestamp", "") for hit in hits), default="")
            print(f"Batch {batch_num}: processed {len(hits)} docs, total so far: {total_docs}, , up to: {latest_time}")
            print(f"    watt_hours: {total_watt_hours:.3f} Wh / watts: {total_watts:.3f} W")
            data = self.scroll_search(scroll_id)
            scroll_id = data.get('_scroll_id')

        print(f"\nEnergy usage report from {start_date} to {end_date}:")
        print(f"Total kilowatt hours (kWh): {total_watt_hours / 1000:.3f}")
        print(f"Total kilowatts (kW): {total_watts / 1000:.3f}")

    def monthly_energy_usage_by_host(self, year, month, verbose=True):
        """
        Returns a dictionary of energy usage per host for a given month.
        Queries OpenSearch for all documents within the given month,
        groups data by host.
        If verbose=True, also print the report:
            - The average sampling period (seconds between measurements)
            - The total energy usage for the month
            - The average energy usage per hour (Wh/hour)

        Args:
            year (int)
            month (int)

        Returns:
            {hostname: (month_wh, hour_wh)}
        """
        if verbose:
            print(f"\n=== Energy usage report for {year}-{month:02d} ===")

        # Define the time range for the month
        start_date = f"{year}-{month:02d}-01T00:00:00Z"
        if month == 12:
            end_date = f"{year+1}-01-01T00:00:00Z"
        else:
            end_date = f"{year}-{month+1:02d}-01T00:00:00Z"

        # Dictionaries to collect timestamps and watts per host
        host_timestamps = defaultdict(list)
        host_watts = defaultdict(list)
        batch_num = 1
        total_docs = 0

        # Initial search and scroll
        data = self.initial_search(start_date, end_date)
        scroll_id = data.get('_scroll_id')

        # Get total number of docs and calculate total batches
        total_docs_to_process = data.get("hits", {}).get("total", {}).get("value", 0)
        batch_size = 10000
        total_batches = (total_docs_to_process + batch_size - 1) // batch_size if batch_size else 0
        print(f"\n=== {year}-{month:02d} ===")
        print(f"Total documents to process: {total_docs_to_process}")
        print(f"Estimated total batches: {total_batches}")
        while True:
            hits = data.get("hits", {}).get("hits", [])
            if not hits:
                if verbose:
                    print("No more hits, exiting scroll loop.")
                break
            # Progress output log on one line
            total_docs += len(hits)
            process_percent = (batch_num / total_batches * 100) if total_batches else 0
            print(
                f"[Batch {batch_num:>3}/{total_batches}] "
                f"Processed: {total_docs:,} docs "
                f"({process_percent:5.1f}%)",
                end='\r', flush=True
            )
            for hit in hits:
                source = hit.get("_source", {})
                hostname = source.get("hostname")
                timestamp = source.get("@timestamp")
                watts = source.get("watts")
                if hostname and timestamp and watts is not None:
                    host_timestamps[hostname].append(parser.isoparse(timestamp))
                    host_watts[hostname].append(watts)
            batch_num += 1
            data = self.scroll_search(scroll_id)
            scroll_id = data.get('_scroll_id')
        if verbose:
            print(f"\nCollected data for {len(host_timestamps)} hosts. Calculating results...")

        # Calculate and print results per host
        host_usage = {}
        for hostname in host_timestamps:
            timestamps = host_timestamps[hostname]
            watts_list = host_watts[hostname]
            if len(timestamps) < 2:
                if verbose:
                    print(f"{hostname}: Not enough data to calculate sampling period or Watt Hours.")
                continue
            # Sort timestamps and watts together
            timestamps, watts_list = zip(*sorted(zip(timestamps, watts_list)))
            # Calculate periods between consecutive timestamps
            periods = [
                (t2 - t1).total_seconds()
                for t1, t2 in zip(timestamps[:-1], timestamps[1:])
            ]
            avg_period = sum(periods) / len(periods)
            # Calculate Wh for each interval
            month_wh = sum(w * (p / 3600) for w, p in zip(watts_list[:-1], periods))
            total_hours = sum(periods) / 3600 if periods else 0 # second to hour
            hour_wh = month_wh / total_hours
            host_usage[hostname] = (month_wh, hour_wh)
            if verbose:
                print(f"{hostname}: avg_sampling_period = {avg_period:.2f}s, intervals = {len(periods)}")
                print(f"    Usage per month = {month_wh:.2f} Wh")
                print(f"    Usage per hour  = {hour_wh:.2f} Wh")
        if verbose:
            print("=== Monthly energy usage report complete ===\n")
        return host_usage

    def hypervisor_model_energy_usage(
        self, 
        year, 
        month, 
        models_yml_path="models.yml", 
        save_data=True,
        ):
        """
        Calculate and prints the average power usage per hypervisor model for a given month.
        Also reports hosts in models.yml that are missing from the data.
        """
        # Load models.yml
        with open(models_yml_path, "r") as f:
            models = yaml.safe_load(f)

        # Get per-host usage
        host_usage = self.monthly_energy_usage_by_host(year, month, verbose=False)
        
        print(f"\n{'='*60}")
        print(f"\n=== Average Power Usage per Hypervisor Model for {year}-{month:02d} ===")
        print(f"\n{'='*60}")

        results = []
        for model, model_data in models.items():
            hosts = list(model_data.get("hosts", {}).keys())
            found_hosts = [h for h in hosts if h in host_usage]
            missing_hosts = [h for h in hosts if h not in host_usage]
            short_found_hosts = [h.replace('.nubes.rl.ac.uk', '') for h in found_hosts]
            short_missing_hosts = [h.replace('.nubes.rl.ac.uk', '') for h in missing_hosts]
            model_usages = [host_usage[h] for h in found_hosts]

            print(f"\nHypervisor Model: {model}")
            print(f"{'-'*40}")
            if model_usages:
                month_wh_list = [u[0] for u in model_usages]
                hour_wh_list = [u[1] for u in model_usages]
                avg_month_wh = statistics.mean(month_wh_list)
                avg_hour_wh = statistics.mean(hour_wh_list)
                min_month_wh = min(month_wh_list)
                max_month_wh = max(month_wh_list)
                std_month_wh = statistics.stdev(month_wh_list) if len(month_wh_list) > 1 else 0.0
                min_hour_wh = min(hour_wh_list)
                max_hour_wh = max(hour_wh_list)
                std_hour_wh = statistics.stdev(hour_wh_list) if len(hour_wh_list) > 1 else 0.0

                if save_data:
                    stats = {
                        "model": model,
                        "count": len(found_hosts),
                        "avg_month_wh": avg_month_wh,
                        "min_month_wh": min_month_wh,
                        "max_month_wh": max_month_wh,
                        "std_month_wh": std_month_wh,
                        "avg_hour_wh": avg_hour_wh,
                        "min_hour_wh": min_hour_wh,
                        "max_hour_wh": max_hour_wh,
                        "std_hour_wh": std_hour_wh,
                    }
                    results.append(stats)
                else:
                    print(f"  Hosts calculated ({len(found_hosts)}): {', '.join(short_found_hosts)}")
                    print(f"   + Month Wh: avg={avg_month_wh:.2f}, min={min_month_wh:.2f}, max={max_month_wh:.2f}, std={std_month_wh:.2f}")
                    print(f"   + Hour Wh: avg={avg_hour_wh:.2f}, min={min_hour_wh:.2f}, max={max_hour_wh:.2f}, std={std_hour_wh:.2f}")
            else:
                print("  No hosts found in data.")

            if missing_hosts:
                print(f"  Hosts not found in data ({len(missing_hosts)}): {', '.join(short_missing_hosts)}")
        if save_data:
            results_dir="results"
            os.makedirs(results_dir, exist_ok=True)
            results_file = os.path.join(results_dir, f"{year}_{month:02d}_model_energy_usage.json")
            with open(results_file, "w") as f:
                json.dump(results, f, indent=2)
            print(f"\nFile saved: {results_file}")
        print("=== End of Model Power Usage Report ===\n")

    def plotly_hypervisor_model_energy_usage(self, results_dir="results"):
        """
        Loop through all monthly model energy usage JSON files in results_dir and plot each month.
        """
        json_files = sorted(glob.glob(os.path.join(results_dir, "*_model_energy_usage.json")))
        for results_file in json_files:
            # Extract year and month from filename
            basename = os.path.basename(results_file)
            try:
                year, month, *_ = basename.split('_')
                year = int(year)
                month = int(month)
            except Exception:
                print(f"Skipping file with unexpected name: {basename}")
                continue

            with open(results_file, "r") as f:
                data = json.load(f)
            models = [d["model"] for d in data]
            avg = [d["avg_month_wh"] for d in data]
            std = [d["std_month_wh"] for d in data]
            minv = [d["min_month_wh"] for d in data]
            maxv = [d["max_month_wh"] for d in data]

            fig = go.Figure()

            # Bar for average with error bars (stddev)
            fig.add_trace(go.Bar(
                x=models,
                y=avg,
                error_y=dict(type='data', array=std, visible=True),
                name='Average Monthly Wh',
                marker_color='royalblue'
            ))

            # Scatter for min/max
            fig.add_trace(go.Scatter(
                x=models,
                y=minv,
                mode='markers',
                marker=dict(color='green', symbol='triangle-down', size=10),
                name='Min Monthly Wh'
            ))
            fig.add_trace(go.Scatter(
                x=models,
                y=maxv,
                mode='markers',
                marker=dict(color='red', symbol='triangle-up', size=10),
                name='Max Monthly Wh'
            ))

            fig.update_layout(
                title=f"Monthly Energy Usage per Hypervisor Model ({year}-{month:02d})",
                xaxis_title="Hypervisor Model",
                yaxis_title="Monthly Energy Usage (Wh)",
                barmode='group',
                legend_title="Legend",
                xaxis_tickangle=-45,
                template="plotly_white"
            )

            fig.show()

# if __name__ == "__main__":
#     opensearch = IriscastOpensearch(
#         host="https://172.16.114.29:9200",
#         user="admin",
#         password="admin",
#         index_pattern="cloud-iriscast-ipmi*"
#     )
#     # opensearch.aggregate_energy_usage(
#     #     start_date="2023-02-01T00:00:00Z",
#     #     end_date="2024-02-01T00:00:00Z"
#     # )
#     #opensearch.monthly_energy_usage_by_host(2023, 8)
#     opensearch.hypervisor_model_energy_usage(2024, 3)
#     #opensearch.plotly_hypervisor_model_energy_usage()

if __name__ == "__main__":
    arg_parser = argparse.ArgumentParser(description="Iriscast OpenSearch energy reports")
    arg_parser.add_argument("--year", type=int, required=True, help="Year to process (e.g. 2024)")
    arg_parser.add_argument("--month", type=int, required=True, choices=range(1,13), metavar="[1-12]", help="Month to process (1-12)")
    arg_parser.add_argument("--host", default=os.environ.get("OPENSEARCH_HOST"), help="OpenSearch host URL")
    arg_parser.add_argument("--user", default=os.environ.get("OPENSEARCH_USER"), help="OpenSearch user")
    arg_parser.add_argument("--password", default=os.environ.get("OPENSEARCH_PASSWORD"), help="OpenSearch password")
    arg_parser.add_argument("--index-pattern", default="cloud-iriscast-ipmi*", help="OpenSearch index pattern")
    arg_parser.add_argument("--models-yml", default="models.yml", help="Path to models.yml")
    arg_parser.add_argument("--no-save", action="store_true", help="Do not save results JSON file")
    args = arg_parser.parse_args()

    opensearch = IriscastOpensearch(
        host=args.host,
        user=args.user,
        password=args.password,
        index_pattern=args.index_pattern
    )

    opensearch.hypervisor_model_energy_usage(
        year=args.year,
        month=args.month,
        models_yml_path=args.models_yml,
        save_data=not args.no_save,
    )