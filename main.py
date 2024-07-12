from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium_recaptcha_solver import RecaptchaSolver
from dotenv import load_dotenv
import os
import time
import pandas as pd
import logging

# Load environment variables
load_dotenv()

# Setup download directory
download_dir = os.path.abspath("downloads")
if not os.path.exists(download_dir):
    os.makedirs(download_dir)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Configure Chrome options for automatic download
options = Options()
options.add_argument("--start-maximized")
options.add_argument("--headless")
options.add_experimental_option("prefs", {
    "download.default_directory": download_dir,
    "download.prompt_for_download": False,
    "download.directory_upgrade": True,
    "safebrowsing.enabled": True
})

# Initialize Selenium WebDriver
driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=options)

# Function to log in to Shutterstock
def login_shutterstock(driver):
    driver.get("https://www.shutterstock.com/")
    logging.info("Navigated to Shutterstock")
    login_button = WebDriverWait(driver, 15).until(
        EC.element_to_be_clickable((By.XPATH, "//a[@data-automation='loginButton']"))
    )
    login_button.click()
    logging.info("Clicked login button")

    WebDriverWait(driver, 15).until(
        EC.frame_to_be_available_and_switch_to_it((By.ID, "login-iframe"))
    )

    email_input = WebDriverWait(driver, 15).until(
        EC.visibility_of_element_located((By.XPATH, "//input[@data-test-id='email-input']"))
    )
    email_input.send_keys(os.getenv('SHUTTERSTOCK_EMAIL'))
    logging.info("Entered email")

    password_input = WebDriverWait(driver, 15).until(
        EC.visibility_of_element_located((By.XPATH, "//input[@data-test-id='password-input']"))
    )
    password_input.send_keys(os.getenv('SHUTTERSTOCK_PASSWORD'))
    logging.info("Entered password")

    login_form_submit = WebDriverWait(driver, 15).until(
        EC.element_to_be_clickable((By.XPATH, "//button[@data-test-id='login-form-submit-button']"))
    )
    login_form_submit.click()
    logging.info("Clicked submit button")
    password_input.send_keys(os.getenv('SHUTTERSTOCK_PASSWORD'))

    # Handle reCAPTCHA with 2Captcha
    captcha_iframe = WebDriverWait(driver, 15).until(
        EC.visibility_of_element_located((By.XPATH, "//iframe[@title='reCAPTCHA']"))
    )
    try:
        solver = RecaptchaSolver(driver)
        solver.click_recaptcha_v2(iframe=captcha_iframe)
        logging.info("reCAPTCHA solved successfully!")
    except Exception as e:
        logging.error(f"Error solving captcha: {e}")

    login_form_submit.click()
    time.sleep(15)  # Wait for the login process to complete
    logging.info("Login completed")

# Function to check if an image is already downloaded
def is_image_downloaded(image_title):
    for file_name in os.listdir(download_dir):
        if file_name.startswith(image_title):
            return True
    return False

# Function to check if a temporary .cr file is present
def is_temp_file_present():
    for file_name in os.listdir(download_dir):
        if file_name.endswith('.cr'):
            return True
    return False

# Function to delete temporary files with .cr extension
def delete_temporary_files():
    for file_name in os.listdir(download_dir):
        if file_name.endswith('.cr') or file_name.endswith('.crdownload'):
            os.remove(os.path.join(download_dir, file_name))
            logging.info(f"Deleted temporary file: {file_name}")

