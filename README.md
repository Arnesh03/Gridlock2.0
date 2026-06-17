# Gridlock AI (Gridlock 2.0)

Welcome to **Gridlock AI**, an interactive and AI-driven dashboard designed for analyzing, simulating, and visualizing parking violations in the city. The goal of this project is to provide actionable insights for urban planners and enforcement teams by understanding when and where parking violations happen, identifying biases in enforcement, and predicting future trends.

## 🌟 Features

* **Heatmap & Hotspots:** Visualize the busiest areas with a dynamic, color-coded map showing exactly where parking violations are most frequent.
* **Temporal Analysis:** View a time-series chart showing trends of violations over months and days of the week, adjusted for the local timezone (IST).
* **AI Model Weights (3D Interaction Matrix):** Explore how different factors (like the day of the week, hour of the day, and specific locations) interact and contribute to violations.
* **Bias Detection:** Analyzes the data using Bayesian shrinkage to detect and normalize unfair enforcement practices across different jurisdictions.
* **Patrol Routing Simulation:** An interactive tool to simulate and allocate parking enforcement resources effectively based on the predicted hotspots.

## 🛠️ How It Works

The project is split into two main parts:
1. **Data Processing Pipeline (Python):** Cleans raw CSV datasets, performs heavy statistical calculations (like bias detection and 3D interactions), and outputs lightweight `.json` files.
2. **Interactive Dashboard (Frontend):** A fast, static web application that reads the generated `.json` files and creates interactive charts and maps.

## 🚀 Getting Started

To run this project on your local machine, follow these easy steps:

### 1. Prerequisites
- Python 3.x installed on your computer.
- A modern web browser (Chrome, Firefox, Safari, Edge).

### 2. Processing the Data
If you have an updated dataset (CSV file), you need to process it first to generate the JSON files used by the dashboard.

Run the Python scripts in this order:
```bash
python process_data.py
python process_model.py
python process_bias.py
```
*Note: The raw CSV data file is excluded from this repository due to its large size. Ensure you have the CSV file (`jan to may police violation_anonymized791b166.csv`) in the root directory before running the scripts.*

### 3. Running the Dashboard
Since the dashboard fetches data using JavaScript, you need to serve the files using a local web server (simply opening the HTML file directly might not work due to browser security restrictions).

Open your terminal, navigate to the project directory, and start a local Python HTTP server:

```bash
python3 -m http.server 8000
```

Once the server is running, open your web browser and go to:
[http://localhost:8000](http://localhost:8000)

## 📂 Project Structure

```
Gridlock2.1/
│
├── index.html              # Main dashboard HTML file
├── styles.css              # Styling for the dashboard
├── app.js                  # Logic for rendering charts and handling user interactions
│
├── process_data.py         # Script to parse times, format data, and generate trends
├── process_model.py        # Script to build the 3D interaction predictive model
├── process_bias.py         # Script to apply Bayesian shrinkage and detect bias
│
├── data/                   # Generated JSON datasets used by the frontend
│   ├── heatmap.json
│   ├── hotspots.json
│   ├── time_series.json
│   ├── model_weights.json
│   ├── bias.json
│   ├── patrol_routes.json
│   ├── enforcement.json
│   └── summary.json
│
└── .gitignore              # Files and folders to ignore in Git (e.g., the large CSV file)
```

## 🤝 Contributing
Feel free to fork this project, submit issues, or make pull requests to improve the dashboard or add new analytical models!
