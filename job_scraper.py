"""
Job Description Scraper - COMPLETE FULL VERSION (WITH MULTI-SELECT)
=====================================================================
Features: Web scraping, full-page screenshots with text extraction,
application tracking, MULTI-SELECT archive/delete, multi-format export
PLUS: Uses OCR to auto-fill missing job information
"""

import requests
from bs4 import BeautifulSoup
import json
import csv
from datetime import datetime
from typing import Dict, List, Optional, Any
import logging
import os
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import subprocess
import platform
import time
from PIL import Image
import pytesseract
from pytesseract import pytesseract
import re

# ✨ OPTIONAL TESSERACT PATH (Comment out if not installed)
# For Windows:
try:
    pytesseract.pytesseract.pytesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
except:
    pass

# For Mac (uncomment if on Mac):
# pytesseract.pytesseract.pytesseract_cmd = '/usr/local/bin/tesseract'

# For Linux (uncomment if on Linux):
# pytesseract.pytesseract.pytesseract_cmd = '/usr/bin/tesseract'

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_yes_no(prompt: str = "Confirm? (y/n): ") -> bool:
    """Foolproof yes/no input."""
    while True:
        user_input = input(prompt).strip().lower()
        if user_input in ['y', 'yes', 'yep', 'yeah', 'true', '1']:
            return True
        elif user_input in ['n', 'no', 'nope', 'false', '0']:
            return False
        print("❌ Enter 'y' or 'n'")

def parse_multi_selection(input_str: str, max_num: int) -> List[int]:
    """Parse multi-select input like '1,3,5' or '1-5' into list of indices."""
    indices = set()
    
    try:
        parts = input_str.split(',')
        for part in parts:
            part = part.strip()
            if '-' in part:
                start, end = part.split('-')
                start = int(start.strip()) - 1
                end = int(end.strip())
                for i in range(start, end):
                    if 0 <= i < max_num:
                        indices.add(i)
            else:
                idx = int(part) - 1
                if 0 <= idx < max_num:
                    indices.add(idx)
        
        return sorted(list(indices))
    except:
        return []

