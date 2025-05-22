from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.theme import Theme
import sys

custom_theme = Theme({
    "info": "dim cyan",
    "warning": "yellow",
    "error": "bold red",
    "success": "bold green",
    "progress": "blue"
})

console = Console(theme=custom_theme)

class ImageScraperLogger:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._setup()
        return cls._instance
    
    def _setup(self):
        """Initialize the logger instance"""
        self.verbose = False
        self.progress = None
        self.current_task = None
        
    def set_verbose(self, verbose: bool):
        """Set verbose logging mode"""
        self.verbose = verbose
    
    def info(self, message: str):
        """Log info message - only if verbose is True"""
        if self.verbose:
            console.print(f"ℹ️ {message}", style="info")
            
    def warning(self, message: str):
        """Log warning message"""
        console.print(f"⚠️ {message}", style="warning")
        
    def error(self, message: str):
        """Log error message"""
        console.print(f"❌ {message}", style="error")
        
    def success(self, message: str):
        """Log success message"""
        console.print(f"✅ {message}", style="success")
        
    def status(self, message: str):
        """Log important status message - always shown"""
        console.print(f"👉 {message}", style="progress")
    
    def start_progress(self, total: int, description: str = "Processing") -> None:
        """Start a progress bar"""
        self.progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console
        )
        self.progress.start()
        self.current_task = self.progress.add_task(description, total=total)
    
    def update_progress(self, advance: int = 1) -> None:
        """Update the progress bar"""
        if self.progress and self.current_task is not None:
            self.progress.update(self.current_task, advance=advance)
            
    def complete_progress(self) -> None:
        """Complete and clear the progress bar"""
        if self.progress:
            self.progress.stop()
            self.progress = None
            self.current_task = None
            
    def truncate_url(self, url: str, max_length: int = 70) -> str:
        """Truncate URL for cleaner display"""
        if len(url) <= max_length:
            return url
        return url[:max_length//2] + "..." + url[-max_length//2:]

# Global logger instance
logger = ImageScraperLogger()