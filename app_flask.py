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

def check_early_stop_condition(browser, selected_stars, max_rating_needed):
    """
    Check if we should stop scrolling early based on rating patterns.
    Returns True if we should stop, False if we should continue.
    """
    try:
        # Get the last 5-10 visible reviews to check their ratings
        reviewDivs = browser.find_elements(By.XPATH, "//div[@data-review-id]")
        if len(reviewDivs) < 10:
            return False
        
        # Check the last 5 reviews
        last_reviews = reviewDivs[-5:]
        ratings_found = []
        
        for review in last_reviews:
            try:
                rating_value = 0
                
                # Try to find star-based rating first (aria-label method)
                try:
                    rating_element = review.find_element(By.XPATH, './/span[contains(@aria-label, "star") or contains(@aria-label, "Stern")]')
                    rating_text = rating_element.get_attribute('aria-label').strip()
                    rating_match = re.search(r'(\d+)', rating_text)
                    if rating_match:
                        rating_value = int(rating_match.group(1))
                except NoSuchElementException:
                    # Try numerical rating format
                    try:
                        rating_element = review.find_element(By.XPATH, './/span[@class="fzvQIb"]')
                        rating_text = rating_element.text.strip()
                        rating_match = re.search(r'(\d+)/5', rating_text)
                        if rating_match:
                            rating_value = int(rating_match.group(1))
                    except NoSuchElementException:
                        continue
                
                if rating_value > 0:
                    ratings_found.append(rating_value)
            except Exception:
                continue
        
        if not ratings_found:
            return False
        
        # If all recent reviews have ratings higher than what we need, stop
        min_recent_rating = min(ratings_found)
        if min_recent_rating > max_rating_needed:
            print(f"Early stop condition met: Recent ratings {ratings_found} are all above {max_rating_needed}")
            return True
        
        return False
        
    except Exception as e:
        print(f"Error in early stop check: {e}")
        return False

