import threading
import time
from typing import Optional, List
from src.logging.logger import logger
from src.environment.webdriver import WebDriverManager

class BrowserPool:
    """Manages a pool of browser instances with proper allocation tracking."""
    
    def __init__(self, pool_size: int):
        self.pool_size = pool_size
        self.lock = threading.Lock()
        self.browsers = []
        self.busy_browsers = set()
        self.initialization_time = time.time()
        
        # Initialize the browser pool
        logger.info(f"Initializing browser pool with {pool_size} instances...")
        for i in range(pool_size):
            try:
                manager = WebDriverManager()
                browser_info = {
                    'id': i + 1,
                    'manager': manager,
                    'driver': manager.driver,
                    'created_at': time.time()
                }
                self.browsers.append(browser_info)
                logger.info(f"Browser {i + 1}/{pool_size} initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize browser {i + 1}: {e}")
        
        if not self.browsers:
            raise RuntimeError("Failed to initialize any browser instances")
        
        logger.success(f"Browser pool initialized with {len(self.browsers)} instances")
    
    def acquire_browser(self, worker_id: int, timeout: float = 30.0) -> Optional[dict]:
        """
        Acquire an available browser instance for a worker.
        
        Args:
            worker_id: The ID of the worker requesting the browser
            timeout: Maximum time to wait for an available browser
            
        Returns:
            Browser info dict if successful, None if timeout
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            with self.lock:
                # Find the first available browser
                for browser in self.browsers:
                    browser_id = browser['id']
                    if browser_id not in self.busy_browsers:
                        self.busy_browsers.add(browser_id)
                        logger.info(f"[Worker {worker_id}] Acquired browser {browser_id}")
                        return browser
            
            # If no browser available, wait a bit and try again
            time.sleep(0.1)
        
        logger.warning(f"[Worker {worker_id}] Timeout waiting for available browser after {timeout}s")
        return None
    
    def release_browser(self, browser_info: dict, worker_id: int):
        """
        Release a browser instance back to the pool.
        
        Args:
            browser_info: The browser info dict returned by acquire_browser
            worker_id: The ID of the worker releasing the browser
        """
        if not browser_info:
            return
            
        browser_id = browser_info['id']
        with self.lock:
            if browser_id in self.busy_browsers:
                self.busy_browsers.remove(browser_id)
                logger.info(f"[Worker {worker_id}] Released browser {browser_id}")
            else:
                logger.warning(f"[Worker {worker_id}] Attempted to release browser {browser_id} that wasn't marked as busy")
    
    def get_pool_status(self) -> dict:
        """Get current status of the browser pool."""
        with self.lock:
            total_browsers = len(self.browsers)
            busy_count = len(self.busy_browsers)
            available_count = total_browsers - busy_count
            
            return {
                'total': total_browsers,
                'busy': busy_count,
                'available': available_count,
                'busy_browser_ids': sorted(list(self.busy_browsers))
            }
    
    def close_all(self):
        """Close all browser instances in the pool."""
        logger.info("Closing all browsers in the pool...")
        
        with self.lock:
            for browser in self.browsers:
                try:
                    browser['manager'].close_driver()
                    logger.info(f"Browser {browser['id']} closed successfully")
                except Exception as e:
                    logger.error(f"Error closing browser {browser['id']}: {e}")
            
            self.browsers.clear()
            self.busy_browsers.clear()
        
        logger.success("All browsers in the pool have been closed")
    
    def wait_for_all_released(self, timeout: float = 30.0) -> bool:
        """
        Wait for all browsers to be released.
        
        Args:
            timeout: Maximum time to wait
            
        Returns:
            True if all browsers were released, False if timeout
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            status = self.get_pool_status()
            if status['busy'] == 0:
                logger.info("All browsers have been released")
                return True
            
            logger.info(f"Waiting for {status['busy']} busy browsers to be released...")
            time.sleep(1.0)
        
        status = self.get_pool_status()
        logger.warning(f"Timeout waiting for browsers to be released. Still busy: {status['busy_browser_ids']}")
        return False