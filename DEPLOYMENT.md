# Render Deployment Guide

## Prerequisites
- GitHub account
- Render account (free tier available)
- Git installed locally

## Step 1: Prepare Your Repository

1. Initialize git repository (if not already done):
```bash
git init
git add .
git commit -m "Initial commit - Google Maps scraper Flask app"
```

2. Create a GitHub repository and push your code:
```bash
git remote add origin https://github.com/yourusername/google-maps-scraper.git
git branch -M main
git push -u origin main
```

## Step 2: Deploy on Render

1. Go to [Render Dashboard](https://dashboard.render.com/)
2. Click "New" → "Web Service"
3. Connect your GitHub repository
4. Configure the service:
   - **Name**: `google-maps-scraper` (or any name you prefer)
   - **Runtime**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app_flask:app --bind 0.0.0.0:$PORT --workers 1 --timeout 120`
   - **Plan**: Free (or paid for better performance)

5. Click "Create Web Service"

## Step 3: Environment Configuration

Render will automatically:
- Install Python 3.11
- Install Chrome/Chromium for Selenium
- Install all dependencies from requirements.txt
- Configure the web server

## Step 4: Access Your App

Once deployed (usually takes 5-10 minutes), you'll get a URL like:
`https://your-app-name.onrender.com`

## Important Notes

- **Cold Starts**: Free tier apps sleep after 15 minutes of inactivity and take ~30 seconds to wake up
- **Timeouts**: Large scraping jobs might timeout on free tier (15-minute limit)
- **Chrome**: The app automatically detects and uses Chrome in the Render environment
- **Memory**: Free tier has 512MB RAM limit

## Troubleshooting

If deployment fails:
1. Check the build logs in Render dashboard
2. Ensure all files are committed to Git
3. Verify requirements.txt has all dependencies
4. Check that the start command matches your app structure

## Files Needed for Deployment

✅ app_flask.py - Main Flask application
✅ requirements.txt - Python dependencies
✅ Procfile - Render process configuration
✅ runtime.txt - Python version specification
✅ render.yaml - Render service configuration (optional)
✅ templates/index.html - Frontend template
✅ .gitignore - Git ignore file
✅ README.md - Documentation
