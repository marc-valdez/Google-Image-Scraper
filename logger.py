from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.theme import Theme
import sys
from datetime import datetime

custom_theme = Theme({
    "info": "dim cyan",
    "warning": "yellow",
    "error": "bold red",
    "success": "bold green",
    "progress": "blue",
    "time": "cyan"
})

class ImageScraperLogger:
    _instance = None
    _progress = None
    _tasks = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._setup()
        return cls._instance
    
    def _setup(self):
        """Initialize the logger instance"""
        self.verbose = False
        self.console = Console(theme=custom_theme)
        # Initialize shared progress
        if self._progress is None:
            self._progress = Progress(
                SpinnerColumn(),
                TextColumn("[progress]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                console=self.console
            )
        
    def set_verbose(self, verbose: bool):
        """Set verbose logging mode"""
        self.verbose = verbose
    
    def _format_message(self, message: str):
        """Format message with timestamp"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        return f"[time]{timestamp}[/time] {message}"
    
    def info(self, message: str):
        """Log info message - only if verbose is True"""
        if self.verbose:
            self.console.print(self._format_message(f"ℹ️ {message}"), style="info")
            
    def warning(self, message: str):
        """Log warning message"""
        self.console.print(self._format_message(f"⚠️ {message}"), style="warning")
        
    def error(self, message: str):
        """Log error message"""
        self.console.print(self._format_message(f"❌ {message}"), style="error")
        
    def success(self, message: str):
        """Log success message"""
        self.console.print(self._format_message(f"✅ {message}"), style="success")
        
    def status(self, message: str):
        """Log important status message - always shown"""
        self.console.print(self._format_message(f"👉 {message}"), style="progress")
    
    def start_progress(self, total: int, description: str = "Processing", worker_id=None) -> None:
        """Start a progress bar for a worker"""
        if worker_id not in self._tasks:
            task_desc = f"[Worker {worker_id}] {description}" if worker_id else description
            if not self._progress.live.is_started:
                self._progress.start()
            self._tasks[worker_id] = self._progress.add_task(task_desc, total=total)
    
    def update_progress(self, advance: int = 1, worker_id=None) -> None:
        """Update the progress bar for a worker"""
        if worker_id in self._tasks:
            self._progress.update(self._tasks[worker_id], advance=advance)
            
    def complete_progress(self, worker_id=None) -> None:
        """Complete a worker's progress bar"""
        if worker_id in self._tasks:
            self._progress.remove_task(self._tasks[worker_id])
            del self._tasks[worker_id]
            if not self._tasks:  # If no more tasks, stop progress display
                self._progress.stop()
            
    def truncate_url(self, url: str, max_length: int = 70) -> str:
        """Truncate URL for cleaner display"""
        if len(url) <= max_length:
            return url
        return url[:max_length//2] + "..." + url[-max_length//2:]

# Global logger instance
logger = ImageScraperLogger()