#!/usr/bin/env python3
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import WebDriverException, SessionNotCreatedException
from src.logging.logger import logger
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

def get_chrome_version(chrome_path):
    """Extract Chrome version from the binary path."""
    try:
        # Common locations for version info in Chrome binary
        if platform == "win32":
            import winreg
            try:
                key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Google\Chrome\BLBeacon")
                version, _ = winreg.QueryValueEx(key, "version")
                return version
            except WindowsError:
                pass
        
        # Fallback: Try to extract version from file properties or binary
        import subprocess
        if platform == "win32":
            cmd = f'powershell -command "&{{ (Get-Item \'{chrome_path}\').VersionInfo.FileVersion }}"'
        else:
            cmd = f"{chrome_path} --version"
        
        version = subprocess.check_output(cmd, shell=True).decode('utf-8').strip()
        match = re.search(r'(\d+\.\d+\.\d+\.\d+|\d+\.\d+\.\d+|\d+)', version)
        if match:
            return match.group(1)
    except Exception as e:
        logger.warning(f"Failed to get Chrome version: {e}")
    return None

def download_lastest_chromedriver(chrome_path=None, required_version=None):
    def get_platform_filename():
        filename = ''
        is_64bits = sys.maxsize > 2**32
    
        if platform == "linux" or platform == "linux2":
            filename += 'linux64'
        elif platform == "darwin":
            filename += 'mac-x64'
        elif platform == "win32":
            filename += 'win32'
        return filename
    
    result = False
    try:
        # Get current Chrome version if path provided and no required_version specified
        current_chrome_version = None
        if chrome_path and not required_version:
            current_chrome_version = get_chrome_version(chrome_path)
            if current_chrome_version:
                logger.info(f"Detected Chrome version: {current_chrome_version}")

        url = 'https://googlechromelabs.github.io/chrome-for-testing/latest-versions-per-milestone-with-downloads.json'
        
        # Download latest chromedriver versions data
        stream = urllib.request.urlopen(url)
        content = json.loads(stream.read().decode('utf-8'))

        # Determine version to use
        if required_version:
            # Use explicitly required version
            version_key = str(required_version)
        elif current_chrome_version:
            # Use current Chrome version
            match = re.search(r'\d+', current_chrome_version)
            if match:
                version_key = match.group()
            else:
                raise ValueError(f"Invalid Chrome version format: {current_chrome_version}")
        else:
            # Use latest version as fallback
            version_key = max(content["milestones"].keys())
        
        if version_key not in content["milestones"]:
            raise ValueError(f"No ChromeDriver available for version {version_key}")
            
        downloads = content["milestones"][version_key]
        driver_url = None
        for download in downloads["downloads"]["chromedriver"]:
            if download["platform"] == get_platform_filename():
                driver_url = download["url"]
                break
                
        if not driver_url:
            raise ValueError(f"No ChromeDriver download found for platform {get_platform_filename()}")

        # Download the file
        logger.info(f"Downloading ChromeDriver version {version_key} from {logger.truncate_url(driver_url)}")
        file_name = driver_url.split("/")[-1]
        app_path = os.getcwd()
        chromedriver_path = os.path.normpath(os.path.join(app_path, 'webdriver', webdriver_executable()))
        webdriver_dir = os.path.normpath(os.path.join(app_path, 'webdriver'))
        os.makedirs(webdriver_dir, exist_ok=True)
        file_path = os.path.normpath(os.path.join(webdriver_dir, file_name))
        urllib.request.urlretrieve(driver_url, file_path)

        # Unzip the file into folder
        with zipfile.ZipFile(file_path, 'r') as zip_file:
            for member in zip_file.namelist():
                filename = os.path.basename(member)
                if not filename:
                    continue
                source = zip_file.open(member)
                target = open(os.path.join(webdriver_dir, filename), "wb")
                with source, target:
                    shutil.copyfileobj(source, target)
            
        # Set executable permissions
        st = os.stat(chromedriver_path)
        os.chmod(chromedriver_path, st.st_mode | stat.S_IEXEC)
        logger.success("ChromeDriver downloaded successfully")
        
        # Cleanup
        os.remove(file_path)
        result = True
    except Exception as e:
        logger.error(str(e))
        logger.warning("Failed to download ChromeDriver - will use existing version if available")
    
    return result