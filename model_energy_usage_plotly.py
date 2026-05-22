import dash
from dash import dcc, html, Input, Output, State
import os
import glob
import json
import plotly.graph_objects as go
import numpy as np
import yaml

def dash_model_energy_usage_over_time(results_dir="results"):
    """
    Dash app: For each hypervisor model, plot its energy usage over time (months) on a single graph.
    All model graphs are shown on the same page.
    """
    # Load models.yml
    with open("models.yml", "r") as f:
        models_yml = yaml.safe_load(f)
    # Build model_hosts dict
    model_hosts = {}
    for model_name, model_info in models_yml.items():
        hosts = model_info.get("hosts", {})
        model_hosts[model_name] = list(hosts.keys())
    
    # Find all monthly JSON files and sort by date
    json_files = sorted(glob.glob(os.path.join(results_dir, "*_model_energy_usage.json")))
    
    # Build a mapping: month_label -> {model: stats}
    month_labels = []
    month_model_stats = {}
    for results_file in json_files:
        basename = os.path.basename(results_file)
        try:
            year, month, *_ = basename.split('_')
            year = int(year)
            month = int(month)
            month_label = f"{year}-{month:02d}"
        except Exception:
            continue
        with open(results_file, "r") as f:
            data = json.load(f)
        # Map model to stats for this month
        model_stats = {d["model"]: d for d in data}
        month_model_stats[month_label] = model_stats
        month_labels.append(month_label)

    # Get all unique model names
    all_models = set()
    for model_stats in month_model_stats.values():
        all_models.update(model_stats.keys())

    # Ensure all month_labels are unique and sorted
    month_labels = sorted(set(month_labels))

    # Prepare data for each model
    model_data = {}
    for model in sorted(all_models):
        y_avg_month, y_std_month, y_min_month, y_max_month = [], [], [], []
        y_avg_hour, y_std_hour, y_min_hour, y_max_hour = [], [], [], []
        for month in month_labels:
            stats = month_model_stats[month].get(model)
            if stats:
                y_avg_month.append(stats["avg_month_wh"])
                y_std_month.append(stats["std_month_wh"])
                y_min_month.append(stats["min_month_wh"])
                y_max_month.append(stats["max_month_wh"])
                y_avg_hour.append(stats["avg_hour_wh"])
                y_std_hour.append(stats["std_hour_wh"])
                y_min_hour.append(stats["min_hour_wh"])
                y_max_hour.append(stats["max_hour_wh"])
            else:
                y_avg_month.append(None)
                y_std_month.append(None)
                y_min_month.append(None)
                y_max_month.append(None)
                y_avg_hour.append(None)
                y_std_hour.append(None)
                y_min_hour.append(None)
                y_max_hour.append(None)
        model_data[model] = {
            "avg_month": y_avg_month,
            "std_month": y_std_month,
            "min_month": y_min_month,
            "max_month": y_max_month,
            "avg_hour": y_avg_hour,
            "std_hour": y_std_hour,
            "min_hour": y_min_hour,
            "max_hour": y_max_hour,
        }

    # Dash app layout
    app = dash.Dash(__name__)
    app.layout = html.Div([
        html.H1("Hypervisor Model Energy Usage Over Time"),
        html.Label("Select metric to display:"),
        dcc.Dropdown(
            id="metric-dropdown",
            options=[
                {"label": "Average Monthly Wh", "value": "month"},
                {"label": "Average Hourly Wh", "value": "hour"},
            ],
            value="month",
            clearable=False,
            style={'width': '300px', 'margin-bottom': '20px'}
        ),
        html.Div(id="all-models-graphs")
    ], style={'width': '95%', 'margin': 'auto'})

    # Callback to update all graphs based on selected metric
    @app.callback(
        Output("all-models-graphs", "children"),
        Input("metric-dropdown", "value")
    )
    def update_all_graphs(selected_metric):
        suffix = "month" if selected_metric == "month" else "hour"
        y_label = "Average Monthly Energy Usage (Wh)" if suffix == "month" else "Average Hourly Energy Usage (Wh)"
        return [
            html.Div([
                html.H2(model),
                html.Div(f"Number of hosts: {len(model_hosts[model])}", style={'margin-bottom': '8px', 'font-style': 'italic'}),
                dcc.Graph(
                    id=f"{model}-graph",
                    figure=go.Figure([
                        go.Bar(
                            x=month_labels,
                            y=model_data[model][f"avg_{suffix}"],
                            error_y=dict(type='data', array=model_data[model][f"std_{suffix}"], visible=True),
                            name=f'Average {suffix.capitalize()}ly Wh',
                            marker_color='royalblue'
                        ),
                        go.Scatter(
                            x=month_labels,
                            y=model_data[model][f"min_{suffix}"],
                            mode='markers',
                            marker=dict(color='green', symbol='triangle-down', size=10),
                            name=f'Min {suffix.capitalize()}ly Wh'
                        ),
                        go.Scatter(
                            x=month_labels,
                            y=model_data[model][f"max_{suffix}"],
                            mode='markers',
                            marker=dict(color='red', symbol='triangle-up', size=10),
                            name=f'Max {suffix.capitalize()}ly Wh'
                        ),
                    ]).update_layout(
                        title=f"Energy Usage Over Time: {model}",
                        xaxis_title="Month",
                        yaxis_title=y_label,
                        barmode='group',
                        legend_title='Legend',
                        xaxis_tickangle=-45,
                        template="plotly_white"
                    )
                ),
                html.Label("Select months to include in median calculation:"),
                dcc.Dropdown(
                    id=f"{model}-months-dropdown",
                    options=[{"label": m, "value": m} for m in month_labels],
                    value=month_labels, # default: all months selected
                    multi=True
                ),
                html.Div(id=f"{model}-median-output", style={'margin-top': '10px', 'font-weight': 'bold'})
            ], style={'margin-bottom': '60px'})
            for model in sorted(all_models)
        ]

    # Callbacks for each model to update median (remains unchanged)
    for model in sorted(all_models):
        @app.callback(
            Output(f"{model}-median-output", "children"),
            Input(f"{model}-months-dropdown", "value"),
            State("metric-dropdown", "value"),
            State(f"{model}-months-dropdown", "id"),
        )
        def update_median(selected_months, selected_metric, dropdown_id, model_name=model):
            new_name = model_name.replace("-", "_")
            suffix = "month" if selected_metric == "month" else "hour"
            indices = [i for i, m in enumerate(month_labels) if m in selected_months]
            avg_values = [model_data[model_name][f"avg_{suffix}"][i] for i in indices if model_data[model_name][f"avg_{suffix}"][i] is not None]
            min_values = [model_data[model_name][f"min_{suffix}"][i] for i in indices if model_data[model_name][f"min_{suffix}"][i] is not None]
            max_values = [model_data[model_name][f"max_{suffix}"][i] for i in indices if model_data[model_name][f"max_{suffix}"][i] is not None]
            if avg_values:
                median_val = float(np.median(avg_values))
                min_val = float(np.min(min_values)) if min_values else None
                max_val = float(np.max(max_values)) if max_values else None
                if suffix == "hour":
                    return html.Div([
                        html.Div(f"{new_name}", style={'font-weight': 'bold'}),
                        html.Div(f"Median Average Hourly Wh (selected months): {median_val:.2f}"),
                        html.Div(f"Lowest Monthly Average Hourly Wh (selected months): {min_val:.2f}" if min_val is not None else "No min value"),
                        html.Div(f"Highest Monthly Average Hourly Wh (selected months): {max_val:.2f}" if max_val is not None else "No max value"),
                    ])
                else:
                    return html.Div([
                        html.Div(f"{new_name}", style={'font-weight': 'bold'}),
                        html.Div(f"Median Average Monthly Wh (selected months): {median_val:.2f}"),
                        html.Div(f"Min of Avg Monthly Wh (selected months): {min_val:.2f}" if min_val is not None else "No min value"),
                        html.Div(f"Max of Avg Monthly Wh (selected months): {max_val:.2f}" if max_val is not None else "No max value"),
                    ])
            else:
                return "No data for selected months."

    app.run()

if __name__ == "__main__":
    dash_model_energy_usage_over_time("results")