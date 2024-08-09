#job_scraper.py
import streamlit as st
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from webdriver_manager.chrome import ChromeDriverManager
import time
import random
import logging
import pandas as pd
import io

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# List of user agents to rotate
USER_AGENTS = [
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4844.83 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4844.51 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Safari/605.1.15',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:97.0) Gecko/20100101 Firefox/97.0'
]

# Dictionary of Indeed domains
INDEED_DOMAINS = {
    "United States": "https://www.indeed.com",
    "Peru": "https://pe.indeed.com"
}

def get_random_user_agent():
    return random.choice(USER_AGENTS)

def create_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument(f"user-agent={get_random_user_agent()}")
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    return driver

def safe_find_element(driver, by, value):
    try:
        return driver.find_element(by, value)
    except NoSuchElementException:
        return None

def scrape_indeed_jobs(job_title, location="", days=None, country="United States"):
    base_url = INDEED_DOMAINS.get(country, INDEED_DOMAINS["United States"])
    params = f"/jobs?q={job_title.replace(' ', '+')}"
    if location:
        params += f"&l={location.replace(' ', '+')}"
    if days is not None:
        params += f"&fromage={days}"
    
    url = base_url + params
    logger.info(f"Searching URL: {url}")
    st.write(f"Searching URL: {url}")  # Debug info
    
    driver = create_driver()
    
    try:
        driver.get(url)
        try:
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CLASS_NAME, "job_seen_beacon")))
        except TimeoutException:
            logger.error("Timeout waiting for job cards to load")
            return []
        
        job_listings = []
        job_cards = driver.find_elements(By.CLASS_NAME, "job_seen_beacon")
        logger.info(f"Found {len(job_cards)} job cards on the page")
        
        for job in job_cards:
            try:
                title_elem = safe_find_element(job, By.CLASS_NAME, "jobTitle")
                title = title_elem.text.strip() if title_elem else "N/A"
                
                if all(word.lower() in title.lower() for word in job_title.split()):
                    company_elem = safe_find_element(job, By.CLASS_NAME, "companyName") or safe_find_element(job, By.CLASS_NAME, "company")
                    company = company_elem.text.strip() if company_elem else "N/A"
                    
                    location_elem = safe_find_element(job, By.CLASS_NAME, "companyLocation")
                    location = location_elem.text.strip() if location_elem else "N/A"
                    
                    summary_elem = safe_find_element(job, By.CLASS_NAME, "job-snippet")
                    summary = summary_elem.text.strip() if summary_elem else "N/A"
                    
                    link_elem = safe_find_element(job, By.CLASS_NAME, "jcs-JobTitle") or safe_find_element(job, By.TAG_NAME, "a")
                    link = link_elem.get_attribute('href') if link_elem else "N/A"
                    
                    job_listings.append({
                        'title': title,
                        'company': company,
                        'location': location,
                        'summary': summary,
                        'link': link
                    })
            except Exception as e:
                logger.error(f"Error processing job card: {e}")
        
        logger.info(f"Processed {len(job_listings)} job listings")
        st.write(f"Found {len(job_listings)} job listings")  # Debug info
        return job_listings
    
    finally:
        driver.quit()

def get_table_download_link(df):
    """Generates a link allowing the data in a given panda dataframe to be downloaded"""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Sheet1')
    binary_data = output.getvalue()
    return binary_data

st.title('Indeed Job Scraper')

country = st.selectbox('Select country:', list(INDEED_DOMAINS.keys()))
job_title = st.text_input('Enter the job title:')
location = st.text_input('Enter location (optional):')
time_options = [("No limit", None), ("1 day", 1), ("3 days", 3), ("7 days", 7), ("14 days", 14), ("30 days", 30)]
selected_time = st.selectbox('Show jobs from:', time_options, format_func=lambda x: x[0])

if st.button('Search Jobs'):
    if job_title:
        with st.spinner('Searching for jobs...'):
            time.sleep(random.uniform(1, 5))  # Random delay between 1 and 5 seconds
            jobs = scrape_indeed_jobs(job_title, location, selected_time[1], country)
        
        if jobs:
            st.success(f'Found {len(jobs)} job listings!')
            df = pd.DataFrame(jobs)
            
            # Display job listings
            for job in jobs:
                with st.expander(f"{job['title']} - {job['company']}"):
                    st.write(f"**Location:** {job['location']}")
                    st.write(f"**Summary:** {job['summary']}")
                    st.write(f"**Link:** {job['link']}")
            
            # Download button for Excel file
            excel_data = get_table_download_link(df)
            st.download_button(
                label="Download job listings as Excel",
                data=excel_data,
                file_name=f"job_listings_{job_title.replace(' ', '_')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.warning(f'No job listings found. Try broadening your search or adjusting the time range.')
    else:
        st.error('Please enter a job title to search.')

st.sidebar.write('''
Note: This scraper fetches job listings from Indeed.com based on your specified criteria.
The search uses partial matching, so results may include jobs with additional words in the title.
''')

# Add a timestamp to show when the app last updated
st.sidebar.write(f"Last updated: {time.strftime('%Y-%m-%d %H:%M:%S')}")