# Function to download images and save metadata
def download_images_and_save_metadata(driver):
    driver.get("https://www.shutterstock.com/catalog/licenses")
    logging.info("Navigated to licenses page")
    
    downloaded_images = set()  # To avoid re-downloading images
    all_metadata = []

    page_number = 1

    while True:
        try:
            # Wait for all elements to be present
            WebDriverWait(driver, 15).until(
                EC.presence_of_all_elements_located((By.XPATH, "//div[contains(@data-automation, 'asset-card_')]"))
            )
            logging.info(f"Page {page_number} loaded")

            images = driver.find_elements(By.XPATH, "//div[contains(@data-automation, 'asset-card_')]")
            logging.info(f"Found {len(images)} images on the page")

            for image_index in range(len(images)):
                try:
                    images = driver.find_elements(By.XPATH, "//div[contains(@data-automation, 'asset-card_')]")
                    image = images[image_index]
                    asset_id = image.find_element(By.XPATH, ".//div[@aria-label='asset_card_content']//div//span").text

                    image.click()
                    logging.info(f"Clicked image with asset ID: {asset_id}")
                    WebDriverWait(driver, 15).until(
                        EC.presence_of_element_located((By.XPATH, "//button[@aria-label='Redownload']"))
                    )

                    title_element = driver.find_element(By.XPATH, "//h1[@data-automation='asset-title']")
                    image_title = title_element.text.replace('/', '_').replace('\\', '_')  # Clean title for filename

                    # Check if image title exists in the metadata Excel file
                    if os.path.exists('image_metadata.xlsx'):
                        df_existing = pd.read_excel('image_metadata.xlsx')
                        if image_title in df_existing['Title'].values:
                            # Image title exists, check if the downloaded file exists and is complete
                            downloaded_file = df_existing.loc[df_existing['Title'] == image_title, 'Downloaded File'].values[0]
                            downloaded_file_path = os.path.join(download_dir, downloaded_file)
                            if os.path.exists(downloaded_file_path):
                                logging.info(f"Image {image_title} already downloaded and verified.")
                                close_button = WebDriverWait(driver, 15).until(
                                    EC.element_to_be_clickable((By.XPATH, "//button[@aria-label='Close']"))
                                )
                                close_button.click()
                                continue

                    if is_image_downloaded(image_title):
                        logging.info(f"Image {image_title} is already downloaded.")
                        close_button = WebDriverWait(driver, 15).until(
                            EC.element_to_be_clickable((By.XPATH, "//button[@aria-label='Close']"))
                        )
                        close_button.click()
                        continue

                    if is_temp_file_present():
                        logging.info(f"Temporary file detected for image {image_title}. Skipping download.")
                        close_button = WebDriverWait(driver, 15).until(
                            EC.element_to_be_clickable((By.XPATH, "//button[@aria-label='Close']"))
                        )
                        close_button.click()
                        continue

                    # Click the download button
                    try:
                        download_button = WebDriverWait(driver, 10).until(
                            EC.element_to_be_clickable((By.XPATH, "//button[@aria-label='Redownload']"))
                        )
                        download_button.click()

                        # Wait for the license dialog and checkbox
                        WebDriverWait(driver, 10).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, 'button[data-automation="LicenseDrawer_ReDownloadButton"]'))
                        )

                        # Check and click the checkbox if present
                        try:
                            checkbox     = WebDriverWait(driver, 5).until(
                                EC.presence_of_element_located((By.XPATH, "//span[@data-automation='licenseForm_confirmationCheckbox']"))
                            )
                            if checkbox:
                                checkbox.click()
                                logging.info(f"Clicked the confirmation checkbox for image {image_title}")
                            else:
                                logging.info(f"Confirmation checkbox not found for image {image_title}")
                        except Exception as e:
                            logging.error(f"Error clicking the confirmation checkbox for image {image_title}" + str(e))

                        # Click the download button again to initiate download
                        download_button = WebDriverWait(driver, 10).until(
                            EC.element_to_be_clickable((By.CSS_SELECTOR, 'button[data-automation="LicenseDrawer_ReDownloadButton"]'))
                        )
                        download_button.click()
                        logging.info(f"Clicked download button for image {image_title}")

                        # Wait for the download to complete
                        time.sleep(10)  # Adjust sleep time as necessary

                        # Verify the download by checking the download directory
                        downloaded_files = os.listdir(download_dir)
                        downloaded_files = [f for f in downloaded_files if f.endswith('.jpg')]

                        if downloaded_files:
                            logging.info(f"Downloaded files: {downloaded_files}")
                            all_metadata.append({
                                'Image ID': asset_id,
                                'Title': image_title,
                                'Downloaded File': downloaded_files[-1]  # Assuming the latest file is the one just downloaded
                            })
                            downloaded_images.add(asset_id)

                        # Close the image details
                        close_license_button = WebDriverWait(driver, 15).until(
                            EC.element_to_be_clickable((By.XPATH, "//button[@data-automation='LicenseDrawer_CloseButton']"))
                        )

                        close_license_button.click()

                        close_button = WebDriverWait(driver, 15).until(
                            EC.element_to_be_clickable((By.XPATH, "//button[@aria-label='Close']"))
                        )
                        close_button.click()

                    except Exception as e:
                        logging.error(f"Error downloading image: {e}")
                        continue

                except Exception as e:
                    logging.error(f"Error processing image: {e}")
                    continue
            
            try:
                next_button = WebDriverWait(driver, 15).until(
                    EC.element_to_be_clickable((By.XPATH, "//a[contains(text(), 'Next')]"))
                )
                if next_button.is_displayed():
                    next_button.click()
                    logging.info(f"Clicked next button to go to page {page_number + 1}")
                    page_number += 1
                else:
                    logging.info("No more pages to navigate.")
                    break
            except Exception as e:
                logging.info(f"No more pages to navigate. {e}")
                break
        except Exception as e:
            logging.error(f"Error loading page: {e}")
            break

    # Save metadata to Excel only for successfully downloaded images
    if all_metadata:
        df = pd.DataFrame(all_metadata)
        if os.path.exists('image_metadata.xlsx'):
            df_existing = pd.read_excel('image_metadata.xlsx')
            df = pd.concat([df_existing, df], ignore_index=True)

        df.to_excel('image_metadata.xlsx', index=False)
        logging.info("Saved metadata to Excel")

# Main script execution
delete_temporary_files()
login_shutterstock(driver)
download_images_and_save_metadata(driver)

# Close the browser after the task is completed
driver.quit()
logging.info("Browser quit and script completed.")