def scrape_google_maps_reviews(business_name_input, location_input, selected_stars):
    search_query = f"{business_name_input} {location_input}".replace(' ', '+')
    all_reviews = []
    business_data = {}

    print(f"Starting scraping for: {business_name_input} in {location_input}")
    print(f"Search URL: https://www.google.com/maps/search/{search_query}")    # Chrome options optimized for cloud deployment
    options = webdriver.ChromeOptions()
    options.add_argument("--disable-notifications")
    options.add_argument("--disable-infobars")
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-web-security")
    options.add_argument("--disable-features=VizDisplayCompositor")
    options.add_argument("--remote-debugging-port=9222")
    options.add_argument("--single-process")
    options.add_argument("--disable-background-timer-throttling")
    options.add_argument("--disable-renderer-backgrounding")
    options.add_argument("--disable-backgrounding-occluded-windows")
    options.add_argument("--user-data-dir=/tmp/chrome-user-data")
    options.add_argument("--data-path=/tmp/chrome-data")
    options.add_argument("--cache-dir=/tmp/chrome-cache")
    options.add_argument("--disk-cache-dir=/tmp/chrome-disk-cache")
    
    print("Chrome options configured for cloud deployment")

    try:
        print("Creating Chrome driver...")
        browser = None
        
        # Skip ChromeDriverManager - use direct Chrome installation
        try:
            # Let webdriver find Chrome automatically without ChromeDriverManager
            browser = webdriver.Chrome(options=options)
            print("✅ Chrome driver created successfully")
        except Exception as e:
            print(f"❌ Chrome driver creation failed: {e}")
            return []

        # Navigate to Google Maps
        try:
            browser.get(f"https://www.google.com/maps/search/{search_query}")
            time.sleep(4)
            print("✅ Successfully navigated to Google Maps")
        except Exception as e:
            print(f"❌ Failed to navigate to Google Maps: {e}")
            if browser:
                browser.quit()
            return []

        # Accept cookies if present
        try:
            accept_button = WebDriverWait(browser, 3).until(
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
                bname = WebDriverWait(browser, 3).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "h1.DUwDvf"))
                ).text
                business_data["Business Name"] = bname
                print(f"  - Business Name: {bname}")
            except Exception as e:
                print(f"  - Could not find business name: {e}")
                business_data["Business Name"] = business_name_input

            # Average Rating
            try:
                rating_element = WebDriverWait(browser, 3).until(
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
                reviews_element = WebDriverWait(browser, 4).until(
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
                    review_button = WebDriverWait(browser, 3).until(
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

        # Check if we should sort by lowest rating for optimization
        max_rating_needed = max(selected_stars)
        min_rating_needed = min(selected_stars)
        should_sort_by_lowest = max_rating_needed <= 3  # Only sort if we only need low ratings
        
        if should_sort_by_lowest:
            try:
                print("Attempting to sort reviews by lowest rating for optimization...")
                # Try multiple selectors for the Sort button
                sort_button = None
                sort_selectors = [
                    '//span[@class="Cw1rxd google-symbols G47vBd"]',
                    '//button[@class="HQzyZ"][@aria-label="Most relevant"]',
                    '//button[contains(@aria-label, "Most relevant")]',
                    '//div[@class="fontBodyLarge k5lwKb" and text()="Most relevant"]',
                    '//span[@class="GMtm7c fontTitleSmall" and text()="Sort"]',
                    '//*[@id="QA0Szd"]/div/div/div[1]/div[2]/div/div[1]/div/div/div[4]/div[10]/button[2]/div'
                ]
                
                for selector in sort_selectors:
                    try:
                        sort_button = WebDriverWait(browser, 3).until(
                            EC.element_to_be_clickable((By.XPATH, selector))
                        )
                        print(f"Found sort button using selector: {selector}")
                        break
                    except (TimeoutException, NoSuchElementException):
                        continue
                
                if sort_button:
                    sort_button.click()
                    print("Clicked Sort/Most Relevant button.")
                    time.sleep(2)
                    
                    # Click "Lowest rating" option using the specific xpath
                    lowest_rating_button = WebDriverWait(browser, 4).until(
                        EC.element_to_be_clickable((By.XPATH, '//*[@id="action-menu"]/div[4]'))
                    )
                    lowest_rating_button.click()
                    print("Selected 'Lowest rating' sort option.")
                    time.sleep(3)
                else:
                    print("Could not find sort button with any selector")
                    should_sort_by_lowest = False
                
            except Exception as e:
                print(f"Could not sort by lowest rating (will continue with default sorting): {e}")
                should_sort_by_lowest = False

        # Scroll through reviews with smart stopping
        try:
            scrollable_div_xpaths = [
                '//div[@role="main"]/div[contains(@class, "review-dialog-list")]',
                '//div[contains(@aria-label, "Reviews for") or contains(@aria-label, "Rezensionen für")]/following-sibling::div//div[contains(@class, "DxyBCb")]',
                '//div[contains(@class, "DxyBCb")]'
            ]
            reviewArea = None
            for xpath in scrollable_div_xpaths:
                try:
                    reviewArea = WebDriverWait(browser, 4).until(
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
            max_scroll_attempts = 100 if not should_sort_by_lowest else 50  # Fewer attempts if sorted
            no_new_reviews_count = 0
            scroll_pause_time = 2
            early_stop_triggered = False

            print(f"Starting scroll to load reviews... (Early stop enabled: {should_sort_by_lowest})")
            for attempt in range(max_scroll_attempts):
                reviewDivs = browser.find_elements(By.XPATH, "//div[@data-review-id]")
                current_reviews_count = len(reviewDivs)
                print(f"Scroll attempt {attempt+1}/{max_scroll_attempts}: Found {current_reviews_count} reviews...")

                # Early stopping logic when sorted by lowest rating
                if should_sort_by_lowest and current_reviews_count >= 10:  # Check after we have some reviews
                    should_stop = check_early_stop_condition(browser, selected_stars, max_rating_needed)
                    if should_stop:
                        print(f"Early stop triggered! Found rating higher than {max_rating_needed} stars. Stopping scroll.")
                        early_stop_triggered = True
                        break

                if current_reviews_count == previous_reviews_count:
                    no_new_reviews_count += 1
                    stop_threshold = 3 if should_sort_by_lowest else 5  # Stop sooner if sorted
                    if no_new_reviews_count >= stop_threshold:
                        print(f"No new reviews found after {no_new_reviews_count} attempts. Assuming all loaded ({current_reviews_count} total).")
                        break
                else:
                    no_new_reviews_count = 0

                previous_reviews_count = current_reviews_count
                browser.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", reviewArea)
                time.sleep(scroll_pause_time)

            if early_stop_triggered:
                print(f"Scrolling stopped early due to rating optimization. Found {previous_reviews_count} reviews.")
            else:
                print(f"Scrolling finished. Found {previous_reviews_count} reviews in total.")

        except Exception as e:
            print(f"Error during scrolling: {e}. Proceeding with currently loaded reviews.")

        base_url = browser.current_url.split('?')[0]
        reviewDivs = browser.find_elements(By.XPATH, "//div[@data-review-id]")
        print(f"Extracting details from {len(reviewDivs)} loaded reviews...")

        extracted_count = 0
        processed_review_ids = set()
        consecutive_high_ratings = 0  # Track consecutive ratings above our threshold

        for review in reviewDivs:
            try:
                review_id = review.get_attribute("data-review-id")
                if not review_id or review_id in processed_review_ids:
                    continue
                processed_review_ids.add(review_id)

                rating_value = 0
                rating_text = "N/A"
                
                # Try to find star-based rating first (aria-label method)
                try:
                    rating_element = review.find_element(By.XPATH, './/span[contains(@aria-label, "star") or contains(@aria-label, "Stern")]')
                    rating_text = rating_element.get_attribute('aria-label').strip()
                    rating_match = re.search(r'(\d+)', rating_text)
                    if rating_match:
                        rating_value = int(rating_match.group(1))
                        rating_text = f"{rating_value} stars"
                except NoSuchElementException:
                    # Try to find numerical rating format (e.g., 3/5, 4/5)
                    try:
                        rating_element = review.find_element(By.XPATH, './/span[@class="fzvQIb"]')
                        rating_text = rating_element.text.strip()
                        # Extract rating from formats like "3/5", "4/5", etc.
                        rating_match = re.search(r'(\d+)/5', rating_text)
                        if rating_match:
                            rating_value = int(rating_match.group(1))
                        else:
                            # Fallback: try to extract just the number
                            rating_match = re.search(r'(\d+)', rating_text)
                            if rating_match:
                                rating_value = int(rating_match.group(1))
                    except NoSuchElementException:
                        # Last attempt: try any span with rating-like text
                        try:
                            rating_elements = review.find_elements(By.XPATH, './/span[contains(text(), "/5")]')
                            if rating_elements:
                                rating_text = rating_elements[0].text.strip()
                                rating_match = re.search(r'(\d+)/5', rating_text)
                                if rating_match:
                                    rating_value = int(rating_match.group(1))
                        except:
                            pass
                
                # Skip review if no rating found
                if rating_value == 0:
                    continue

                # Early stopping logic when sorted by lowest rating
                if should_sort_by_lowest and rating_value > max_rating_needed:
                    consecutive_high_ratings += 1
                    print(f"Found {rating_value}-star review (above threshold {max_rating_needed}). Consecutive high ratings: {consecutive_high_ratings}")
                    
                    # Stop if we see 5 consecutive reviews above our threshold
                    if consecutive_high_ratings >= 5:
                        print(f"Stopping extraction: Found {consecutive_high_ratings} consecutive reviews above {max_rating_needed} stars")
                        break
                    else:
                        continue  # Skip this review but don't stop yet
                else:
                    consecutive_high_ratings = 0  # Reset counter

                if rating_value in selected_stars:
                    reviewer_name = "N/A"
                    review_date = "N/A"
                    review_text_content = "N/A"
                    review_link = "No link available"
                    review_source = "Unknown"
                    
                    try:
                        reviewer_name = review.find_element(By.XPATH, ".//div[contains(@class, 'd4r55')]").text
                    except NoSuchElementException:
                        pass

                    # Handle different date formats and filter by source
                    try:
                        # First try the standard date format (star-based reviews)
                        date_element = review.find_element(By.XPATH, ".//span[contains(@class, 'rsqaWe')]")
                        review_date = date_element.text
                        review_source = "Google"
                        print(f"Found star-based date: {review_date}")
                    except NoSuchElementException:
                        # Try the DU9Pgb div which contains rating, date and source info
                        try:
                            du9pgb_element = review.find_element(By.XPATH, ".//div[@class='DU9Pgb']")
                            full_text = du9pgb_element.text.strip()
                            print(f"Found DU9Pgb element with text: '{full_text}'")
                            
                            # Example text: "2/5 5 years ago on Tripadvisor" or "4/5 a year ago on Google"
                            # We need to extract just the date part (e.g., "5 years ago", "a year ago")
                            
                            # Use regex to extract the date pattern from the full text
                            # This pattern covers both English and German date formats
                            date_patterns = [
                                # German patterns (including "bei" variations)
                                r'(vor\s+\d+\s+Jahren?(?:\s+bei)?)',       # "vor 2 Jahren", "vor 2 Jahren bei"
                                r'(vor\s+einem\s+Jahr(?:\s+bei)?)',        # "vor einem Jahr", "vor einem Jahr bei"
                                r'(vor\s+\d+\s+Monaten?(?:\s+bei)?)',      # "vor 2 Monaten", "vor 2 Monaten bei"
                                r'(vor\s+einem\s+Monat(?:\s+bei)?)',       # "vor einem Monat", "vor einem Monat bei"
                                r'(vor\s+\d+\s+Wochen?(?:\s+bei)?)',       # "vor 2 Wochen", "vor 2 Wochen bei"
                                r'(vor\s+einer\s+Woche(?:\s+bei)?)',       # "vor einer Woche", "vor einer Woche bei"
                                r'(vor\s+\d+\s+Tagen?(?:\s+bei)?)',        # "vor 2 Tagen", "vor 2 Tagen bei"
                                r'(vor\s+einem\s+Tag(?:\s+bei)?)',         # "vor einem Tag", "vor einem Tag bei"
                                # English patterns
                                r'(\d+\s+years?\s+ago)',                   # "2 years ago", "1 year ago"
                                r'(a\s+year\s+ago)',                       # "a year ago"
                                r'(\d+\s+months?\s+ago)',                  # "2 months ago", "1 month ago"
                                r'(a\s+month\s+ago)',                      # "a month ago"
                                r'(\d+\s+weeks?\s+ago)',                   # "2 weeks ago", "1 week ago"
                                r'(a\s+week\s+ago)',                       # "a week ago"
                                r'(\d+\s+days?\s+ago)',                    # "2 days ago", "1 day ago"
                                r'(a\s+day\s+ago)',                        # "a day ago"
                            ]
                            
                            # First, normalize whitespace and newlines to handle multiline text
                            normalized_text = ' '.join(full_text.split())
                            print(f"Normalized text: '{normalized_text}'")
                            
                            review_date = None
                            for pattern in date_patterns:
                                date_match = re.search(pattern, normalized_text, re.IGNORECASE | re.DOTALL)
                                if date_match:
                                    review_date = date_match.group(1).strip()
                                    # Remove "bei" from the end if present
                                    review_date = re.sub(r'\s+bei\s*$', '', review_date, flags=re.IGNORECASE)
                                    break
                            
                            if review_date:
                                print(f"Extracted date from DU9Pgb: '{review_date}'")
                                
                                # Determine source from the full text
                                if "Google" in full_text:
                                    review_source = "Google"
                                elif any(source in full_text for source in ["Tripadvisor", "Yelp", "Facebook", "Booking"]):
                                    # Extract the source name
                                    if "Tripadvisor" in full_text:
                                        review_source = "Tripadvisor"
                                    elif "Yelp" in full_text:
                                        review_source = "Yelp"
                                    elif "Facebook" in full_text:
                                        review_source = "Facebook"
                                    elif "Booking" in full_text:
                                        review_source = "Booking"
                                    
                                    print(f"Skipping {review_source} review: {full_text}")
                                    continue
                                else:
                                    review_source = "Google"  # Default to Google if no source specified
                                
                                print(f"Review source: {review_source}, Date: {review_date}")
                            else:
                                print(f"Could not extract date from DU9Pgb text: '{full_text}'")
                                # Try fallback methods
                                if "ago" in full_text.lower() or "her" in full_text.lower():
                                    # Try to split by common patterns
                                    if " on " in full_text:
                                        parts = full_text.split(" on ")
                                        if len(parts) >= 2:
                                            # Extract everything before " on " and after the rating
                                            before_on = parts[0].strip()
                                            # Remove rating pattern (e.g., "2/5 ")
                                            date_part = re.sub(r'^\d+/\d+\s*', '', before_on).strip()
                                            if date_part:
                                                review_date = date_part
                                                # Determine source from after " on "
                                                source_part = parts[1].strip()
                                                if "Google" in source_part:
                                                    review_source = "Google"
                                                else:
                                                    print(f"Skipping non-Google review from: {source_part}")
                                                    continue
                                            else:
                                                review_date = "Date not found"
                                                review_source = "Google"
                                    else:
                                        # No " on " found, assume it's Google and try to extract date
                                        date_part = re.sub(r'^\d+/\d+\s*', '', full_text).strip()
                                        review_date = date_part if date_part else "Date not found"
                                        review_source = "Google"
                                else:
                                    review_date = "Date not found"
                                    review_source = "Google"
                                    
                        except NoSuchElementException:
                            print("Could not find DU9Pgb element, trying fallback methods")
                            # Final fallback to original xRkPPb method
                            try:
                                date_element = review.find_element(By.XPATH, ".//span[@class='xRkPPb']")
                                date_text = date_element.text
                                print(f"Fallback: Found xRkPPb date element: '{date_text}'")
                                
                                if "Google" in date_text:
                                    if " on " in date_text:
                                        review_date = date_text.split(" on ")[0].strip()
                                    elif " auf " in date_text:
                                        review_date = date_text.split(" auf ")[0].strip()
                                    else:
                                        review_date = date_text.replace("Google", "").strip()
                                    review_source = "Google"
                                else:
                                    review_date = "Date not found"
                                    review_source = "Google"
                            except NoSuchElementException:
                                print("No date elements found, setting defaults")
                                review_date = "Date not found"
                                review_source = "Google"

                    # Skip the review if it's not from Google
                    if review_source != "Google":
                        continue

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
        return []
    finally:
        if 'browser' in locals() and browser:
            try:
                browser.quit()
                print("Browser closed.")
            except:
                pass

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
