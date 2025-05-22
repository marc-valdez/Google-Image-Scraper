#!/usr/bin/env python3
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import WebDriverException, SessionNotCreatedException
from logger import logger
import sys
import os
import urllib.request
import re
import zipfile
import stat
import json
import shutil
from sys import platform

def webdriver_executable():
    if platform == "linux" or platform == "linux2" or platform == "darwin":
        return 'chromedriver'
    return 'chromedriver.exe'

def download_lastest_chromedriver(current_chrome_version="", required_version=None, chrome_path=None):
    def get_platform_filename():
        filename = ''
        is_64bits = sys.maxsize > 2**32
    
        if platform == "linux" or platform == "linux2":
            # linux
            filename += 'linux64'
        
        elif platform == "darwin":
            # OS X
            filename += 'mac-x64'
        elif platform == "win32":
            # Windows...
            filename += 'win32'
   
        return filename
    
    # Find the latest chromedriver, download, unzip, set permissions to executable.
    
    result = False
    try:
        url = 'https://googlechromelabs.github.io/chrome-for-testing/latest-versions-per-milestone-with-downloads.json'
    
        # Download latest chromedriver.
        stream = urllib.request.urlopen(url)
        content = json.loads(stream.read().decode('utf-8'))

        # Parse the latest version.
        
        # Determine version to use
        if required_version:
            # Use explicitly required version
            downloads = content["milestones"][required_version]
        elif current_chrome_version:
            # Use current Chrome version
            match = re.search(r'\d+', current_chrome_version)
            if match:
                downloads = content["milestones"][match.group()]
            else:
                raise ValueError(f"Invalid Chrome version format: {current_chrome_version}")
        else:
            # Use latest version as fallback
            latest_milestone = max(content["milestones"].keys())
            downloads = content["milestones"][latest_milestone]
        
        for download in downloads["downloads"]["chromedriver"]:
            if (download["platform"] == get_platform_filename()):
                driver_url = download["url"]
        
        # Download the file.
        logger.info(f"Downloading chromedriver version {current_chrome_version} from {logger.truncate_url(driver_url)}")
        file_name = driver_url.split("/")[-1]
        app_path = os.getcwd()
        chromedriver_path = os.path.normpath(os.path.join(app_path, 'webdriver', webdriver_executable()))
        webdriver_dir = os.path.normpath(os.path.join(app_path, 'webdriver'))
        os.makedirs(webdriver_dir, exist_ok=True)
        file_path = os.path.normpath(os.path.join(webdriver_dir, file_name))
        urllib.request.urlretrieve(driver_url, file_path)

        # Unzip the file into folde
        
        webdriver_path = os.path.normpath(os.path.join(app_path, 'webdriver'))
        with zipfile.ZipFile(file_path, 'r') as zip_file:
            for member in zip_file.namelist():
                filename = os.path.basename(member)
                if not filename:
                    continue
                source = zip_file.open(member)
                target = open(os.path.join(webdriver_path, filename), "wb")
                with source, target:
                    shutil.copyfileobj(source, target)
            
        st = os.stat(chromedriver_path)
        os.chmod(chromedriver_path, st.st_mode | stat.S_IEXEC)
        logger.success("ChromeDriver downloaded successfully")
        # Cleanup.
        os.remove(file_path)
        result = True
    except Exception as e:
        logger.error(str(e))
        logger.warning("Failed to download ChromeDriver - will use existing version if available")
    
    return result