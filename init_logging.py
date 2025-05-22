import os
import sys
from absl import flags
from absl import app
from absl import logging as absl_logging
import logging

# Initialize absl flags before anything else
flags.FLAGS.mark_as_parsed()

def configure_logging():
    """Configure logging for the entire application"""
    
    # Initialize absl logging first (must be done before any other imports that might use it)
    absl_logging.use_absl_handler()
    absl_logging.set_verbosity(absl_logging.ERROR)
    absl_logging.get_absl_handler().setFormatter(logging.Formatter(''))
    
    # Suppress other logging
    selenium_logger = logging.getLogger('selenium')
    selenium_logger.setLevel(logging.WARNING)
    
    urllib3_logger = logging.getLogger('urllib3')
    urllib3_logger.setLevel(logging.WARNING)
    
    # Chrome-specific environment variables
    os.environ['WDM_LOG_LEVEL'] = '0'
    os.environ['WDM_PRINT_FIRST_LINE'] = 'False'
    os.environ['CHROMIUM_LOG_LEVEL'] = '3'

# Initialize logging immediately on module import
configure_logging()