import os
import io
import hashlib
from typing import Tuple, Dict, Optional
from urllib.parse import urlparse
from PIL import Image, UnidentifiedImageError
from src.logging.logger import logger
import config as cfg


class FileVerificationCache:
    """Cache file verification results to avoid redundant checks"""
    def __init__(self):
        self._cache: Dict[str, bool] = {}
    
    def verify_file(self, path: str, expected_hash: str) -> bool:
        """Verify file with caching"""
        if not expected_hash or not os.path.exists(path):
            return False
        
        # Use file path + expected hash as cache key
        cache_key = f"{path}:{expected_hash}"
        
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        try:
            with open(path, 'rb') as f:
                actual_hash = hashlib.md5(f.read()).hexdigest()
            
            result = actual_hash == expected_hash
            self._cache[cache_key] = result
            return result
        except Exception as e:
            logger.debug(f"File verification failed for {path}: {e}")
            self._cache[cache_key] = False
            return False
    
    def invalidate_file(self, path: str):
        """Remove all cache entries for a file path"""
        keys_to_remove = [key for key in self._cache.keys() if key.startswith(f"{path}:")]
        for key in keys_to_remove:
            del self._cache[key]


class ImageAnalyzer:
    """Optimized image analysis with header-only processing when possible"""
    
    @staticmethod
    def get_image_info_from_headers(content: bytes) -> Optional[Tuple[str, int, int, str]]:
        """
        Try to extract image info from headers without loading full image
        Returns: (format, width, height, mode) or None if unsuccessful
        """
        try:
            # PNG header check
            if content.startswith(b'\x89PNG\r\n\x1a\n'):
                if len(content) >= 24:
                    width = int.from_bytes(content[16:20], 'big')
                    height = int.from_bytes(content[20:24], 'big')
                    return 'png', width, height, 'RGBA'
            
            # JPEG header check
            elif content.startswith(b'\xff\xd8\xff'):
                return ImageAnalyzer._parse_jpeg_headers(content)
            
            # GIF header check
            elif content.startswith(b'GIF87a') or content.startswith(b'GIF89a'):
                if len(content) >= 10:
                    width = int.from_bytes(content[6:8], 'little')
                    height = int.from_bytes(content[8:10], 'little')
                    return 'gif', width, height, 'P'
            
            # WebP header check
            elif content.startswith(b'RIFF') and b'WEBP' in content[:12]:
                return ImageAnalyzer._parse_webp_headers(content)
            
        except Exception as e:
            logger.debug(f"Header parsing failed: {e}")
        
        return None
    
    @staticmethod
    def _parse_jpeg_headers(content: bytes) -> Optional[Tuple[str, int, int, str]]:
        """Parse JPEG headers to extract dimensions"""
        try:
            pos = 2
            while pos < len(content) - 10:
                if content[pos] != 0xFF:
                    break
                
                marker = content[pos + 1]
                if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                    # SOF marker found
                    height = int.from_bytes(content[pos + 5:pos + 7], 'big')
                    width = int.from_bytes(content[pos + 7:pos + 9], 'big')
                    return 'jpeg', width, height, 'RGB'
                
                if marker in (0xD8, 0xD9, 0xDA):
                    pos += 2
                else:
                    length = int.from_bytes(content[pos + 2:pos + 4], 'big')
                    pos += 2 + length
            
        except Exception:
            pass
        
        return None
    
    @staticmethod
    def _parse_webp_headers(content: bytes) -> Optional[Tuple[str, int, int, str]]:
        """Parse WebP headers to extract dimensions"""
        try:
            if len(content) >= 30 and content[12:16] == b'VP8 ':
                # Simple WebP
                width = int.from_bytes(content[26:28], 'little') & 0x3FFF
                height = int.from_bytes(content[28:30], 'little') & 0x3FFF
                return 'webp', width, height, 'RGB'
            elif len(content) >= 21 and content[12:16] == b'VP8L':
                # Lossless WebP
                bits = int.from_bytes(content[21:25], 'little')
                width = (bits & 0x3FFF) + 1
                height = ((bits >> 14) & 0x3FFF) + 1
                return 'webp', width, height, 'RGBA'
        except Exception:
            pass
        
        return None
    
    @staticmethod
    def get_image_info_full(content: bytes, url: str, filename: str) -> Tuple[str, int, int, str]:
        """
        Get image info using PIL as fallback
        Returns: (format, width, height, mode)
        """
        try:
            with Image.open(io.BytesIO(content)) as img:
                fmt = (img.format or 'jpg').lower()
                return fmt, img.width or 0, img.height or 0, img.mode or 'unknown'
        except (UnidentifiedImageError, Exception) as e:
            logger.debug(f"PIL analysis failed for {filename}: {e}")
            # Fallback to URL extension
            fmt = os.path.splitext(urlparse(url).path)[1][1:].lower() or 'jpg'
            return fmt, 0, 0, 'unknown'
    
    @staticmethod
    def analyze_image(content: bytes, url: str, filename: str) -> Tuple[str, int, int, str]:
        """
        Analyze image with header-first approach, PIL fallback
        Returns: (format, width, height, mode)
        """
        # Try header analysis first (faster, less memory)
        header_info = ImageAnalyzer.get_image_info_from_headers(content)
        if header_info:
            fmt, width, height, mode = header_info
            logger.debug(f"Used header analysis for {filename}: {fmt} {width}x{height}")
            return fmt, width, height, mode
        
        # Fallback to full PIL analysis
        logger.debug(f"Using PIL fallback for {filename}")
        return ImageAnalyzer.get_image_info_full(content, url, filename)


