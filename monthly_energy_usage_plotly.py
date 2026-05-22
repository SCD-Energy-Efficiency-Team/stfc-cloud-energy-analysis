import dash
from dash import dcc, html
import os
import glob
import json
import plotly.graph_objects as go
import yaml

def plotly_hypervisor_model_energy_usage(results_dir="results"):
    """
    Use Dash to display all monthly model energy usage graphs.
    """
    # Find all JSON files in the 'results' directory that match the monthly energy usage file pattern
    json_files = sorted(glob.glob(os.path.join(results_dir, "*_model_energy_usage.json")))
    figures = [] # List to hold Plotly tuples (month_label, figure)

    # Load models.yml to get host lists
    with open("models.yml", "r") as f:
        model_hosts = yaml.safe_load(f)  # dict: model_name -> list of hosts

    # Loop through each JSON file (one per month)
    for results_file in json_files:
        basename = os.path.basename(results_file)
        try:
            # Extract year and month from the filename
            year, month, *_ = basename.split('_')
            year = int(year)
            month = int(month)
        except Exception:
            # Skip files that don't match the expected naming pattern
            continue
        
        # Load JSON data for this month
        with open(results_file, "r") as f:
            data = json.load(f)
        
        # Extract hypervisor model names and statistics for plotting
        models = [d["model"] for d in data]
        avg = [d["avg_month_wh"] for d in data]
        std = [d["std_month_wh"] for d in data]
        minv = [d["min_month_wh"] for d in data]
        maxv = [d["max_month_wh"] for d in data]
        # Calculate number of hosts for each model
        host_counts = [len(model_hosts.get(model, [])) for model in models]
        
        # Create a Plotly figure for this month
        fig = go.Figure()
        # Bar for Standard Deviation (average with error bars)
        fig.add_trace(go.Bar(
            x=models,
            y=avg,
            error_y=dict(type='data', array=std, visible=True),
            name='Average Monthly Wh',
            marker_color='royalblue'
        ))
        # Scatter for min values
        fig.add_trace(go.Scatter(
            x=models,
            y=minv,
            mode='markers',
            marker=dict(color='green', symbol='triangle-down', size=10),
            name='Min Monthly Wh'
        ))
        # Scatter for max value
        fig.add_trace(go.Scatter(
            x=models,
            y=maxv,
            mode='markers',
            marker=dict(color='red', symbol='triangle-up', size=10),
            name='Max Monthly Wh'
        ))
        # Update Plotly layout
        fig.update_layout(
            title=f"Monthly Energy Usage per Hypervisor Model ({year}-{month:02d})",
            xaxis_title="Hypervisor Model",
            yaxis_title="Monthly Energy Usage (Wh)",
            barmode='group',
            legend_title="Legend",
            xaxis_tickangle=-45,
            template="plotly_white"
        )
        # Store Plotly figure and its labels
        figures.append((f"{year}-{month:02d}", fig))

    # Dash app layout
    app = dash.Dash(__name__)
    app.layout = html.Div([
        html.H1("Monthly Hypervisor Model Energy Usage"),
        html.Div([
            html.Div([
                html.H2(month_label),
                dcc.Graph(figure=fig)
            ], style={'margin-bottom': '60px'})
            for month_label, fig in figures
        ])
    ], style={'width': '95%', 'margin': 'auto'})

    app.run()

if __name__ == "__main__":
    plotly_hypervisor_model_energy_usage("results")