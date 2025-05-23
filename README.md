# Google Maps Reviews Scraper

A Flask web application that scrapes Google Maps reviews for businesses and allows downloading the data as CSV or Excel files.

## Features

- Web-based interface for easy use
- Scrape Google Maps reviews by business name and location
- Filter reviews by star rating
- Download results as CSV or Excel files
- Real-time progress updates during scraping

## Local Development

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Run the Flask app:
```bash
python app_flask.py
```

3. Open your browser and go to `http://localhost:5000`

## Deployment on Render

1. Create a new Web Service on Render
2. Connect your GitHub repository
3. Use the following settings:
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app_flask:app --bind 0.0.0.0:$PORT --workers 1 --timeout 120`

The app will automatically install Chrome/Chromium dependencies and configure the web driver for the Render environment.

## Usage

1. Enter the business name and location
2. Select the minimum star rating to filter reviews
3. Click "Start Scraping" to begin the process
4. Wait for the scraping to complete
5. Download the results as CSV or Excel

## Files Structure

- `app_flask.py` - Main Flask application
- `templates/index.html` - Web interface
- `requirements.txt` - Python dependencies
- `Procfile` - Render deployment configuration
- `runtime.txt` - Python version specification
- `render.yaml` - Render service configuration