class TextAnalyzer:
    """Analyzes extracted text to find job information."""
    
    @staticmethod
    def extract_salary(text: str) -> Optional[str]:
        """Extract salary from text."""
        patterns = [
            r'\$[\d,]+\s*-\s*\$[\d,]+',
            r'\$[\d,]+[KkMm]?/[yY]ear',
            r'[\d,]+\s*-\s*[\d,]+\s*[KkMm]',
            r'salary.*?\$[\d,]+',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(0).strip()
        return None
    
    @staticmethod
    def extract_location(text: str) -> Optional[str]:
        """Extract location from text."""
        patterns = [
            r'(?:Location|Based|based)[:\s]+([A-Za-z\s,]+?)(?:\n|$)',
            r'(New York|Los Angeles|Chicago|Houston|Phoenix|Philadelphia|San Antonio|San Diego|Dallas|San Jose|Austin|Jacksonville|Fort Worth|Columbus|Charlotte|San Francisco|Indianapolis|Seattle|Denver|Boston|Miami)[,\s]?(?:CA|TX|NY|FL|IL|OH|PA|WA|MA|CO|AZ|NV|NC|VA|TN|GA|MN|MO|MD)?',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                loc = match.group(1) if match.lastindex else match.group(0)
                return loc.strip()
        return None
    
    @staticmethod
    def extract_job_title(text: str) -> Optional[str]:
        """Extract job title from text."""
        patterns = [
            r'(?:Job Title|Position|Role)[:\s]+([A-Za-z\s/\+#]+?)(?:\n|$)',
            r'^([A-Za-z\s/\+#]{5,60})$',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.MULTILINE | re.IGNORECASE)
            if match:
                title = match.group(1) if match.lastindex else match.group(0)
                return title.strip()
        return None
    
    @staticmethod
    def extract_company(text: str) -> Optional[str]:
        """Extract company name from text."""
        patterns = [
            r'(?:Company|Employer|Hiring|Posted by)[:\s]+([A-Za-z0-9\s&\.\,]+?)(?:\n|$)',
            r'(?:at|@)\s+([A-Za-z0-9\s&\.\,]+?)(?:\n|$)',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                company = match.group(1) if match.lastindex else match.group(0)
                return company.strip()
        return None

class ScreenshotCapture:
    """Handles screenshot capture with OCR text extraction."""
    
    def __init__(self) -> None:
        self.screenshots_dir = 'job_screenshots'
        self.extracted_text_dir = 'extracted_text'
        os.makedirs(self.screenshots_dir, exist_ok=True)
        os.makedirs(self.extracted_text_dir, exist_ok=True)
        self.text_analyzer = TextAnalyzer()
        self.ocr_available = self._check_tesseract()  # ✨ CHECK IF TESSERACT IS AVAILABLE
    
    def _check_tesseract(self) -> bool:
        """Check if Tesseract is installed."""
        try:
            pytesseract.pytesseract.get_tesseract_version()
            print("✓ Tesseract OCR found - text extraction enabled")
            return True
        except Exception as e:
            logger.warning(f"⚠️  Tesseract not available: {str(e)}")
            print("⚠️  Tesseract OCR not installed - screenshots will be captured but text won't be extracted")
            print("    Install from: https://github.com/UB-Mannheim/tesseract/wiki")
            return False
    
    def extract_text_from_image(self, image_path: str) -> str:
        """Extract text from image using OCR."""
        if not self.ocr_available:
            return "[OCR not available - install Tesseract]"
        
        try:
            if not os.path.exists(image_path):
                return ""
            image = Image.open(image_path)
            text = pytesseract.image_to_string(image)
            return text.strip()
        except Exception as e:
            logger.error(f"Error extracting text: {str(e)}")
            return ""
    
    def analyze_text_for_info(self, text: str) -> Dict[str, Optional[str]]:
        """Analyze extracted text to find missing job info."""
        if not self.ocr_available or "[OCR not available" in text:
            return {
                'job_title': None,
                'company': None,
                'location': None,
                'salary': None,
            }
        
        return {
            'job_title': self.text_analyzer.extract_job_title(text),
            'company': self.text_analyzer.extract_company(text),
            'location': self.text_analyzer.extract_location(text),
            'salary': self.text_analyzer.extract_salary(text),
        }
    
    def capture_full_page_screenshot(self, url: str, job_id: str) -> Optional[Dict[str, Any]]:
        """Capture full page screenshots by scrolling with text extraction."""
        try:
            options = webdriver.ChromeOptions()
            options.add_argument('--headless')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--window-size=1920,1080')
            
            driver = webdriver.Chrome(options=options)
            print(f"📸 Capturing full page screenshots...")
            driver.get(url)
            
            WebDriverWait(driver, 10).until(EC.presence_of_all_elements_located((By.TAG_NAME, "body")))
            time.sleep(2)
            
            total_height = driver.execute_script("return document.body.parentNode.scrollHeight")
            viewport_height = driver.execute_script("return window.innerHeight")
            print(f"   Page height: {total_height}px, Viewport: {viewport_height}px")
            
            screenshot_data = {'paths': [], 'extracted_text': [], 'full_text': '', 'found_info': {}}
            scroll_position = 0
            screenshot_count = 0
            all_extracted_text = []
            
            while scroll_position < total_height and screenshot_count < 20:
                driver.execute_script(f"window.scrollTo(0, {scroll_position});")
                time.sleep(1)
                
                screenshot_filename = f"{self.screenshots_dir}/{job_id}_page_{screenshot_count}.png"
                driver.save_screenshot(screenshot_filename)
                screenshot_data['paths'].append(screenshot_filename)
                
                if self.ocr_available:  # ✨ ONLY EXTRACT IF AVAILABLE
                    extracted_text = self.extract_text_from_image(screenshot_filename)
                    screenshot_data['extracted_text'].append(extracted_text)
                    all_extracted_text.append(extracted_text)
                    print(f"   ✓ Captured page {screenshot_count + 1} - Extracted {len(extracted_text)} chars")
                else:
                    print(f"   ✓ Captured page {screenshot_count + 1}")
                
                screenshot_count += 1
                scroll_position += viewport_height * 0.8
            
            if self.ocr_available and all_extracted_text:
                screenshot_data['full_text'] = '\n\n'.join(all_extracted_text)
                screenshot_data['found_info'] = self.analyze_text_for_info(screenshot_data['full_text'])
            
            text_filename = f"{self.extracted_text_dir}/{job_id}_extracted_text.txt"
            with open(text_filename, 'w', encoding='utf-8') as f:
                f.write(screenshot_data['full_text'] if screenshot_data['full_text'] else "[OCR not available]")
            
            driver.quit()
            logger.info(f"✓ Captured {len(screenshot_data['paths'])} screenshots")
            return screenshot_data if screenshot_data['paths'] else None
        
        except Exception as e:
            logger.error(f"Error capturing screenshots: {str(e)}")
            return None
    
    def capture_single_screenshot(self, url: str, job_id: str) -> Optional[Dict[str, Any]]:
        """Capture single screenshot with text extraction."""
        try:
            options = webdriver.ChromeOptions()
            options.add_argument('--headless')
            options.add_argument('--no-sandbox')
            options.add_argument('--window-size=1920,1080')
            
            driver = webdriver.Chrome(options=options)
            print(f"📸 Capturing screenshot...")
            driver.get(url)
            
            WebDriverWait(driver, 10).until(EC.presence_of_all_elements_located((By.TAG_NAME, "body")))
            time.sleep(2)
            
            screenshot_filename = f"{self.screenshots_dir}/{job_id}_screenshot.png"
            driver.save_screenshot(screenshot_filename)
            
            if self.ocr_available:  # ✨ ONLY EXTRACT IF AVAILABLE
                extracted_text = self.extract_text_from_image(screenshot_filename)
            else:
                extracted_text = "[OCR not available - install Tesseract]"
            
            text_filename = f"{self.extracted_text_dir}/{job_id}_extracted_text.txt"
            with open(text_filename, 'w', encoding='utf-8') as f:
                f.write(extracted_text)
            
            driver.quit()
            logger.info(f"✓ Screenshot saved")
            
            found_info = self.analyze_text_for_info(extracted_text)
            
            return {'paths': [screenshot_filename], 'extracted_text': [extracted_text], 'full_text': extracted_text, 'found_info': found_info}
        
        except Exception as e:
            logger.error(f"Error: {str(e)}")
            return None
    
    def open_all_screenshots(self, screenshot_paths: List[str]) -> None:
        """Open screenshots in image viewer."""
        if not screenshot_paths:
            print("❌ No screenshots")
            return
        try:
            for path in screenshot_paths:
                if os.path.exists(path):
                    if platform.system() == 'Windows':
                        os.startfile(path)
                    elif platform.system() == 'Darwin':
                        subprocess.Popen(['open', path])
                    else:
                        subprocess.Popen(['xdg-open', path])
            print(f"✓ Opening {len(screenshot_paths)} screenshots...")
        except Exception as e:
            logger.error(f"Error: {str(e)}")

class ApplicationProgress:
    """Track application progress."""
    
    STATUS_NOT_APPLIED = "Not Applied"
    STATUS_APPLIED = "Applied"
    STATUS_INTERVIEW = "Interview"
    STATUS_OFFER = "Offer"
    STATUS_REJECTED = "Rejected"
    VALID_STATUSES = [STATUS_NOT_APPLIED, STATUS_APPLIED, STATUS_INTERVIEW, STATUS_OFFER, STATUS_REJECTED]
    
    def __init__(self) -> None:
        self.status: str = self.STATUS_NOT_APPLIED
        self.applied_date: Optional[str] = None
        self.interview_dates: List[str] = []
        self.offer_date: Optional[str] = None
        self.rejection_date: Optional[str] = None
        self.notes: List[Dict[str, str]] = []
        self.last_follow_up: Optional[str] = None
        self.next_follow_up: Optional[str] = None
    
    def set_status(self, status: str) -> None:
        if status not in self.VALID_STATUSES:
            raise ValueError(f"Invalid status")
        self.status = status
        if status == self.STATUS_APPLIED and not self.applied_date:
            self.applied_date = datetime.now().isoformat()
    
    def add_interview_date(self, interview_date: str) -> None:
        self.interview_dates.append(interview_date)
        if self.status != self.STATUS_INTERVIEW:
            self.status = self.STATUS_INTERVIEW
    
    def add_note(self, note: str) -> None:
        self.notes.append({'timestamp': datetime.now().isoformat(), 'text': note})
    
    def set_follow_up(self, follow_up_date: str) -> None:
        self.last_follow_up = datetime.now().isoformat()
        self.next_follow_up = follow_up_date
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'status': self.status,
            'applied_date': self.applied_date,
            'interview_dates': self.interview_dates,
            'offer_date': self.offer_date,
            'rejection_date': self.rejection_date,
            'notes': self.notes,
            'last_follow_up': self.last_follow_up,
            'next_follow_up': self.next_follow_up
        }
    
    def from_dict(self, data: Dict[str, Any]) -> None:
        self.status = data.get('status', self.STATUS_NOT_APPLIED)
        self.applied_date = data.get('applied_date')
        self.interview_dates = data.get('interview_dates', [])
        self.offer_date = data.get('offer_date')
        self.rejection_date = data.get('rejection_date')
        self.notes = data.get('notes', [])
        self.last_follow_up = data.get('last_follow_up')
        self.next_follow_up = data.get('next_follow_up')

class JobScraper:
    """Main job scraper class with auto-save."""
    
    def __init__(self) -> None:
        self.headers: Dict[str, str] = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        self.jobs_data: List[Dict[str, Any]] = []
        self.archived_jobs: List[Dict[str, Any]] = []
        self.screenshot_capture = ScreenshotCapture()
        self.auto_save = True  # ✨ AUTO-SAVE ENABLED
    
    def auto_save_all(self) -> None:
        """Auto-save to all databases (JSON, CSV, Excel)."""
        if not self.auto_save:
            return
        
        try:
            print("\n💾 Auto-saving to all databases...")
            self.save_to_json('jobs_data.json')
            self.save_to_csv('jobs_data.csv')
            self.save_to_excel('jobs_data.xlsx')
            print("✓ All databases updated!")
        except Exception as e:
            logger.error(f"Auto-save error: {str(e)}")
    
    def scrape_linkedin_job(self, job_url: str) -> Optional[Dict[str, Any]]:
        """Scrape LinkedIn job."""
        try:
            response = requests.get(job_url, headers=self.headers, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            
            job_info: Dict[str, Any] = {
                'id': self._generate_job_id(),
                'source': 'LinkedIn',
                'url': job_url,
                'scraped_at': datetime.now().isoformat(),
                'job_title': None,
                'company': None,
                'location': None,
                'job_description': None,
                'requirements': [],
                'application_process': None,
                'salary': None,
                'progress': ApplicationProgress(),
                'is_archived': False,
                'archived_at': None,
                'archive_reason': None,
                'screenshot_paths': [],
                'extracted_text': '',
                'extracted_text_file': None,
                'auto_filled_from_screenshot': False
            }
            
            title_elem = soup.find('h1', class_='top-card-layout__title')
            job_info['job_title'] = title_elem.text.strip() if title_elem else None
            
            company_elem = soup.find('a', class_='topcard__org-name-link')
            job_info['company'] = company_elem.text.strip() if company_elem else None
            
            location_elem = soup.find('span', class_='topcard__location')
            job_info['location'] = location_elem.text.strip() if location_elem else None
            
            desc_elem = soup.find('div', class_='show-more-less-html__markup')
            job_info['job_description'] = desc_elem.text.strip() if desc_elem else None
            
            req_items = soup.find_all('li', class_='description__job-criteria-item')
            job_info['requirements'] = [item.text.strip() for item in req_items]
            
            apply_btn = soup.find('button', {'aria-label': 'Easy Apply to'})
            job_info['application_process'] = 'Easy Apply Button' if apply_btn else 'Apply via LinkedIn Profile'
            
            logger.info(f"✓ Scraped LinkedIn job: {job_info['job_title']}")
            return job_info
        
        except Exception as e:
            logger.error(f"Error scraping LinkedIn: {str(e)}")
            return None
    
    def scrape_indeed_job(self, job_url: str) -> Optional[Dict[str, Any]]:
        """Scrape Indeed job."""
        try:
            response = requests.get(job_url, headers=self.headers, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            
            job_info: Dict[str, Any] = {
                'id': self._generate_job_id(),
                'source': 'Indeed',
                'url': job_url,
                'scraped_at': datetime.now().isoformat(),
                'job_title': None,
                'company': None,
                'location': None,
                'job_description': None,
                'requirements': [],
                'application_process': None,
                'salary': None,
                'progress': ApplicationProgress(),
                'is_archived': False,
                'archived_at': None,
                'archive_reason': None,
                'screenshot_paths': [],
                'extracted_text': '',
                'extracted_text_file': None,
                'auto_filled_from_screenshot': False
            }
            
            title_elem = soup.find('h1', class_='jobsearch-JobInfoHeader-jobTitle')
            job_info['job_title'] = title_elem.text.strip() if title_elem else None
            
            company_elem = soup.find('div', class_='jobsearch-InlineCompanyRating-companyHeader')
            if company_elem:
                company_link = company_elem.find('a')
                job_info['company'] = company_link.text.strip() if company_link else None
            
            location_elem = soup.find('div', class_='jobsearch-JobInfoHeader-subtitle')
            if location_elem:
                location_text = location_elem.text.strip()
                job_info['location'] = location_text.split('\n')[1] if '\n' in location_text else location_text
            
            salary_elem = soup.find('span', class_='salary-snippet')
            job_info['salary'] = salary_elem.text.strip() if salary_elem else None
            
            desc_elem = soup.find('div', class_='jobsearch-jobDescriptionText')
            job_info['job_description'] = desc_elem.text.strip() if desc_elem else None
            
            ul_items = soup.find_all('li')
            job_info['requirements'] = [item.text.strip() for item in ul_items[:10]]
            
            apply_btn = soup.find('button', class_='icl-Button')
            job_info['application_process'] = 'Direct via Indeed' if apply_btn else 'Company Website'
            
            logger.info(f"✓ Scraped Indeed job: {job_info['job_title']}")
            return job_info
        
        except Exception as e:
            logger.error(f"Error scraping Indeed: {str(e)}")
            return None
    
    def scrape_generic_job(self, job_url: str, config: Optional[Dict[str, str]] = None) -> Optional[Dict[str, Any]]:
        """Scrape generic job portal."""
        try:
            response = requests.get(job_url, headers=self.headers, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            
            job_info: Dict[str, Any] = {
                'id': self._generate_job_id(),
                'source': 'Generic',
                'url': job_url,
                'scraped_at': datetime.now().isoformat(),
                'job_title': None,
                'company': None,
                'location': None,
                'job_description': None,
                'requirements': [],
                'application_process': None,
                'salary': None,
                'progress': ApplicationProgress(),
                'is_archived': False,
                'archived_at': None,
                'archive_reason': None,
                'screenshot_paths': [],
                'extracted_text': '',
                'extracted_text_file': None,
                'auto_filled_from_screenshot': False
            }
            
            if config:
                for key, selector in config.items():
                    if selector:
                        elem = soup.select_one(selector)
                        if elem:
                            job_info[key] = elem.text.strip()
            else:
                h1_tags = soup.find_all('h1')
                job_info['job_title'] = h1_tags[0].text.strip() if h1_tags else None
            
            logger.info(f"✓ Scraped generic job: {job_info['job_title']}")
            return job_info
        
        except Exception as e:
            logger.error(f"Error scraping generic: {str(e)}")
            return None
    
    def _generate_job_id(self) -> str:
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
        return f"job_{timestamp}"
    
    def detect_job_source(self, job_url: str) -> str:
        url_lower = job_url.lower()
        if 'linkedin.com' in url_lower:
            return 'linkedin'
        elif 'indeed.com' in url_lower:
            return 'indeed'
        return 'generic'
    
    def auto_fill_from_screenshot(self, job: Dict[str, Any], found_info: Dict[str, Optional[str]]) -> None:
        """Auto-fill missing job info from screenshot text analysis."""
        filled_count = 0
        
        if not job.get('job_title') and found_info.get('job_title'):
            job['job_title'] = found_info['job_title']
            print(f"   ✓ Auto-filled Job Title: {found_info['job_title']}")
            filled_count += 1
        
        if not job.get('company') and found_info.get('company'):
            job['company'] = found_info['company']
            print(f"   ✓ Auto-filled Company: {found_info['company']}")
            filled_count += 1
        
        if not job.get('location') and found_info.get('location'):
            job['location'] = found_info['location']
            print(f"   ✓ Auto-filled Location: {found_info['location']}")
            filled_count += 1
        
        if not job.get('salary') and found_info.get('salary'):
            job['salary'] = found_info['salary']
            print(f"   ✓ Auto-filled Salary: {found_info['salary']}")
            filled_count += 1
        
        if filled_count > 0:
            job['auto_filled_from_screenshot'] = True
            logger.info(f"✓ Auto-filled {filled_count} fields from screenshot")
        else:
            if self.screenshot_capture.ocr_available:
                print("   ℹ️  No missing fields to auto-fill")
    
    def scrape_multiple_jobs(self, job_urls: List[str], sources: Optional[List[str]] = None, capture_screenshots: bool = False, full_page: bool = False) -> List[Dict[str, Any]]:
        """Scrape multiple jobs with screenshots and auto-fill."""
        if sources is None:
            sources = [self.detect_job_source(url) for url in job_urls]
        
        for url, source in zip(job_urls, sources):
            logger.info(f"Scraping {source} job: {url}")
            
            if source.lower() == 'linkedin':
                job_data = self.scrape_linkedin_job(url)
            elif source.lower() == 'indeed':
                job_data = self.scrape_indeed_job(url)
            else:
                job_data = self.scrape_generic_job(url)
            
            if job_data:
                if capture_screenshots:
                    if full_page:
                        screenshot_data = self.screenshot_capture.capture_full_page_screenshot(url, job_data['id'])
                    else:
                        screenshot_data = self.screenshot_capture.capture_single_screenshot(url, job_data['id'])
                    
                    if screenshot_data:
                        job_data['screenshot_paths'] = screenshot_data.get('paths', [])
                        job_data['extracted_text'] = screenshot_data.get('full_text', '')
                        job_data['extracted_text_file'] = f"extracted_text/{job_data['id']}_extracted_text.txt"
                        
                        if self.screenshot_capture.ocr_available:
                            print("\n📝 Auto-filling missing information from screenshot...")
                            self.auto_fill_from_screenshot(job_data, screenshot_data.get('found_info', {}))
                
                self.jobs_data.append(job_data)
        
        # ✨ AUTO-SAVE AFTER ADDING
        self.auto_save_all()
        
        return self.jobs_data
    
    def capture_job_screenshots(self, job_index: int, is_archived: bool = False, full_page: bool = True) -> None:
        """Capture screenshots for a job and auto-fill missing info."""
        jobs_list = self.archived_jobs if is_archived else self.jobs_data
        
        if 0 <= job_index < len(jobs_list):
            job = jobs_list[job_index]
            url = job.get('url')
            job_id = job.get('id')
            
            if not url:
                print("❌ Job URL not available")
                return
            
            if full_page:
                screenshot_data = self.screenshot_capture.capture_full_page_screenshot(url, job_id)
            else:
                screenshot_data = self.screenshot_capture.capture_single_screenshot(url, job_id)
            
            if screenshot_data:
                job['screenshot_paths'] = screenshot_data.get('paths', [])
                job['extracted_text'] = screenshot_data.get('full_text', '')
                job['extracted_text_file'] = f"extracted_text/{job_id}_extracted_text.txt"
                print(f"✓ Captured {len(screenshot_data.get('paths', []))} screenshots")
                
                if self.screenshot_capture.ocr_available:
                    print("\n📝 Auto-filling missing information from screenshot...")
                    self.auto_fill_from_screenshot(job, screenshot_data.get('found_info', {}))
                
                # ✨ AUTO-SAVE AFTER CAPTURING
                self.auto_save_all()
    
    def view_job_screenshots(self, job_index: int, is_archived: bool = False) -> None:
        """View job screenshots and extracted text."""
        jobs_list = self.archived_jobs if is_archived else self.jobs_data
        
        if 0 <= job_index < len(jobs_list):
            job = jobs_list[job_index]
            screenshot_paths = job.get('screenshot_paths', [])
            
            if not screenshot_paths:
                print("❌ No screenshots")
                if get_yes_no("Capture now? (y/n): "):
                    full = get_yes_no("Full page? (y/n): ")
                    self.capture_job_screenshots(job_index, is_archived, full_page=full)
                return
            
            print(f"\n📸 Opening {len(screenshot_paths)} screenshot(s)...")
            self.screenshot_capture.open_all_screenshots(screenshot_paths)
            
            if job.get('extracted_text'):
                print(f"\n📄 Extracted Text Preview:")
                print("="*80)
                text = job.get('extracted_text')[:500]
                print(f"{text}..." if len(job.get('extracted_text', '')) > 500 else text)
                print("="*80)
                
                if get_yes_no("\nView full text? (y/n): "):
                    full_text = job.get('extracted_text', '')
                    print("\n" + "="*80)
                    print("FULL EXTRACTED TEXT")
                    print("="*80)
                    print(full_text)
                    print("="*80)
    
    def edit_job(self, job_index: int, is_archived: bool = False) -> None:
        """Edit job information."""
        jobs_list = self.archived_jobs if is_archived else self.jobs_data
        
        if not (0 <= job_index < len(jobs_list)):
            logger.error(f"Invalid job index")
            return
        
        job = jobs_list[job_index]
        
        print("\n" + "="*80)
        print("EDIT JOB")
        print("="*80)
        print(f"\nEditing: {job.get('job_title', 'Unknown')}\n")
        
        auto_filled = " ✨ (Auto-filled from screenshot)" if job.get('auto_filled_from_screenshot') else ""
        print("1. Job Title: " + (job.get('job_title') or '❌') + auto_filled)
        print("2. Company: " + (job.get('company') or '❌'))
        print("3. Location: " + (job.get('location') or '❌'))
        print("4. Salary: " + (job.get('salary') or '❌'))
        print("5. Application Process: " + (job.get('application_process') or '❌'))
        print("6. URL: " + (job.get('url') or '❌'))
        print("7. Source: " + (job.get('source') or '❌'))
        
        ss_count = len(job.get('screenshot_paths', []))
        print(f"8. {'📸 View' if ss_count > 0 else '📷 Capture'} screenshots ({ss_count})")
        print("9. View description")
        print("10. View/Edit requirements")
        print("11. View extracted text")
        print("12. Done")
        
        modified = False
        
        while True:
            choice = input("\nSelect (1-12): ").strip()
            
            if choice == '1':
                new_val = input(f"Title ({job.get('job_title')}): ").strip()
                if new_val:
                    job['job_title'] = new_val
                    modified = True
                    print("✓ Updated")
            elif choice == '2':
                new_val = input(f"Company ({job.get('company')}): ").strip()
                if new_val:
                    job['company'] = new_val
                    modified = True
                    print("✓ Updated")
            elif choice == '3':
                new_val = input(f"Location ({job.get('location')}): ").strip()
                if new_val:
                    job['location'] = new_val
                    modified = True
                    print("✓ Updated")
            elif choice == '4':
                new_val = input(f"Salary ({job.get('salary')}): ").strip()
                if new_val:
                    job['salary'] = new_val
                    modified = True
                    print("✓ Updated")
            elif choice == '5':
                new_val = input(f"App Process ({job.get('application_process')}): ").strip()
                if new_val:
                    job['application_process'] = new_val
                    modified = True
                    print("✓ Updated")
            elif choice == '6':
                new_val = input(f"URL ({job.get('url')}): ").strip()
                if new_val:
                    job['url'] = new_val
                    modified = True
                    print("✓ Updated")
            elif choice == '7':
                print(f"Source: {job.get('source')} (Cannot edit)")
            elif choice == '8':
                if ss_count > 0:
                    self.view_job_screenshots(job_index, is_archived)
                else:
                    if get_yes_no("Capture full page? (y/n): "):
                        self.capture_job_screenshots(job_index, is_archived, full_page=True)
                    else:
                        self.capture_job_screenshots(job_index, is_archived, full_page=False)
            elif choice == '9':
                print("\n" + "="*40)
                print("DESCRIPTION")
                print("="*40)
                if job.get('job_description'):
                    print(job.get('job_description'))
                else:
                    print("❌ No description")
            elif choice == '10':
                print("\n" + "="*40)
                print("REQUIREMENTS")
                print("="*40)
                if job.get('requirements'):
                    for idx, req in enumerate(job.get('requirements'), 1):
                        print(f"{idx}. {req}")
                else:
                    print("❌ None")
            elif choice == '11':
                print("\n" + "="*40)
                print("EXTRACTED TEXT")
                print("="*40)
                if job.get('extracted_text'):
                    print(job.get('extracted_text'))
                else:
                    print("❌ None")
            elif choice == '12':
                print("✓ Saved")
                break
        
        # ✨ AUTO-SAVE AFTER EDITING
        if modified:
            self.auto_save_all()
    
    def view_job_details(self, job_index: int, is_archived: bool = False) -> None:
        """View complete job details."""
        jobs_list = self.archived_jobs if is_archived else self.jobs_data
        
        if not (0 <= job_index < len(jobs_list)):
            logger.error(f"Invalid job index")
            return
        
        job = jobs_list[job_index]
        progress = job.get('progress')
        
        print("\n" + "="*80)
        print("COMPLETE JOB DETAILS")
        print("="*80)
        
        auto_filled = " ✨" if job.get('auto_filled_from_screenshot') else ""
        print(f"\n📌 Basic Info{auto_filled}:")
        print(f"   Title: {job.get('job_title') or '❌'}")
        print(f"   Company: {job.get('company') or '❌'}")
        print(f"   Location: {job.get('location') or '❌'}")
        print(f"   Salary: {job.get('salary') or 'N/A'}")
        print(f"   Source: {job.get('source')}")
        print(f"   URL: {job.get('url') or '❌'}")
        
        ss_count = len(job.get('screenshot_paths', []))
        print(f"   📸 Screenshots: {ss_count} captured" if ss_count > 0 else "   ❌ No screenshots")
        
        print(f"\n📝 Application Info:")
        print(f"   Method: {job.get('application_process') or '❌'}")
        emoji = self._get_status_emoji(progress.status if isinstance(progress, ApplicationProgress) else '')
        status = progress.status if isinstance(progress, ApplicationProgress) else 'Unknown'
        print(f"   Status: {emoji} {status}")
        
        if isinstance(progress, ApplicationProgress):
            print(f"   Applied: {progress.applied_date or 'Not yet'}")
            if progress.interview_dates:
                print(f"   Interviews: {', '.join(progress.interview_dates)}")
            if progress.next_follow_up:
                print(f"   Follow-up: {progress.next_follow_up}")
        
        print(f"\n📋 Requirements:")
        if job.get('requirements'):
            for idx, req in enumerate(job.get('requirements'), 1):
                print(f"   {idx}. {req}")
        else:
            print("   ❌ None")
        
        print(f"\n📄 Description:")
        if job.get('job_description'):
            desc = job.get('job_description')
            print(f"   {desc[:300]}..." if len(desc) > 300 else f"   {desc}")
        else:
            print("   ❌ None")
        
        print(f"\n🖼️  Extracted Text:")
        if job.get('extracted_text'):
            ext = job.get('extracted_text')
            print(f"   {ext[:300]}..." if len(ext) > 300 else f"   {ext}")
        else:
            print("   ❌ None")
        
        if is_archived and job.get('archived_at'):
            print(f"\n🗂️  Archive Info:")
            print(f"   Archived: {job.get('archived_at')}")
            if job.get('archive_reason'):
                print(f"   Reason: {job.get('archive_reason')}")
        
        print("\n" + "="*80)
    
    def archive_job(self, job_index: int, reason: Optional[str] = None) -> None:
        """Archive a single job."""
        if 0 <= job_index < len(self.jobs_data):
            job = self.jobs_data[job_index]
            job['is_archived'] = True
            job['archived_at'] = datetime.now().isoformat()
            job['archive_reason'] = reason
            
            self.archived_jobs.append(job)
            self.jobs_data.pop(job_index)
            
            logger.info(f"✓ Archived: {job.get('job_title')}")
            print(f"✓ Archived: {job.get('job_title')}")
            
            # ✨ AUTO-SAVE AFTER ARCHIVING
            self.auto_save_all()
    
    def archive_multiple_jobs(self, indices: List[int], reason: Optional[str] = None) -> None:
        """Archive multiple jobs at once."""
        if not indices:
            print("❌ No jobs selected")
            return
        
        indices.sort(reverse=True)
        
        archived_count = 0
        for idx in indices:
            if 0 <= idx < len(self.jobs_data):
                job = self.jobs_data[idx]
                job['is_archived'] = True
                job['archived_at'] = datetime.now().isoformat()
                job['archive_reason'] = reason
                
                self.archived_jobs.append(job)
                self.jobs_data.pop(idx)
                
                archived_count += 1
                print(f"   ✓ Archived: {job.get('job_title')}")
        
        logger.info(f"✓ Archived {archived_count} jobs")
        print(f"\n✓ Successfully archived {archived_count} job(s)")
        
        # ✨ AUTO-SAVE AFTER ARCHIVING MULTIPLE
        self.auto_save_all()
    
    def unarchive_job(self, archived_index: int) -> None:
        """Restore archived job."""
        if 0 <= archived_index < len(self.archived_jobs):
            job = self.archived_jobs[archived_index]
            job['is_archived'] = False
            
            self.jobs_data.append(job)
            self.archived_jobs.pop(archived_index)
            
            logger.info(f"✓ Restored: {job.get('job_title')}")
            print(f"✓ Restored: {job.get('job_title')}")
            
            # ✨ AUTO-SAVE AFTER RESTORING
            self.auto_save_all()
    
    def delete_job(self, job_index: int, is_archived: bool = False) -> None:
        """Delete a single job permanently from memory AND all files."""
        jobs_list = self.archived_jobs if is_archived else self.jobs_data
        
        if 0 <= job_index < len(jobs_list):
            job = jobs_list[job_index]
            job_title = job.get('job_title')
            job_id = job.get('id')
            
            for path in job.get('screenshot_paths', []):
                if path and os.path.exists(path):
                    try:
                        os.remove(path)
                        logger.info(f"✓ Deleted: {path}")
                    except:
                        pass
            
            text_file = f"extracted_text/{job_id}_extracted_text.txt"
            if os.path.exists(text_file):
                try:
                    os.remove(text_file)
                except:
                    pass
            
            jobs_list.pop(job_index)
            self._delete_from_files(job_id)
            
            logger.info(f"✓ Deleted: {job_title}")
            print(f"✓ Deleted '{job_title}' from all sources")
            
            # ✨ AUTO-SAVE AFTER DELETING
            self.auto_save_all()
    
    def delete_multiple_jobs(self, indices: List[int], is_archived: bool = False) -> None:
        """Delete multiple jobs at once (permanently from ALL files)."""
        jobs_list = self.archived_jobs if is_archived else self.jobs_data
        
        if not indices:
            print("❌ No jobs selected")
            return
        
        indices.sort(reverse=True)
        
        deleted_count = 0
        for idx in indices:
            if 0 <= idx < len(jobs_list):
                job = jobs_list[idx]
                job_title = job.get('job_title')
                job_id = job.get('id')
                
                for path in job.get('screenshot_paths', []):
                    if path and os.path.exists(path):
                        try:
                            os.remove(path)
                        except:
                            pass
                
                text_file = f"extracted_text/{job_id}_extracted_text.txt"
                if os.path.exists(text_file):
                    try:
                        os.remove(text_file)
                    except:
                        pass
                
                jobs_list.pop(idx)
                self._delete_from_files(job_id)
                
                deleted_count += 1
                print(f"   ✓ Deleted: {job_title}")
        
        logger.info(f"✓ Deleted {deleted_count} jobs from all sources")
        print(f"\n✓ Successfully deleted {deleted_count} job(s) from all sources")
        
        # ✨ AUTO-SAVE AFTER DELETING MULTIPLE
        self.auto_save_all()
    
    def _delete_from_files(self, job_id: str) -> None:
        """Delete job from all saved files."""
        self._delete_from_json(job_id)
        self._delete_from_csv(job_id)
        self._delete_from_excel(job_id)
    
    def _delete_from_json(self, job_id: str) -> None:
        """Delete from JSON file."""
        filename = 'jobs_data.json'
        try:
            if not os.path.exists(filename):
                return
            with open(filename, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if not isinstance(data, list):
                data = [data]
            filtered = [j for j in data if j.get('id') != job_id]
            if len(filtered) < len(data):
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(filtered, f, indent=4, ensure_ascii=False)
                logger.info(f"✓ Deleted from JSON")
        except Exception as e:
            logger.error(f"JSON error: {str(e)}")
    
    def _delete_from_csv(self, job_id: str) -> None:
        """Delete from CSV file."""
        filename = 'jobs_data.csv'
        try:
            if not os.path.exists(filename):
                return
            df = pd.read_csv(filename)
            if 'id' not in df.columns:
                return
            orig_len = len(df)
            df = df[df['id'] != job_id]
            if len(df) < orig_len:
                df.to_csv(filename, index=False, encoding='utf-8')
                logger.info(f"✓ Deleted from CSV")
        except Exception as e:
            logger.error(f"CSV error: {str(e)}")
    
    def _delete_from_excel(self, job_id: str) -> None:
        """Delete from Excel file."""
        filename = 'jobs_data.xlsx'
        try:
            if not os.path.exists(filename):
                return
            df = pd.read_excel(filename, sheet_name='Jobs')
            if 'ID' not in df.columns:
                return
            orig_len = len(df)
            df = df[df['ID'] != job_id]
            if len(df) < orig_len:
                with pd.ExcelWriter(filename, engine='openpyxl') as writer:
                    df.to_excel(writer, sheet_name='Jobs', index=False)
                logger.info(f"✓ Deleted from Excel")
        except Exception as e:
            logger.error(f"Excel error: {str(e)}")
    
    def get_active_jobs_count(self) -> int:
        return len(self.jobs_data)
    
    def get_archived_jobs_count(self) -> int:
        return len(self.archived_jobs)
    
    def load_from_json(self, filename: str = 'jobs_data.json') -> int:
        """Load from JSON."""
        try:
            if not os.path.exists(filename):
                return 0
            with open(filename, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if not isinstance(data, list):
                data = [data]
            
            count = 0
            for jd in data:
                job: Dict[str, Any] = {
                    'id': jd.get('id', self._generate_job_id()),
                    'source': jd.get('source'),
                    'url': jd.get('url'),
                    'scraped_at': jd.get('scraped_at'),
                    'job_title': jd.get('job_title'),
                    'company': jd.get('company'),
                    'location': jd.get('location'),
                    'job_description': jd.get('job_description'),
                    'requirements': jd.get('requirements', []),
                    'application_process': jd.get('application_process'),
                    'salary': jd.get('salary'),
                    'progress': ApplicationProgress(),
                    'is_archived': jd.get('is_archived', False),
                    'archived_at': jd.get('archived_at'),
                    'archive_reason': jd.get('archive_reason'),
                    'screenshot_paths': jd.get('screenshot_paths', []),
                    'extracted_text': jd.get('extracted_text', ''),
                    'extracted_text_file': jd.get('extracted_text_file'),
                    'auto_filled_from_screenshot': jd.get('auto_filled_from_screenshot', False)
                }
                
                if 'progress' in jd and isinstance(jd['progress'], dict):
                    job['progress'].from_dict(jd['progress'])
                
                if job.get('is_archived'):
                    self.archived_jobs.append(job)
                else:
                    self.jobs_data.append(job)
                count += 1
            
            logger.info(f"✓ Loaded {count} jobs from JSON")
            return count
        except Exception as e:
            logger.error(f"JSON load error: {str(e)}")
            return 0
    
    def load_from_csv(self, filename: str = 'jobs_data.csv') -> int:
        """Load from CSV."""
        try:
            if not os.path.exists(filename):
                return 0
            df = pd.read_csv(filename)
            count = 0
            
            for idx, row in df.iterrows():
                job: Dict[str, Any] = {
                    'id': row.get('id') if 'id' in df.columns else self._generate_job_id(),
                    'source': row.get('source', 'Generic'),
                    'url': row.get('url'),
                    'scraped_at': row.get('scraped_at'),
                    'job_title': row.get('job_title'),
                    'company': row.get('company'),
                    'location': row.get('location'),
                    'job_description': row.get('job_description'),
                    'requirements': [],
                    'application_process': row.get('application_process'),
                    'salary': row.get('salary'),
                    'progress': ApplicationProgress(),
                    'is_archived': bool(row.get('is_archived')) if 'is_archived' in df.columns else False,
                    'archived_at': row.get('archived_at') if 'archived_at' in df.columns else None,
                    'archive_reason': row.get('archive_reason') if 'archive_reason' in df.columns else None,
                    'screenshot_paths': [],
                    'extracted_text': row.get('extracted_text', '') if 'extracted_text' in df.columns else '',
                    'extracted_text_file': row.get('extracted_text_file') if 'extracted_text_file' in df.columns else None,
                    'auto_filled_from_screenshot': bool(row.get('auto_filled_from_screenshot')) if 'auto_filled_from_screenshot' in df.columns else False
                }
                
                if pd.notna(row.get('status')):
                    job['progress'].status = row.get('status')
                if pd.notna(row.get('applied_date')):
                    job['progress'].applied_date = row.get('applied_date')
                if pd.notna(row.get('interview_dates')) and str(row.get('interview_dates')) != 'nan':
                    dates_str = str(row.get('interview_dates'))
                    if dates_str:
                        job['progress'].interview_dates = [d.strip() for d in dates_str.split(';')]
                if pd.notna(row.get('next_follow_up')):
                    job['progress'].next_follow_up = row.get('next_follow_up')
                
                if job.get('is_archived'):
                    self.archived_jobs.append(job)
                else:
                    self.jobs_data.append(job)
                count += 1
            
            logger.info(f"✓ Loaded {count} jobs from CSV")
            return count
        except Exception as e:
            logger.error(f"CSV load error: {str(e)}")
            return 0
    
    def load_from_excel(self, filename: str = 'jobs_data.xlsx') -> int:
        """Load from Excel."""
        try:
            if not os.path.exists(filename):
                return 0
            df = pd.read_excel(filename, sheet_name='Jobs')
            count = 0
            
            for idx, row in df.iterrows():
                job: Dict[str, Any] = {
                    'id': row.get('ID') if 'ID' in df.columns else self._generate_job_id(),
                    'source': row.get('Source', 'Generic'),
                    'url': row.get('URL'),
                    'scraped_at': row.get('Scraped At'),
                    'job_title': row.get('Job Title'),
                    'company': row.get('Company'),
                    'location': row.get('Location'),
                    'job_description': row.get('Description'),
                    'requirements': [],
                    'application_process': row.get('Application Process'),
                    'salary': row.get('Salary'),
                    'progress': ApplicationProgress(),
                    'is_archived': bool(row.get('Is Archived')) if 'Is Archived' in df.columns else False,
                    'archived_at': row.get('Archived At') if 'Archived At' in df.columns else None,
                    'archive_reason': row.get('Archive Reason') if 'Archive Reason' in df.columns else None,
                    'screenshot_paths': [],
                    'extracted_text': row.get('Extracted Text', '') if 'Extracted Text' in df.columns else '',
                    'extracted_text_file': row.get('Extracted Text File') if 'Extracted Text File' in df.columns else None,
                    'auto_filled_from_screenshot': bool(row.get('Auto Filled')) if 'Auto Filled' in df.columns else False
                }
                
                if pd.notna(row.get('Status')):
                    job['progress'].status = row.get('Status')
                if pd.notna(row.get('Applied Date')):
                    job['progress'].applied_date = row.get('Applied Date')
                if pd.notna(row.get('Interview Dates')) and str(row.get('Interview Dates')) != 'nan':
                    dates_str = str(row.get('Interview Dates'))
                    if dates_str:
                        job['progress'].interview_dates = [d.strip() for d in dates_str.split(';')]
                if pd.notna(row.get('Next Follow-up')):
                    job['progress'].next_follow_up = row.get('Next Follow-up')
                
                if job.get('is_archived'):
                    self.archived_jobs.append(job)
                else:
                    self.jobs_data.append(job)
                count += 1
            
            logger.info(f"✓ Loaded {count} jobs from Excel")
            return count
        except Exception as e:
            logger.error(f"Excel load error: {str(e)}")
            return 0
    
    def update_job_progress(self, job_index: int, new_status: str, notes: Optional[str] = None) -> None:
        """Update progress."""
        if 0 <= job_index < len(self.jobs_data):
            job = self.jobs_data[job_index]
            job['progress'].set_status(new_status)
            if notes:
                job['progress'].add_note(notes)
            print(f"✓ Status: {new_status}")
            
            # ✨ AUTO-SAVE AFTER UPDATING PROGRESS
            self.auto_save_all()
    
    def add_interview_date(self, job_index: int, date: str) -> None:
        """Add interview date."""
        if 0 <= job_index < len(self.jobs_data):
            self.jobs_data[job_index]['progress'].add_interview_date(date)
            print(f"✓ Interview: {date}")
            
            # ✨ AUTO-SAVE AFTER ADDING INTERVIEW
            self.auto_save_all()
    
    def add_note(self, job_index: int, note: str) -> None:
        """Add note."""
        if 0 <= job_index < len(self.jobs_data):
            self.jobs_data[job_index]['progress'].add_note(note)
            print(f"✓ Note added")
            
            # ✨ AUTO-SAVE AFTER ADDING NOTE
            self.auto_save_all()
    
    def set_follow_up(self, job_index: int, date: str) -> None:
        """Set follow-up."""
        if 0 <= job_index < len(self.jobs_data):
            self.jobs_data[job_index]['progress'].set_follow_up(date)
            print(f"✓ Follow-up: {date}")
            
            # ✨ AUTO-SAVE AFTER SETTING FOLLOW-UP
            self.auto_save_all()
    
    def _serialize_job_data(self, job: Dict[str, Any]) -> Dict[str, Any]:
        """Serialize job."""
        ser = job.copy()
        if isinstance(ser.get('progress'), ApplicationProgress):
            ser['progress'] = ser['progress'].to_dict()
        return ser
    
    def _get_all_jobs(self) -> List[Dict[str, Any]]:
        return self.jobs_data + self.archived_jobs
    
    def save_to_json(self, filename: str = 'jobs_data.json') -> None:
        """Save to JSON."""
        try:
            jobs = self._get_all_jobs()
            data = [self._serialize_job_data(j) for j in jobs]
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            logger.info(f"✓ Saved {len(jobs)} to JSON")
        except Exception as e:
            logger.error(f"Save error: {str(e)}")
    
    def append_to_json(self, filename: str = 'jobs_data.json') -> None:
        """Append to JSON."""
        try:
            existing = []
            if os.path.exists(filename):
                try:
                    with open(filename, 'r', encoding='utf-8') as f:
                        existing = json.load(f)
                        if not isinstance(existing, list):
                            existing = [existing]
                except:
                    existing = []
            
            jobs = self._get_all_jobs()
            new_data = [self._serialize_job_data(j) for j in jobs]
            combined = existing + new_data
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(combined, f, indent=4, ensure_ascii=False)
            
            logger.info(f"✓ Appended {len(jobs)}")
            print(f"✓ Appended {len(jobs)} jobs")
        except Exception as e:
            logger.error(f"Append error: {str(e)}")
            print(f"❌ Error: {str(e)}")
    
    def save_to_csv(self, filename: str = 'jobs_data.csv') -> None:
        """Save to CSV."""
        try:
            jobs = self._get_all_jobs()
            if not jobs:
                return
            
            data = []
            for job in jobs:
                row = {
                    'id': job.get('id'),
                    'job_title': job.get('job_title'),
                    'company': job.get('company'),
                    'location': job.get('location'),
                    'source': job.get('source'),
                    'salary': job.get('salary'),
                    'application_process': job.get('application_process'),
                    'url': job.get('url'),
                    'status': job['progress'].status if isinstance(job.get('progress'), ApplicationProgress) else '',
                    'applied_date': job['progress'].applied_date if isinstance(job.get('progress'), ApplicationProgress) else '',
                    'interview_dates': '; '.join(job['progress'].interview_dates) if isinstance(job.get('progress'), ApplicationProgress) else '',
                    'next_follow_up': job['progress'].next_follow_up if isinstance(job.get('progress'), ApplicationProgress) else '',
                    'is_archived': job.get('is_archived'),
                    'archived_at': job.get('archived_at'),
                    'archive_reason': job.get('archive_reason'),
                    'extracted_text': job.get('extracted_text', '')[:100] if job.get('extracted_text') else '',
                    'auto_filled_from_screenshot': job.get('auto_filled_from_screenshot', False)
                }
                data.append(row)
            
            keys = data[0].keys()
            with open(filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=keys)
                writer.writeheader()
                writer.writerows(data)
            
            logger.info(f"✓ Saved {len(jobs)}")
        except Exception as e:
            logger.error(f"CSV error: {str(e)}")
    
    def append_to_csv(self, filename: str = 'jobs_data.csv') -> None:
        """Append to CSV."""
        try:
            jobs = self._get_all_jobs()
            if not jobs:
                return
            
            data = []
            for job in jobs:
                row = {
                    'id': job.get('id'),
                    'job_title': job.get('job_title'),
                    'company': job.get('company'),
                    'location': job.get('location'),
                    'source': job.get('source'),
                    'salary': job.get('salary'),
                    'application_process': job.get('application_process'),
                    'url': job.get('url'),
                    'status': job['progress'].status if isinstance(job.get('progress'), ApplicationProgress) else '',
                    'applied_date': job['progress'].applied_date if isinstance(job.get('progress'), ApplicationProgress) else '',
                    'interview_dates': '; '.join(job['progress'].interview_dates) if isinstance(job.get('progress'), ApplicationProgress) else '',
                    'next_follow_up': job['progress'].next_follow_up if isinstance(job.get('progress'), ApplicationProgress) else '',
                    'is_archived': job.get('is_archived'),
                    'archived_at': job.get('archived_at'),
                    'archive_reason': job.get('archive_reason'),
                    'extracted_text': job.get('extracted_text', '')[:100] if job.get('extracted_text') else '',
                    'auto_filled_from_screenshot': job.get('auto_filled_from_screenshot', False)
                }
                data.append(row)
            
            exists = os.path.exists(filename)
            keys = data[0].keys()
            
            with open(filename, 'a', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=keys)
                if not exists:
                    writer.writeheader()
                writer.writerows(data)
            
            logger.info(f"✓ Appended {len(jobs)}")
        except Exception as e:
            logger.error(f"CSV error: {str(e)}")
    
    def save_to_excel(self, filename: str = 'jobs_data.xlsx') -> None:
        """Save to Excel."""
        try:
            jobs = self._get_all_jobs()
            if not jobs:
                return
            
            data = []
            for job in jobs:
                prog = job.get('progress')
                row = {
                    'ID': job.get('id'),
                    'Job Title': job.get('job_title'),
                    'Company': job.get('company'),
                    'Location': job.get('location'),
                    'Source': job.get('source'),
                    'Salary': job.get('salary'),
                    'Application Process': job.get('application_process'),
                    'URL': job.get('url'),
                    'Status': prog.status if isinstance(prog, ApplicationProgress) else '',
                    'Applied Date': prog.applied_date if isinstance(prog, ApplicationProgress) else '',
                    'Interview Dates': '; '.join(prog.interview_dates) if isinstance(prog, ApplicationProgress) else '',
                    'Next Follow-up': prog.next_follow_up if isinstance(prog, ApplicationProgress) else '',
                    'Notes': len(prog.notes) if isinstance(prog, ApplicationProgress) else 0,
                    'Is Archived': job.get('is_archived'),
                    'Archived At': job.get('archived_at'),
                    'Archive Reason': job.get('archive_reason'),
                    'Has Screenshot': len(job.get('screenshot_paths', [])) > 0,
                    'Auto Filled': job.get('auto_filled_from_screenshot', False)
                }
                data.append(row)
            
            df = pd.DataFrame(data)
            with pd.ExcelWriter(filename, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='Jobs', index=False)
                ws = writer.sheets['Jobs']
                for col in ws.columns:
                    ws.column_dimensions[col[0].column_letter].width = 20
            
            logger.info(f"✓ Saved {len(jobs)}")
        except Exception as e:
            logger.error(f"Excel error: {str(e)}")
    
    def append_to_excel(self, filename: str = 'jobs_data.xlsx') -> None:
        """Append to Excel."""
        try:
            jobs = self._get_all_jobs()
            if not jobs:
                return
            
            data = []
            for job in jobs:
                prog = job.get('progress')
                row = {
                    'ID': job.get('id'),
                    'Job Title': job.get('job_title'),
                    'Company': job.get('company'),
                    'Location': job.get('location'),
                    'Source': job.get('source'),
                    'Salary': job.get('salary'),
                    'Application Process': job.get('application_process'),
                    'URL': job.get('url'),
                    'Status': prog.status if isinstance(prog, ApplicationProgress) else '',
                    'Applied Date': prog.applied_date if isinstance(prog, ApplicationProgress) else '',
                    'Interview Dates': '; '.join(prog.interview_dates) if isinstance(prog, ApplicationProgress) else '',
                    'Next Follow-up': prog.next_follow_up if isinstance(prog, ApplicationProgress) else '',
                    'Notes': len(prog.notes) if isinstance(prog, ApplicationProgress) else 0,
                    'Is Archived': job.get('is_archived'),
                    'Archived At': job.get('archived_at'),
                    'Archive Reason': job.get('archive_reason'),
                    'Has Screenshot': len(job.get('screenshot_paths', [])) > 0,
                    'Auto Filled': job.get('auto_filled_from_screenshot', False)
                }
                data.append(row)
            
            if os.path.exists(filename):
                df_exist = pd.read_excel(filename, sheet_name='Jobs')
                df_new = pd.DataFrame(data)
                df_combined = pd.concat([df_exist, df_new], ignore_index=True)
            else:
                df_combined = pd.DataFrame(data)
            
            with pd.ExcelWriter(filename, engine='openpyxl') as writer:
                df_combined.to_excel(writer, sheet_name='Jobs', index=False)
                ws = writer.sheets['Jobs']
                for col in ws.columns:
                    ws.column_dimensions[col[0].column_letter].width = 20
            
            logger.info(f"✓ Appended {len(jobs)}")
        except Exception as e:
            logger.error(f"Excel error: {str(e)}")
    
    def display_summary(self, show_archived: bool = False) -> None:
        """Display summary."""
        print("\n" + "="*80)
        print("ARCHIVED JOBS" if show_archived else "ACTIVE JOBS")
        print("="*80)
        
        jobs = self.archived_jobs if show_archived else self.jobs_data
        
        if not jobs:
            print("\n⚪ None")
            return
        
        print(f"\nTotal: {len(jobs)}\n")
        
        status_counts: Dict[str, int] = {}
        for job in jobs:
            prog = job.get('progress')
            stat = prog.status if isinstance(prog, ApplicationProgress) else ''
            status_counts[stat] = status_counts.get(stat, 0) + 1
        
        print("Status:")
        for stat, cnt in status_counts.items():
            emoji = self._get_status_emoji(stat)
            print(f"  {emoji} {stat}: {cnt}")
        
        print("\n" + "-"*80)
        
        for idx, job in enumerate(jobs, 1):
            prog = job.get('progress')
            stat = prog.status if isinstance(prog, ApplicationProgress) else 'N/A'
            emoji = self._get_status_emoji(stat)
            
            missing = []
            if not job.get('job_title'):
                missing.append("Title")
            if not job.get('company'):
                missing.append("Company")
            if not job.get('location'):
                missing.append("Location")
            
            ss_cnt = len(job.get('screenshot_paths', []))
            ss_ind = f"📸({ss_cnt})" if ss_cnt > 0 else ""
            miss_txt = f" ⚠️  Missing: {', '.join(missing)}" if missing else ""
            auto_fill = " ✨" if job.get('auto_filled_from_screenshot') else ""
            
            print(f"\n{idx}. {job.get('job_title', '❌')}{miss_txt} {ss_ind}{auto_fill}")
            print(f"   Company: {job.get('company', '❌')}")
            print(f"   Location: {job.get('location', '❌')}")
            print(f"   {emoji} {stat}")
            
            if job.get('salary'):
                print(f"   Salary: {job.get('salary')}")
            
            if show_archived and job.get('archived_at'):
                print(f"   Archived: {job.get('archived_at')}")
        
        print("\n" + "="*80)
    
    def _get_status_emoji(self, status: str) -> str:
        """Get status emoji."""
        emojis = {
            'Not Applied': '⚪',
            'Applied': '🟡',
            'Interview': '🔵',
            'Offer': '🟢',
            'Rejected': '🔴'
        }
        return emojis.get(status, '❓')


def main() -> None:
    """Main program."""
    print("\n" + "="*80)
    print("╔════════════════════════════════════════════════════════════════════════════╗")
    print("║  JOB SCRAPER WITH FULL PAGE SCREENSHOTS - COMPLETE VERSION                 ║")
    print("║       💼 Complete Job Application Management System 💼                      ║")
    print("║   WITH AUTO-SAVE ON EVERY ACTION (JSON, CSV, EXCEL) ✨                     ║")
    print("╚════════════════════════════════════════════════════════════════════════════╝")
    print("="*80)
    
    scraper = JobScraper()
    
    while True:
        print("\n" + "="*80)
        print("MAIN MENU")
        print("="*80)
        print(f"\n📊 Stats: {scraper.get_active_jobs_count()} active | {scraper.get_archived_jobs_count()} archived\n")
        print("1. 📂 Load previous job data")
        print("2. 📋 Add NEW job links and scrape")
        print("3. 📊 View active jobs")
        print("4. 📦 View archived jobs")
        print("5. ✏️  Edit job information")
        print("6. 👁️  View complete job details")
        print("7. 📈 Update application progress")
        print("8. 🗂️  Manage jobs (Archive/Delete/Restore)")
        print("9. 💾 Save to new files (Manual)")
        print("10. ➕ Append to existing files (Manual)")
        print("11. 🚪 Exit")
        print("\n" + "="*80)
        
        choice = input("Enter choice (1-11): ").strip()
        
        if choice == '1':
            print("\n" + "="*80)
            print("LOAD DATA")
            print("="*80)
            print("\n1. JSON\n2. CSV\n3. Excel\n4. All")
            fmt = input("\nSelect (1-4) [4]: ").strip() or '4'
            
            if fmt == '1':
                fn = input("Filename [jobs_data.json]: ").strip() or 'jobs_data.json'
                loaded = scraper.load_from_json(fn)
                print(f"✓ Loaded {loaded}" if loaded > 0 else "❌ No data")
            elif fmt == '2':
                fn = input("Filename [jobs_data.csv]: ").strip() or 'jobs_data.csv'
                loaded = scraper.load_from_csv(fn)
                print(f"✓ Loaded {loaded}" if loaded > 0 else "❌ No data")
            elif fmt == '3':
                fn = input("Filename [jobs_data.xlsx]: ").strip() or 'jobs_data.xlsx'
                loaded = scraper.load_from_excel(fn)
                print(f"✓ Loaded {loaded}" if loaded > 0 else "❌ No data")
            else:
                total = 0
                if os.path.exists('jobs_data.json'):
                    total += scraper.load_from_json('jobs_data.json')
                if os.path.exists('jobs_data.csv'):
                    total += scraper.load_from_csv('jobs_data.csv')
                if os.path.exists('jobs_data.xlsx'):
                    total += scraper.load_from_excel('jobs_data.xlsx')
                print(f"✓ Loaded {total}" if total > 0 else "❌ No data")
        
        elif choice == '2':
            print("\n" + "="*80)
            print("ADD JOBS")
            print("="*80)
            try:
                num = int(input("\nHow many? (1-50): "))
                if 1 <= num <= 50:
                    urls: List[str] = []
                    for i in range(num):
                        print(f"\n--- Job {i+1}/{num} ---")
                        url = input("URL: ").strip()
                        if url:
                            urls.append(url)
                    
                    if urls:
                        cap = get_yes_no("\nCapture screenshots? (y/n): ")
                        full = False
                        if cap:
                            full = get_yes_no("Full page scroll? (y/n): ")
                        
                        print(f"\n🔄 Scraping {len(urls)} jobs...")
                        scraper.scrape_multiple_jobs(urls, capture_screenshots=cap, full_page=full)
                        print(f"✓ Done! Total: {scraper.get_active_jobs_count()}")
            except ValueError:
                print("❌ Invalid number")
        
        elif choice == '3':
            scraper.display_summary(show_archived=False)
        
        elif choice == '4':
            scraper.display_summary(show_archived=True)
        
        elif choice == '5':
            if scraper.get_active_jobs_count() == 0:
                print("\n❌ No jobs")
                continue
            
            print("\nActive jobs:")
            for idx, j in enumerate(scraper.jobs_data, 1):
                ss = f"📸({len(j.get('screenshot_paths', []))})" if j.get('screenshot_paths') else ""
                auto = " ✨" if j.get('auto_filled_from_screenshot') else ""
                print(f"{idx}. {j.get('job_title')} {ss}{auto}")
            
            try:
                idx = int(input(f"\nSelect (1-{scraper.get_active_jobs_count()}): ")) - 1
                if 0 <= idx < scraper.get_active_jobs_count():
                    scraper.edit_job(idx)
            except:
                print("❌ Invalid")
        
        elif choice == '6':
            if scraper.get_active_jobs_count() == 0 and scraper.get_archived_jobs_count() == 0:
                print("\n❌ No jobs")
                continue
            
            print("\n1. Active\n2. Archived")
            vc = input("Select (1-2): ").strip()
            
            if vc == '1' and scraper.get_active_jobs_count() > 0:
                for idx, j in enumerate(scraper.jobs_data, 1):
                    print(f"{idx}. {j.get('job_title')}")
                try:
                    idx = int(input(f"\nSelect (1-{scraper.get_active_jobs_count()}): ")) - 1
                    if 0 <= idx < scraper.get_active_jobs_count():
                        scraper.view_job_details(idx, is_archived=False)
                except:
                    print("❌ Invalid")
            
            elif vc == '2' and scraper.get_archived_jobs_count() > 0:
                for idx, j in enumerate(scraper.archived_jobs, 1):
                    print(f"{idx}. {j.get('job_title')}")
                try:
                    idx = int(input(f"\nSelect (1-{scraper.get_archived_jobs_count()}): ")) - 1
                    if 0 <= idx < scraper.get_archived_jobs_count():
                        scraper.view_job_details(idx, is_archived=True)
                except:
                    print("❌ Invalid")
        
        elif choice == '7':
            if scraper.get_active_jobs_count() == 0:
                print("\n❌ No jobs")
                continue
            
            for idx, j in enumerate(scraper.jobs_data, 1):
                print(f"{idx}. {j.get('job_title')}")
            
            try:
                idx = int(input(f"\nSelect (1-{scraper.get_active_jobs_count()}): ")) - 1
                if 0 <= idx < scraper.get_active_jobs_count():
                    print("\n1. Change status\n2. Add interview\n3. Add note\n4. Set follow-up")
                    uc = input("Select (1-4): ").strip()
                    
                    if uc == '1':
                        print("1. Not Applied\n2. Applied\n3. Interview\n4. Offer\n5. Rejected")
                        sc = input("Select (1-5): ").strip()
                        statuses = {'1': 'Not Applied', '2': 'Applied', '3': 'Interview', '4': 'Offer', '5': 'Rejected'}
                        if sc in statuses:
                            scraper.update_job_progress(idx, statuses[sc])
                    elif uc == '2':
                        date = input("Date (YYYY-MM-DD): ").strip()
                        scraper.add_interview_date(idx, date)
                    elif uc == '3':
                        note = input("Note: ").strip()
                        if note:
                            scraper.add_note(idx, note)
                    elif uc == '4':
                        date = input("Date (YYYY-MM-DD): ").strip()
                        scraper.set_follow_up(idx, date)
            except:
                print("❌ Invalid")
        
        elif choice == '8':
            if scraper.get_active_jobs_count() == 0 and scraper.get_archived_jobs_count() == 0:
                print("\n❌ No jobs")
                continue
            
            print(f"\nActive: {scraper.get_active_jobs_count()} | Archived: {scraper.get_archived_jobs_count()}\n")
            print("1. Archive (single/multi)\n2. Restore\n3. Delete (single/multi)\n4. Delete archived (single/multi)")
            mc = input("Select (1-4): ").strip()
            
            if mc == '1' and scraper.get_active_jobs_count() > 0:
                for idx, j in enumerate(scraper.jobs_data, 1):
                    print(f"{idx}. {j.get('job_title')}")
                try:
                    selection = input(f"\nSelect (Examples: 1 | 1,3,5 | 1-5): ").strip()
                    indices = parse_multi_selection(selection, scraper.get_active_jobs_count())
                    if indices:
                        reason = input("Reason (optional): ").strip()
                        scraper.archive_multiple_jobs(indices, reason if reason else None)
                    else:
                        print("❌ Invalid selection")
                except:
                    print("❌ Invalid")
            
            elif mc == '2' and scraper.get_archived_jobs_count() > 0:
                for idx, j in enumerate(scraper.archived_jobs, 1):
                    print(f"{idx}. {j.get('job_title')}")
                try:
                    selection = input(f"\nSelect (Examples: 1 | 1,3,5 | 1-5): ").strip()
                    indices = parse_multi_selection(selection, scraper.get_archived_jobs_count())
                    if indices:
                        for idx in sorted(indices, reverse=True):
                            scraper.unarchive_job(idx)
                    else:
                        print("❌ Invalid selection")
                except:
                    print("❌ Invalid")
            
            elif mc == '3' and scraper.get_active_jobs_count() > 0:
                for idx, j in enumerate(scraper.jobs_data, 1):
                    print(f"{idx}. {j.get('job_title')}")
                try:
                    selection = input(f"\nSelect (Examples: 1 | 1,3,5 | 1-5): ").strip()
                    indices = parse_multi_selection(selection, scraper.get_active_jobs_count())
                    if indices:
                        if get_yes_no(f"Delete {len(indices)} job(s)? (y/n): "):
                            scraper.delete_multiple_jobs(indices, is_archived=False)
                    else:
                        print("❌ Invalid selection")
                except:
                    print("❌ Invalid")
            
            elif mc == '4' and scraper.get_archived_jobs_count() > 0:
                for idx, j in enumerate(scraper.archived_jobs, 1):
                    print(f"{idx}. {j.get('job_title')}")
                try:
                    selection = input(f"\nSelect (Examples: 1 | 1,3,5 | 1-5): ").strip()
                    indices = parse_multi_selection(selection, scraper.get_archived_jobs_count())
                    if indices:
                        if get_yes_no(f"Delete {len(indices)} job(s)? (y/n): "):
                            scraper.delete_multiple_jobs(indices, is_archived=True)
                    else:
                        print("❌ Invalid selection")
                except:
                    print("❌ Invalid")
        
        elif choice == '9':
            jobs = scraper._get_all_jobs()
            if not jobs:
                print("\n❌ No data")
                continue
            
            print("\n1. JSON\n2. CSV\n3. Excel\n4. All")
            sc = input("Select (1-4): ").strip()
            
            if sc == '1' or sc == '4':
                scraper.save_to_json()
                print("✓ JSON saved!")
            if sc == '2' or sc == '4':
                scraper.save_to_csv()
                print("✓ CSV saved!")
            if sc == '3' or sc == '4':
                scraper.save_to_excel()
                print("✓ Excel saved!")
        
        elif choice == '10':
            jobs = scraper._get_all_jobs()
            if not jobs:
                print("\n❌ No data")
                continue
            
            print("\n1. JSON\n2. CSV\n3. Excel\n4. All")
            ac = input("Select (1-4): ").strip()
            
            if ac == '1' or ac == '4':
                scraper.append_to_json()
            if ac == '2' or ac == '4':
                scraper.append_to_csv()
            if ac == '3' or ac == '4':
                scraper.append_to_excel()
            
            print("\n✓ Appended!")
        
        elif choice == '11':
            print("\n" + "="*80)
            print("Thank you for using Job Scraper! 👋")
            print("="*80 + "\n")
            break
        
        else:
            print("❌ Invalid choice")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
