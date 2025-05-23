import streamlit as st
import pandas as pd
import io
import time
import re
import csv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager # Added for easier driver management
from selenium.webdriver.chrome.service import Service as ChromeService # Added for driver management
import os

# --- Helper Function to Convert DataFrame to CSV/Excel ---
# @st.cache_data # Cache the conversion to prevent re-running on every interaction
def convert_df_to_csv(df):
    output = io.StringIO()
    df.to_csv(output, index=False, encoding='utf-8')
    return output.getvalue()

# @st.cache_data # Cache the conversion
def convert_df_to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Reviews')
    # writer.save() # Not needed when using 'with' statement
    processed_data = output.getvalue()
    return processed_data

# --- Refactored Scraping Logic ---
# Takes business name and location as input, returns list of dicts
def scrape_google_maps_reviews(business_name, location, selected_stars):
    search_query = f"{business_name} {location}".replace(' ', '+')
    all_reviews = []
    business_data = {} # Initialize business data dict

    st.info(f"Starting scraping for: {business_name} in {location}")
    st.info(f"Search URL: https://www.google.com/maps/search/{search_query}")

    # Setup WebDriver (consider adding options like headless if needed)
    options = webdriver.ChromeOptions()
    options.add_argument("--disable-notifications")
    options.add_argument("--disable-infobars")
    options.add_argument("--headless")  # Change from --headless=new
    options.add_argument("--no-sandbox") # Often needed in containerized environments
    options.add_argument("--disable-dev-shm-usage") # Often needed in containerized environments
    options.add_argument("--window-size=1920,1080") # Specify window size for headless
    options.add_argument("--disable-gpu")

    # Set binary location for Streamlit Cloud
    if os.path.exists("/usr/bin/chromium-browser"):
        options.binary_location = "/usr/bin/chromium-browser"

    try:
        # Use webdriver-manager to handle driver installation/updates
        service = ChromeService(ChromeDriverManager().install())
        browser = webdriver.Chrome(service=service, options=options)
        browser.get(f"https://www.google.com/maps/search/{search_query}")
        time.sleep(4) # Increased wait time

        # Accept cookies
        try:
            accept_button = WebDriverWait(browser, 10).until( # Increased wait
                EC.element_to_be_clickable((By.XPATH, '//button[.//span[contains(text(),"Accept all") or contains(text(),"Alle akzeptieren")]]'))
            )
            accept_button.click()
            st.write("✓ Accepted cookies.")
            time.sleep(1) # Wait after click
        except (TimeoutException, NoSuchElementException):
            st.write("ℹ️ No cookie prompt found or already accepted.")

        # Extract business overview information
        try:
            st.write("Extracting business overview...")
            # --- Use the same selectors as scrape_defined.py ---
            # Business Name
            try:
                business_name = WebDriverWait(browser, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "h1.DUwDvf"))
                ).text
                business_data["Business Name"] = business_name
                st.write(f"  - Business Name: {business_name}")
            except Exception as e:
                st.write(f"  - Could not find business name: {e}")
                business_data["Business Name"] = business_name  # fallback to input

            # Average Rating
            try:
                rating_element = WebDriverWait(browser, 5).until(
                    EC.presence_of_element_located((By.XPATH, '//*[@id="QA0Szd"]/div/div/div[1]/div[2]/div/div[1]/div/div/div[2]/div/div[1]/div[2]/div/div[1]/div[2]/span[1]/span[1]'))
                )
                avg_rating = rating_element.text
                business_data["Average Rating"] = avg_rating
                st.write(f"  - Average Rating: {avg_rating}")
            except Exception as e:
                st.write(f"  - Could not find average rating: {e}")
                business_data["Average Rating"] = "N/A"

            # Total Reviews
            try:
                reviews_element = WebDriverWait(browser, 5).until(
                    EC.presence_of_element_located((By.XPATH, '//*[@id="QA0Szd"]/div/div/div[1]/div[2]/div/div[1]/div/div/div[2]/div/div[1]/div[2]/div/div[1]/div[2]/span[2]/span/span'))
                )
                total_reviews = reviews_element.text
                business_data["Total Reviews"] = total_reviews
                st.write(f"  - Total Reviews: {total_reviews}")
            except Exception as e:
                st.write(f"  - Could not find total reviews: {e}")
                business_data["Total Reviews"] = "N/A"

            # Price Level/Range (optional, as in scrape_defined.py)
            business_data["Price Level"] = "N/A"
            business_data["Price Range"] = "N/A"

        except Exception as e:
            st.warning(f"Could not extract all business overview details: {e}")

        # Click "Reviews" tab
        try:
            # Try multiple XPaths for the reviews button/tab
            review_button_xpaths = [
                '//button[contains(@aria-label, "Reviews for") or contains(@aria-label, "Rezensionen für")]', # More specific button
                '//button[@role="tab"][contains(., "Reviews") or contains(., "Rezensionen")]', # Tab role
                '//div[contains(@class, "Gpq6kf") and contains(@class, "NlVald") and (text()="Reviews" or text()="Rezensionen")]' # Original div approach
            ]
            review_button = None
            for xpath in review_button_xpaths:
                try:
                    review_button = WebDriverWait(browser, 10).until( # Increased wait
                        EC.element_to_be_clickable((By.XPATH, xpath))
                    )
                    st.write(f"✓ Found reviews button/tab using XPath: {xpath}")
                    break # Stop searching once found
                except (TimeoutException, NoSuchElementException):
                    continue # Try next XPath

            if review_button:
                review_button.click()
                st.write("✓ Clicked on Reviews tab.")
                time.sleep(3) # Wait for reviews to potentially load
            else:
                 st.error("❌ Could not find or click the Reviews button/tab.")
                 browser.quit()
                 return [] # Stop if we can't get to reviews

        except Exception as e:
            st.error(f"❌ Error clicking reviews tab: {e}")
            browser.quit()
            return []

        # Scroll through ALL reviews
        try:
            # Find the scrollable review pane
            # Common XPaths for the scrollable reviews div
            scrollable_div_xpaths = [
                '//div[@role="main"]/div[contains(@class, "review-dialog-list")]', # Common pattern in dialogs
                '//div[contains(@aria-label, "Reviews for") or contains(@aria-label, "Rezensionen für")]/following-sibling::div//div[contains(@class, "DxyBCb")]', # Relative to title
                '//div[contains(@class, "DxyBCb")]' # Original approach
            ]
            reviewArea = None
            for xpath in scrollable_div_xpaths:
                try:
                    reviewArea = WebDriverWait(browser, 10).until( # Increased wait
                        EC.presence_of_element_located((By.XPATH, xpath))
                    )
                    st.write(f"✓ Found scrollable review area using XPath: {xpath}")
                    break
                except (TimeoutException, NoSuchElementException):
                    continue

            if not reviewArea:
                st.error("❌ Could not find the scrollable review area.")
                browser.quit()
                return []

            previous_reviews_count = 0
            max_scroll_attempts = 50  # Limit scrolls
            no_new_reviews_count = 0
            scroll_pause_time = 2.5 # Slightly longer pause

            st.write("⏳ Starting scroll to load all reviews...")
            progress_bar = st.progress(0)
            status_text = st.empty()

            for attempt in range(max_scroll_attempts):
                reviewDivs = browser.find_elements(By.XPATH, "//div[@data-review-id]") # More specific selector for reviews
                current_reviews_count = len(reviewDivs)

                status_text.text(f"Scroll attempt {attempt+1}/{max_scroll_attempts}: Found {current_reviews_count} reviews...")

                if current_reviews_count == previous_reviews_count:
                    no_new_reviews_count += 1
                    if no_new_reviews_count >= 5: # Increase patience
                        st.write(f"✓ No new reviews found after {no_new_reviews_count} attempts. Assuming all loaded ({current_reviews_count} total).")
                        break
                else:
                    no_new_reviews_count = 0

                previous_reviews_count = current_reviews_count
                browser.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", reviewArea)
                time.sleep(scroll_pause_time)
                progress_bar.progress((attempt + 1) / max_scroll_attempts)

            status_text.text(f"✓ Scrolling finished. Found {previous_reviews_count} reviews in total.")
            progress_bar.progress(1.0)

        except Exception as e:
            st.warning(f"⚠️ Error during scrolling: {e}. Proceeding with currently loaded reviews.")

        # Extract reviews after scrolling
        base_url = browser.current_url.split('?')[0] # Get base URL for links
        reviewDivs = browser.find_elements(By.XPATH, "//div[@data-review-id]") # Use the specific selector again
        st.write(f"Extracting details from {len(reviewDivs)} loaded reviews...")

        extracted_count = 0
        processed_review_ids = set()  # <-- Add this line

        for review in reviewDivs:
            try:
                review_id = review.get_attribute("data-review-id")
                if not review_id or review_id in processed_review_ids:
                    continue  # Skip duplicates or missing IDs
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
                    continue  # Skip if no rating found

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
                st.warning(f"⚠️ Error processing one review: {e}")

        st.success(f"✓ Extracted {extracted_count} unique reviews with 3 stars or less.")

    except Exception as e:
        st.error(f"❌ An unexpected error occurred during the scraping process: {e}")
        st.exception(e) # Show full traceback in Streamlit for debugging
    finally:
        if 'browser' in locals() and browser:
            browser.quit()
            st.write("Browser closed.")

    return all_reviews

