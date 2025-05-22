from threading import Lock
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.theme import Theme
from datetime import datetime
import uuid

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
    _lock = Lock()
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._setup()
        return cls._instance
    
    def _setup(self):
        self.verbose = False
        self.console = Console(theme=custom_theme)
        if self._progress is None:
            self._progress = Progress(
                SpinnerColumn(),
                TextColumn("[progress]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                console=self.console
            )
    
    def set_verbose(self, verbose: bool):
        self.verbose = verbose
    
    def _format_message(self, message: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        return f"[time]{timestamp}[/time] {message}"
    
    def info(self, message: str):
        if self.verbose:
            self.console.print(self._format_message(f"ℹ️ {message}"), style="info")
            
    def warning(self, message: str):
        self.console.print(self._format_message(f"⚠️  {message}"), style="warning")
        
    def error(self, message: str):
        self.console.print(self._format_message(f"❌ {message}"), style="error")
        
    def success(self, message: str):
        self.console.print(self._format_message(f"✅ {message}"), style="success")
        
    def status(self, message: str):
        self.console.print(self._format_message(f"👉 {message}"), style="progress")
    
    def start_progress(self, total: int, description: str = "Processing", worker_id=None) -> None:
        if worker_id is None:
            raise ValueError("worker_id must be provided to start_progress")
        with self._lock:
            if worker_id not in self._tasks:
                task_desc = f"[Worker {worker_id}] {description}"
                if not self._progress.live.is_started:
                    self._progress.start()

                actual_total = max(0, total)
                task_id = self._progress.add_task(task_desc, total=actual_total)
                self._tasks[worker_id] = task_id
                if actual_total == 0:
                    self._progress.update(task_id, completed=0)
                self._progress.refresh()

    def _find_task_by_id(self, task_id_to_find):
        for task in self._progress.tasks:
            if task.id == task_id_to_find:
                return task
        return None

    def update_progress(self, advance: int = 1, worker_id=None) -> None:
        if worker_id is None: return
        with self._lock:
            if worker_id in self._tasks:
                task_id = self._tasks[worker_id]
                task = self._find_task_by_id(task_id)
                if task:
                    if not task.finished: 
                        self._progress.update(task_id, advance=advance)
                    self._progress.refresh() 
                else:
                    self.warning(f"Task {task_id} for worker {worker_id} not found in rich for update. May have auto-completed/removed.")
            
    def complete_progress(self, worker_id) -> None:
        if worker_id is None: return
        with self._lock:
            if worker_id in self._tasks:
                task_id_to_complete = self._tasks[worker_id]
                task = self._find_task_by_id(task_id_to_complete)
                
                if task:
                    if not task.finished:
                        self._progress.update(task_id_to_complete, completed=task.total)
                    self._progress.refresh() 
                    self._progress.remove_task(task_id_to_complete)
                    self._progress.refresh() 
                else:
                    self.warning(f"Task {task_id_to_complete} for worker {worker_id} not found in rich during completion/removal.")
                
                if worker_id in self._tasks: 
                    del self._tasks[worker_id]

                if not self._tasks and self._progress.live.is_started:
                    self._progress.stop()
                    self._progress.refresh() 
            else:
                self.warning(f"No active progress task in _tasks for worker_id: {worker_id} to complete.")
            
    def truncate_url(self, url: str, max_length: int = 70) -> str:
        if len(url) <= max_length:
            return url
        return url[:max_length//2] + "..." + url[-max_length//2:]

logger = ImageScraperLogger()
