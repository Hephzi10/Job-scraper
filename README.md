# Job Scraper 💼

[![Python Version](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![GitHub Stars](https://img.shields.io/github/stars/Hephzi10/Job-scraper?style=social)](https://github.com/Hephzi10/Job-scraper)

A **production-ready Python application** for scraping job postings from multiple sources with advanced features like OCR auto-fill, full-page screenshots, multi-select management, and automatic database syncing.

## ✨ Features

- **🌐 Multi-Source Scraping**: LinkedIn, Indeed, and generic job portals
- **📸 Screenshot Capture**: Full-page or single screenshot with Selenium
- **🔍 OCR Text Extraction**: Auto-fill missing job info using pytesseract
- **📊 Multi-Format Export**: JSON, CSV, Excel with auto-save
- **✂️ Multi-Select Management**: Archive, delete, restore multiple jobs at once
- **📈 Application Tracking**: Status, interview dates, notes, follow-ups
- **💾 Auto-Save**: Automatically updates all databases on every action

## 🚀 Installation
Prerequisites
Python 3.8+
ChromeDriver (for Selenium screenshots)
Tesseract OCR (optional but recommended)
## 🎯 Quick Start

```bash
# Clone the repository
git clone https://github.com/Hephzi10/Job-scraper.git
cd Job-scraper

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the application
python job_scraper_complete.py