# --- Streamlit App UI ---
st.set_page_config(layout="wide") # Use wider layout
st.title("⭐ Google Maps Review Scraper ⭐")
st.markdown("""
Enter the business name and its general location (e.g., city, state).
The app will search on Google Maps, scroll through reviews, and extract those with **5 stars or less**.
You can then download the results as CSV or Excel.
""")

# Input fields in columns for better layout
col1, col2 = st.columns(2)
with col1:
    business_name_input = st.text_input("Enter Business Name:", placeholder="e.g., Edeka")
with col2:
    location_input = st.text_input("Enter Location:", placeholder="e.g., Berlin")

# Add this below the location_input
star_options = [1, 2, 3, 4, 5]
selected_stars = st.multiselect(
    "Select which star ratings to scrape:",
    options=star_options,
    default=[1, 2, 3]
)

# Scrape button
if st.button("🚀 Scrape Reviews", type="primary"):
    if business_name_input and location_input and selected_stars:
        if 'scraped_data' not in st.session_state or st.session_state.get('last_query') != (business_name_input, location_input, tuple(selected_stars)):
            with st.spinner(f"Scraping reviews for '{business_name_input}' in '{location_input}'... Please wait."):
                st.session_state.scraped_data = scrape_google_maps_reviews(business_name_input, location_input, selected_stars)
                st.session_state.last_query = (business_name_input, location_input, tuple(selected_stars))
                st.rerun()
        else:
            st.info("Using cached results for this query. Click again to re-scrape if needed (or clear cache).")
    else:
        st.warning("⚠️ Please enter both Business Name, Location, and select at least one star rating.")

