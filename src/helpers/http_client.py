import time
import random
import hashlib
from urllib.parse import urlparse
from typing import Tuple, Optional, Set
import requests
import certifi
import urllib3
from urllib3 import Retry
from requests.adapters import HTTPAdapter
from requests.exceptions import SSLError, RequestException, HTTPError
from src.logging.logger import logger
import config as cfg


class SmartRateLimiter:
    def __init__(self):
        self.min_interval = cfg.REQUEST_INTERVAL
        self.last_completion = 0
    
    def wait(self):
        """Ensure minimum gap between request completions"""
        elapsed = time.time() - self.last_completion
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
    
    def mark_completion(self):
        """Mark when a request completed"""
        self.last_completion = time.time()


class SSLDomainManager:
    def __init__(self):
        self._problematic_domains: Set[str] = set()
        self._skip_ssl_domains = getattr(cfg, 'SKIP_SSL_PROBLEMATIC_DOMAINS', [])
    
    def is_ssl_problematic(self, domain: str) -> bool:
        """Check if domain has known SSL issues"""
        domain_lower = domain.lower()
        return (domain_lower in self._problematic_domains or 
                any(skip_domain in domain_lower for skip_domain in self._skip_ssl_domains))
    
    def mark_ssl_problematic(self, domain: str):
        """Mark domain as having SSL issues"""
        self._problematic_domains.add(domain.lower())
        logger.debug(f"Marked {domain} as SSL-problematic")


class ErrorClassifier:
    PERMANENT_STATUS_CODES = {400, 401, 403, 404, 410, 451}
    RETRYABLE_STATUS_CODES = {408, 429, 500, 502, 503, 504}
    
    @staticmethod
    def is_retryable_error(exception) -> bool:
        """Determine if an error is worth retrying"""
        if isinstance(exception, HTTPError):
            return exception.response.status_code in ErrorClassifier.RETRYABLE_STATUS_CODES
        
        if isinstance(exception, SSLError):
            error_str = str(exception).lower()
            return any(term in error_str for term in ['hostname mismatch', 'certificate is not valid', 'certificate verify failed'])
        
        if isinstance(exception, RequestException):
            error_str = str(exception).lower()
            return any(term in error_str for term in ['timeout', 'timed out', 'connection', 'network'])
        
        return False


class OptimizedHTTPClient:
    def __init__(self):
        self.rate_limiter = SmartRateLimiter()
        self.ssl_manager = SSLDomainManager()
        self.error_classifier = ErrorClassifier()
        self.session = self._create_session()
    
    def _create_session(self) -> requests.Session:
        session = requests.Session()
        retries = Retry(
            total=cfg.MAX_RETRIES,
            backoff_factor=cfg.RETRY_BACKOFF,
            status_forcelist=list(ErrorClassifier.RETRYABLE_STATUS_CODES),
            allowed_methods=["GET"]
        )
        adapter = HTTPAdapter(max_retries=retries, pool_connections=10, pool_maxsize=50)
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        session.verify = certifi.where()
        return session
    
    def _get_headers(self, url: str) -> dict:
        ua = cfg.get_random_user_agent() if cfg.ROTATE_USER_AGENT else "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        return {
            "User-Agent": ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": url,
            "Connection": "keep-alive",
        }
    
    def fetch_content(self, url: str) -> Tuple[Optional[bytes], Optional[str]]:
        """
        Fetch content from URL with optimized retry logic
        Returns: (content, error_message)
        """
        # Early validation
        parsed_url = urlparse(url)
        if not parsed_url.scheme or not parsed_url.netloc:
            return None, f"Invalid URL format: {url}"
        
        domain = parsed_url.netloc
        
        # Skip known SSL-problematic domains
        if self.ssl_manager.is_ssl_problematic(domain):
            return None, f"Skipping SSL-problematic domain: {domain}"
        
        # Rate limiting
        self.rate_limiter.wait()
        
        max_ua_attempts = 5 if cfg.ROTATE_USER_AGENT else 1
        
        for ua_attempt in range(max_ua_attempts):
            headers = self._get_headers(url)
            
            # Try with SSL verification first, then without for SSL issues
            ssl_attempts = [True, False] if not self.ssl_manager.is_ssl_problematic(domain) else [False]
            
            for ssl_verify in ssl_attempts:
                original_verify = self.session.verify
                
                try:
                    # Add jitter to avoid thundering herd
                    time.sleep(random.uniform(0, cfg.REQUEST_INTERVAL))
                    
                    if not ssl_verify:
                        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
                        self.session.verify = False
                        logger.debug(f"Trying {domain} with SSL verification disabled")
                    
                    response = self.session.get(url, headers=headers, timeout=cfg.CONNECTION_TIMEOUT)
                    response.raise_for_status()
                    
                    # Success - restore settings and return
                    self._restore_ssl_settings(original_verify, ssl_verify)
                    self.rate_limiter.mark_completion()
                    return response.content, None
                
                except SSLError as e:
                    self._restore_ssl_settings(original_verify, ssl_verify)
                    
                    if ssl_verify:  # Mark domain as problematic and try without SSL
                        self.ssl_manager.mark_ssl_problematic(domain)
                        logger.warning(f"SSL issue for {domain}, trying without SSL verification")
                        continue
                    else:
                        self.rate_limiter.mark_completion()
                        return None, f"SSL Error: {str(e)}"
                
                except HTTPError as e:
                    self._restore_ssl_settings(original_verify, ssl_verify)
                    
                    if e.response.status_code == 403 and ua_attempt + 1 < max_ua_attempts:
                        logger.debug(f"403 Forbidden, rotating user agent (attempt {ua_attempt + 1})")
                        time.sleep(getattr(cfg, 'RETRY_BACKOFF_FOR_UA_ROTATE', 2.0))
                        break  # Try next user agent
                    
                    self.rate_limiter.mark_completion()
                    return None, f"HTTP {e.response.status_code} error"
                
                except RequestException as e:
                    self._restore_ssl_settings(original_verify, ssl_verify)
                    
                    if self.error_classifier.is_retryable_error(e) and ssl_verify:
                        logger.debug(f"Retryable error for {domain}, trying without SSL")
                        continue
                    
                    self.rate_limiter.mark_completion()
                    return None, f"Request Error: {str(e)}"
                
                break  # Success with current SSL setting
        
        self.rate_limiter.mark_completion()
        return None, f"All attempts failed for {url}"
    
    def _restore_ssl_settings(self, original_verify: bool, ssl_verify: bool):
        """Restore SSL verification settings and warnings"""
        self.session.verify = original_verify
        if not ssl_verify:
            urllib3.warnings.resetwarnings()