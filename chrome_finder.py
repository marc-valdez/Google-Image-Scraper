import os
import platform
import shutil

class ChromeFinder:
    """
    Locates installed Chrome browser binaries on the system.
    Tries to find Stable, Beta, Dev, and Canary versions in a preferred order.
    """

    def __init__(self):
        self.system = platform.system()

    def _get_possible_paths(self):
        """
        Returns a list of potential Chrome binary paths based on the OS.
        The list is ordered by preference (e.g., common paths for Stable first).
        Each item in the list can be a direct path string or a tuple 
        (executable_name_for_shutil_which, description).
        """
        paths = []
        # Common executable names to check with shutil.which
        # Order might matter if multiple are on PATH (e.g. prefer 'google-chrome-stable')
        executable_names_for_path_search = [
            'google-chrome-stable', 'google-chrome', 'chrome', 'chromium-browser', 'chromium'
        ]

        if self.system == "Windows":
            # Environment variables
            program_files = os.environ.get("ProgramFiles", "C:\\Program Files")
            program_files_x86 = os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)")
            local_app_data = os.environ.get("LOCALAPPDATA", "")

            # Paths ordered by common preference (Stable first)
            # Standard Chrome installations
            paths.extend([
                os.path.join(program_files, "Google\\Chrome\\Application\\chrome.exe"),
                os.path.join(program_files_x86, "Google\\Chrome\\Application\\chrome.exe"),
            ])
            if local_app_data:
                paths.append(os.path.join(local_app_data, "Google\\Chrome\\Application\\chrome.exe"))
            
            # Chrome Beta
            paths.extend([
                os.path.join(program_files, "Google\\Chrome Beta\\Application\\chrome.exe"),
                os.path.join(program_files_x86, "Google\\Chrome Beta\\Application\\chrome.exe"),
            ])
            if local_app_data:
                paths.append(os.path.join(local_app_data, "Google\\Chrome Beta\\Application\\chrome.exe"))

            # Chrome Dev
            paths.extend([
                os.path.join(program_files, "Google\\Chrome Dev\\Application\\chrome.exe"),
                os.path.join(program_files_x86, "Google\\Chrome Dev\\Application\\chrome.exe"),
            ])
            if local_app_data:
                paths.append(os.path.join(local_app_data, "Google\\Chrome Dev\\Application\\chrome.exe"))

            # Chrome Canary (often in LocalAppData)
            if local_app_data:
                paths.append(os.path.join(local_app_data, "Google\\Chrome SxS\\Application\\chrome.exe"))
        
        elif self.system == "Darwin": # macOS
            paths.extend([
                "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                "/Applications/Google Chrome Beta.app/Contents/MacOS/Google Chrome Beta",
                "/Applications/Google Chrome Dev.app/Contents/MacOS/Google Chrome Dev",
                "/Applications/Google Chrome Canary.app/Contents/MacOS/Google Chrome Canary",
                "/Applications/Chromium.app/Contents/MacOS/Chromium", # Generic Chromium
            ])

        elif self.system == "Linux":
            # Specific paths first, then rely on shutil.which for common names
            paths.extend([
                "/opt/google/chrome/chrome",              # Google Chrome Stable (official .deb/.rpm)
                "/opt/google/chrome-beta/chrome",         # Google Chrome Beta
                "/opt/google/chrome-unstable/chrome",     # Google Chrome Dev/Unstable
                # Common system paths (often symlinks handled by shutil.which better)
                # "/usr/bin/google-chrome-stable",
                # "/usr/bin/google-chrome",
                # "/usr/bin/chromium-browser",
                # "/usr/bin/chromium",
            ])
        
        # Add shutil.which checks for all OS at the end as a general fallback
        for exec_name in executable_names_for_path_search:
            paths.append((exec_name, f"{exec_name} (via PATH)"))
            
        return paths

    def get_chrome_path(self):
        """
        Attempts to find an installed Chrome/Chromium binary.

        Returns:
            str: The path to the first found Chrome binary, ordered by preference.
            None: If no Chrome binary is found.
        """
        possible_locations = self._get_possible_paths()

        for item in possible_locations:
            if isinstance(item, tuple): # Item for shutil.which
                exec_name, description = item
                found_path = shutil.which(exec_name)
                if found_path and os.path.isfile(found_path):
                    print(f"[CHROME_FINDER_INFO] Found Chrome via {description}: {found_path}")
                    return found_path
            elif isinstance(item, str): # Direct path
                if os.path.isfile(item):
                    print(f"[CHROME_FINDER_INFO] Found Chrome at direct path: {item}")
                    return item
        
        print("[CHROME_FINDER_WARN] No suitable Chrome/Chromium installation found in common locations or PATH.")
        return None

if __name__ == '__main__':
    # Example Usage:
    finder = ChromeFinder()
    chrome_exe_path = finder.get_chrome_path()
    if chrome_exe_path:
        print(f"Chrome executable found: {chrome_exe_path}")
    else:
        print("Chrome executable not found.")