# Display results and download buttons if data exists in session state
if 'scraped_data' in st.session_state and st.session_state.scraped_data:
    st.subheader("📊 Scraped Reviews")
    df = pd.DataFrame(st.session_state.scraped_data)

    # Display DataFrame (limit height)
    st.dataframe(df, height=400)

    st.subheader("⬇️ Download Data")
    col_dl_1, col_dl_2 = st.columns(2)

    # Prepare file names using the actual business name found, or the input if not found
    file_business_name = df['Business Name'].iloc[0] if not df.empty and df['Business Name'].iloc[0] != "N/A" else business_name_input
    file_prefix = re.sub(r'[^\w\s-]', '', file_business_name).strip().replace(' ', '_').replace('-', '_')


    with col_dl_1:
        csv_data = convert_df_to_csv(df)
        st.download_button(
            label="Download as CSV",
            data=csv_data,
            file_name=f"{file_prefix}_low_reviews.csv",
            mime="text/csv",
            key='csv_download'
        )

    with col_dl_2:
        excel_data = convert_df_to_excel(df)
        st.download_button(
            label="Download as Excel",
            data=excel_data,
            file_name=f"{file_prefix}_low_reviews.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key='excel_download'
        )
elif 'scraped_data' in st.session_state: # Check if scraping ran but found nothing
     st.info("ℹ️ No reviews with 3 stars or less were found for this business.")

st.markdown("---")
st.caption("Note: Web scraping can be fragile and may break if Google Maps changes its website structure. Use responsibly.")
st.caption("Made by Unternehmensschutz GmbH. For more info, visit [our website](https://unternehmensschutzonline.de/).")
