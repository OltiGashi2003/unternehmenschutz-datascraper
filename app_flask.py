from flask import Flask, render_template, request, jsonify, send_file
import pandas as pd
import io
import time
import re
import csv
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service as ChromeService

app = Flask(__name__)

def convert_df_to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Reviews')
    processed_data = output.getvalue()
    return processed_data

def scrape_google_maps_reviews(business_name_input, location_input, selected_stars):
    search_query = f"{business_name_input} {location_input}".replace(' ', '+')
    all_reviews = []
    business_data = {}

    print(f"Starting scraping for: {business_name_input} in {location_input}")
    print(f"Search URL: https://www.google.com/maps/search/{search_query}")

    options = webdriver.ChromeOptions()
    options.add_argument("--disable-notifications")
    options.add_argument("--disable-infobars")
    options.add_argument("--headless")  # Use classic headless for better compatibility
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-extensions")

    # Set binary location for Render deployment
    if os.path.exists("/usr/bin/google-chrome"):
        options.binary_location = "/usr/bin/google-chrome"
    elif os.path.exists("/usr/bin/google-chrome-stable"):
        options.binary_location = "/usr/bin/google-chrome-stable"

    try:
        service = ChromeService(ChromeDriverManager().install())
        browser = webdriver.Chrome(service=service, options=options)
        browser.get(f"https://www.google.com/maps/search/{search_query}")
        time.sleep(4)

        # Accept cookies if present
        try:
            accept_button = WebDriverWait(browser, 10).until(
                EC.element_to_be_clickable((By.XPATH, '//button[.//span[contains(text(),"Accept all") or contains(text(),"Alle akzeptieren")]]'))
            )
            accept_button.click()
            print("Accepted cookies.")
            time.sleep(1)
        except (TimeoutException, NoSuchElementException):
            print("No cookie prompt found or already accepted.")

        # Extract business overview information
        try:
            print("Extracting business overview...")
            # Business Name
            try:
                bname = WebDriverWait(browser, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "h1.DUwDvf"))
                ).text
                business_data["Business Name"] = bname
                print(f"  - Business Name: {bname}")
            except Exception as e:
                print(f"  - Could not find business name: {e}")
                business_data["Business Name"] = business_name_input

            # Average Rating
            try:
                rating_element = WebDriverWait(browser, 5).until(
                    EC.presence_of_element_located((By.XPATH, '//*[@id="QA0Szd"]/div/div/div[1]/div[2]/div/div[1]/div/div/div[2]/div/div[1]/div[2]/div/div[1]/div[2]/span[1]/span[1]'))
                )
                avg_rating = rating_element.text
                business_data["Average Rating"] = avg_rating
                print(f"  - Average Rating: {avg_rating}")
            except Exception as e:
                print(f"  - Could not find average rating: {e}")
                business_data["Average Rating"] = "N/A"

            # Total Reviews
            try:
                reviews_element = WebDriverWait(browser, 5).until(
                    EC.presence_of_element_located((By.XPATH, '//*[@id="QA0Szd"]/div/div/div[1]/div[2]/div/div[1]/div/div/div[2]/div/div[1]/div[2]/div/div[1]/div[2]/span[2]/span/span'))
                )
                total_reviews = reviews_element.text
                business_data["Total Reviews"] = total_reviews
                print(f"  - Total Reviews: {total_reviews}")
            except Exception as e:
                print(f"  - Could not find total reviews: {e}")
                business_data["Total Reviews"] = "N/A"

            business_data["Price Level"] = "N/A"
            business_data["Price Range"] = "N/A"

        except Exception as e:
            print(f"Could not extract all business overview details: {e}")

        # Click "Reviews" tab
        try:
            review_button_xpaths = [
                '//button[contains(@aria-label, "Reviews for") or contains(@aria-label, "Rezensionen für")]',
                '//button[@role="tab"][contains(., "Reviews") or contains(., "Rezensionen")]',
                '//div[contains(@class, "Gpq6kf") and contains(@class, "NlVald") and (text()="Reviews" or text()="Rezensionen")]'
            ]
            review_button = None
            for xpath in review_button_xpaths:
                try:
                    review_button = WebDriverWait(browser, 10).until(
                        EC.element_to_be_clickable((By.XPATH, xpath))
                    )
                    print(f"Found reviews button/tab using XPath: {xpath}")
                    break
                except (TimeoutException, NoSuchElementException):
                    continue

            if review_button:
                review_button.click()
                print("Clicked on Reviews tab.")
                time.sleep(3)
            else:
                print("Could not find or click the Reviews button/tab.")
                browser.quit()
                return []

        except Exception as e:
            print(f"Error clicking reviews tab: {e}")
            browser.quit()
            return []

        # Scroll through ALL reviews
        try:
            scrollable_div_xpaths = [
                '//div[@role="main"]/div[contains(@class, "review-dialog-list")]',
                '//div[contains(@aria-label, "Reviews for") or contains(@aria-label, "Rezensionen für")]/following-sibling::div//div[contains(@class, "DxyBCb")]',
                '//div[contains(@class, "DxyBCb")]'
            ]
            reviewArea = None
            for xpath in scrollable_div_xpaths:
                try:
                    reviewArea = WebDriverWait(browser, 10).until(
                        EC.presence_of_element_located((By.XPATH, xpath))
                    )
                    print(f"Found scrollable review area using XPath: {xpath}")
                    break
                except (TimeoutException, NoSuchElementException):
                    continue

            if not reviewArea:
                print("Could not find the scrollable review area.")
                browser.quit()
                return []

            previous_reviews_count = 0
            max_scroll_attempts = 100
            no_new_reviews_count = 0
            scroll_pause_time = 2

            print("Starting scroll to load all reviews...")
            for attempt in range(max_scroll_attempts):
                reviewDivs = browser.find_elements(By.XPATH, "//div[@data-review-id]")
                current_reviews_count = len(reviewDivs)
                print(f"Scroll attempt {attempt+1}/{max_scroll_attempts}: Found {current_reviews_count} reviews...")

                if current_reviews_count == previous_reviews_count:
                    no_new_reviews_count += 1
                    if no_new_reviews_count >= 5:
                        print(f"No new reviews found after {no_new_reviews_count} attempts. Assuming all loaded ({current_reviews_count} total).")
                        break
                else:
                    no_new_reviews_count = 0

                previous_reviews_count = current_reviews_count
                browser.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", reviewArea)
                time.sleep(scroll_pause_time)

            print(f"Scrolling finished. Found {previous_reviews_count} reviews in total.")

        except Exception as e:
            print(f"Error during scrolling: {e}. Proceeding with currently loaded reviews.")

        base_url = browser.current_url.split('?')[0]
        reviewDivs = browser.find_elements(By.XPATH, "//div[@data-review-id]")
        print(f"Extracting details from {len(reviewDivs)} loaded reviews...")

        extracted_count = 0
        processed_review_ids = set()

        for review in reviewDivs:
            try:
                review_id = review.get_attribute("data-review-id")
                if not review_id or review_id in processed_review_ids:
                    continue
                processed_review_ids.add(review_id)

                rating_value = 0
                rating_text = "N/A"
                try:
                    rating_element = review.find_element(By.XPATH, './/span[contains(@aria-label, "star") or contains(@aria-label, "Stern")]')
                    rating_text = rating_element.get_attribute('aria-label').strip()
                    rating_match = re.search(r'(\d+)', rating_text)
                    if rating_match:
                        rating_value = int(rating_match.group(1))
                except NoSuchElementException:
                    continue

                if rating_value in selected_stars:
                    reviewer_name = "N/A"
                    review_date = "N/A"
                    review_text_content = "N/A"
                    review_link = "No link available"

                    try:
                        reviewer_name = review.find_element(By.XPATH, ".//div[contains(@class, 'd4r55')]").text
                    except NoSuchElementException:
                        pass

                    try:
                        review_date = review.find_element(By.XPATH, ".//span[contains(@class, 'rsqaWe')]").text
                    except NoSuchElementException:
                        pass

                    try:
                        more_button = review.find_element(By.XPATH, ".//button[contains(@aria-label, 'See more')]")
                        more_button.click()
                        time.sleep(0.5)
                    except NoSuchElementException:
                        pass

                    try:
                        review_text_content = review.find_element(By.XPATH, ".//span[contains(@class, 'wiI7pd')]").text
                    except NoSuchElementException:
                        pass

                    review_link = f"{base_url}?hl=en&review={review_id}"

                    record = {
                        "Business Name": business_data.get("Business Name", "N/A"),
                        "Average Rating": business_data.get("Average Rating", "N/A"),
                        "Total Reviews": business_data.get("Total Reviews", "N/A"),
                        "Reviewer": reviewer_name,
                        "Rating": rating_text,
                        "Reviewed On": review_date,
                        "Review Text": review_text_content,
                        "Review Link": review_link
                    }
                    all_reviews.append(record)
                    extracted_count += 1

            except Exception as e:
                print(f"Error processing one review: {e}")

        print(f"Extracted {extracted_count} unique reviews with selected star ratings.")
    except Exception as e:
        print(f"An unexpected error occurred during the scraping process: {e}")
    finally:
        if 'browser' in locals() and browser:
            browser.quit()
            print("Browser closed.")

    return all_reviews

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/scrape', methods=['POST'])
def scrape():
    data = request.json
    business_name = data.get('business_name')
    location = data.get('location')
    selected_stars = data.get('selected_stars', [1, 2, 3])
    
    if not business_name or not location:
        return jsonify({'error': 'Business name and location are required'}), 400
    
    try:
        reviews = scrape_google_maps_reviews(business_name, location, selected_stars)
        return jsonify({
            'success': True,
            'reviews_count': len(reviews),
            'reviews': reviews
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