class FilenameGenerator:
    """Generate consistent filenames for downloaded images"""
    
    @staticmethod
    def generate_filename(class_name: str, url_key: str, original_filename: str, 
                         image_format: str, keep_original: bool) -> str:
        """
        Generate appropriate filename based on settings
        """
        if keep_original:
            # Use original filename with sanitization
            name = os.path.splitext(original_filename)[0] or f"{cfg.sanitize_class_name(class_name)}_{url_key}"
            # Basic sanitization
            name = "".join(c for c in name if c.isalnum() or c in (' ', '-', '_')).strip()
            name = name[:100]  # Limit length
        else:
            # Use key-based naming for consistency
            key_number = int(url_key) if url_key.isdigit() else 1
            name = cfg.format_filename(class_name, key_number)
        
        return f"{name}.{image_format}"


class URLDeduplicator:
    """Remove duplicate URLs from download lists"""
    
    @staticmethod
    def deduplicate_urls(images_dict: dict) -> dict:
        """
        Remove entries with duplicate URLs, keeping the first occurrence
        Returns: cleaned images_dict
        """
        seen_urls = set()
        cleaned_dict = {}
        duplicates_removed = 0
        
        for url_key, img_data in images_dict.items():
            fetch_data = img_data.get('fetch_data', {})
            url = fetch_data.get('link')
            
            if not url:
                # Keep entries without URLs (shouldn't happen, but be safe)
                cleaned_dict[url_key] = img_data
                continue
            
            if url not in seen_urls:
                seen_urls.add(url)
                cleaned_dict[url_key] = img_data
            else:
                duplicates_removed += 1
                logger.debug(f"Removed duplicate URL: {url} (key: {url_key})")
        
        if duplicates_removed > 0:
            logger.info(f"Removed {duplicates_removed} duplicate URLs from download list")
        
        return cleaned_dict


# Global instances for reuse
_file_verification_cache = FileVerificationCache()
_image_analyzer = ImageAnalyzer()
_filename_generator = FilenameGenerator()
_url_deduplicator = URLDeduplicator()

# Convenience functions
def verify_file_cached(path: str, expected_hash: str) -> bool:
    return _file_verification_cache.verify_file(path, expected_hash)

def invalidate_file_cache(path: str):
    _file_verification_cache.invalidate_file(path)

def analyze_image_optimized(content: bytes, url: str, filename: str) -> Tuple[str, int, int, str]:
    return _image_analyzer.analyze_image(content, url, filename)

def generate_filename(class_name: str, url_key: str, original_filename: str, 
                     image_format: str, keep_original: bool) -> str:
    return _filename_generator.generate_filename(class_name, url_key, original_filename, 
                                               image_format, keep_original)

def deduplicate_urls(images_dict: dict) -> dict:
    return _url_deduplicator.deduplicate_urls(images_dict)