"""
Local File Watcher - Monitor local directories for documentation changes
Uses watchdog for efficient file system event handling
"""
import os
import time
import hashlib
import json
import requests
from pathlib import Path
from datetime import datetime
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

WEKNORA_API = os.getenv("WEKNORA_API_URL", "http://weknora-api:8080")
DEFAULT_KB_ID = os.getenv("WEKNORA_KB_ID", "kb_default")

class FileChangeHandler(FileSystemEventHandler):
    """Handle file system events for documentation sync"""

    def __init__(self, kb_id: str, weknora_api: str):
        self.kb_id = kb_id
        self.weknora_api = weknora_api
        self.state_file = Path("/data/file_watcher_state.json")
        self.state = self._load_state()

    def _load_state(self) -> dict:
        """Load file state for deduplication"""
        if self.state_file.exists():
            return json.loads(self.state_file.read_text())
        return {}

    def _save_state(self):
        """Save file state"""
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.state_file.write_text(json.dumps(self.state, indent=2))

    def _get_content_hash(self, filepath: Path) -> str:
        """Generate SHA256 hash for file content"""
        try:
            return hashlib.sha256(filepath.read_bytes()).hexdigest()
        except Exception:
            return ""

    def _should_sync(self, filepath: str) -> bool:
        """Check if file needs to be synced"""
        current_hash = self._get_content_hash(Path(filepath))
        old_hash = self.state.get(filepath, {}).get('content_hash', '')
        return current_hash != old_hash and current_hash

    def _sync_to_weknora(self, filepath: Path):
        """Sync file to WeKnora"""
        api_url = f"{self.weknora_api}/api/v1/knowledge-bases/{self.kb_id}/knowledge/file"

        try:
            with open(filepath, 'rb') as f:
                files = {"file": (filepath.name, f)}
                data = {
                    "metadata": json.dumps({
                        "source": f"local:{filepath}",
                        "ingested_at": datetime.now().isoformat()
                    })
                }
                resp = requests.post(api_url, files=files, data=data, timeout=30)

                if resp.status_code == 200:
                    # Update state
                    self.state[str(filepath)] = {
                        'content_hash': self._get_content_hash(filepath),
                        'synced_at': datetime.now().isoformat()
                    }
                    self._save_state()
                    print(f"  ✅ Synced: {filepath}")
                else:
                    print(f"  ❌ Failed: {filepath} - {resp.text}")
        except Exception as e:
            print(f"  ❌ Error syncing {filepath}: {e}")

    def on_modified(self, event):
        """Handle file modification events"""
        if event.is_directory:
            return

        if str(event.src_path).endswith(('.md', '.rst', '.txt')):
            print(f"[{datetime.now()}] Modified: {event.src_path}")
            if self._should_sync(event.src_path):
                self._sync_to_weknora(Path(event.src_path))

    def on_created(self, event):
        """Handle file creation events"""
        if event.is_directory:
            return

        if str(event.src_path).endswith(('.md', '.rst', '.txt')):
            print(f"[{datetime.now()}] Created: {event.src_path}")
            self._sync_to_weknora(Path(event.src_path))

    def on_deleted(self, event):
        """Handle file deletion events"""
        if event.is_directory:
            return

        if str(event.src_path).endswith(('.md', '.rst', '.txt')):
            print(f"[{datetime.now()}] Deleted: {event.src_path}")
            # Remove from state
            if str(event.src_path) in self.state:
                del self.state[str(event.src_path)]
                self._save_state()


class FileWatcher:
    """Monitor directories for documentation changes"""

    def __init__(self, watch_dirs: list, kb_id: str = DEFAULT_KB_ID):
        self.watch_dirs = [Path(d) for d in watch_dirs]
        self.kb_id = kb_id
        self.weknora_api = WEKNORA_API

    def scan_once(self) -> int:
        """One-time scan of watched directories"""
        count = 0
        for watch_dir in self.watch_dirs:
            if not watch_dir.exists():
                print(f"Watch directory not found: {watch_dir}")
                continue

            print(f"Scanning: {watch_dir}")
            for filepath in watch_dir.rglob('*'):
                if filepath.is_file() and filepath.suffix in ['.md', '.rst', '.txt']:
                    handler = FileChangeHandler(self.kb_id, self.weknora_api)
                    if handler._should_sync(str(filepath)):
                        handler._sync_to_weknora(filepath)
                        count += 1

        return count

    def start_watching(self):
        """Start continuous file watching"""
        event_handler = FileChangeHandler(self.kb_id, self.weknora_api)
        observer = Observer()

        for watch_dir in self.watch_dirs:
            watch_dir.mkdir(parents=True, exist_ok=True)
            observer.schedule(event_handler, str(watch_dir), recursive=True)
            print(f"Watching: {watch_dir}")

        observer.start()
        print(f"[{datetime.now()}] File watcher started. Press Ctrl+C to stop.")

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            observer.stop()
            observer.join()
            print(f"[{datetime.now()}] File watcher stopped.")


if __name__ == "__main__":
    import sys

    # Default watch directories
    watch_dirs = sys.argv[1:] if len(sys.argv) > 1 else ["/data/local-docs"]
    kb_id = os.getenv("WEKNORA_KB_ID", "kb_local")

    watcher = FileWatcher(watch_dirs, kb_id)

    # One-time scan
    print("Running initial scan...")
    count = watcher.scan_once()
    print(f"Synced {count} files")

    # Start continuous watching
    watcher.start_watching()
