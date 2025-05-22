import os
from src.environment.chrome_finder import ChromeFinder
from src.logging.logger import logger

class EnvironmentResolver:
    @staticmethod
    def resolve_webdriver_path(webdriver_path=None):
        default_dir = os.path.join(os.getcwd(), "webdriver")
        default_path = os.path.join(default_dir, "chromedriver.exe")

        if webdriver_path and os.path.isdir(os.path.dirname(webdriver_path)):
            return webdriver_path

        if not os.path.exists(default_dir):
            os.makedirs(default_dir, exist_ok=True)
            logger.info(f"Created webdriver directory: {default_dir}")

        logger.info(f"Using default webdriver path: {default_path}")
        return default_path

    @staticmethod
    def auto_detect_chrome():
        finder = ChromeFinder()
        path = finder.get_chrome_path()
        if path:
            logger.info(f"Auto-detected Chrome at: {path}")
        else:
            logger.warning("Could not detect Chrome path - ensure Chrome is installed")
        return path
