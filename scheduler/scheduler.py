"""
Scheduler - Unified scheduling for Crawl4AI, Git Ingester, and File Watcher
Uses APScheduler with cron triggers
"""
import os
import yaml
import time
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

# Import ingesters
from ingester.git_ingester import GitIngester
# from ingester.file_watcher import FileWatcher

WEKNORA_API = os.getenv("WEKNORA_API_URL", "http://weknora-api:8080")

def load_config(config_path: str = "config.yaml") -> dict:
    """Load scheduler configuration"""
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def crawl_web_source(source: dict):
    """Trigger web crawl task"""
    from crawler.crawler import WebCrawler
    crawler = WebCrawler()
    print(f"[{datetime.now()}] Triggering web crawl: {source['name']}")
    # In production, this would call the crawler service
    # For now, it's a placeholder for the actual implementation

def run_git_ingestion(source: dict):
    """Trigger Git repository ingestion"""
    ingester = GitIngester(WEKNORA_API)
    print(f"[{datetime.now()}] Triggering Git ingestion: {source['name']}")
    ingester.run_repo(source)

def run_file_scan():
    """Trigger local file scanning"""
    print(f"[{datetime.now()}] Running file scan...")
    # Placeholder for file watcher implementation

def main():
    config = load_config()
    scheduler = BackgroundScheduler()

    # Schedule web crawl tasks
    for source in config.get('web_sources', []):
        if not source.get('enabled', True):
            continue
        scheduler.add_job(
            crawl_web_source,
            CronTrigger.from_crontab(source.get('schedule', '0 3 * * *')),
            args=[source],
            id=f"web_{source['id']}",
            replace_existing=True
        )
        print(f"Scheduled: {source['name']} at {source.get('schedule', '0 3 * * *')}")

    # Schedule Git ingestion tasks
    for source in config.get('git_sources', []):
        if not source.get('enabled', True):
            continue
        scheduler.add_job(
            run_git_ingestion,
            CronTrigger.from_crontab(source.get('schedule', '0 5 * * *')),
            args=[source],
            id=f"git_{source['id']}",
            replace_existing=True
        )
        print(f"Scheduled: {source['name']} at {source.get('schedule', '0 5 * * *')}")

    # Schedule file scanning
    scheduler.add_job(
        run_file_scan,
        CronTrigger.from_crontab("0 */2 * * *"),  # Every 2 hours
        id="file_watcher",
        replace_existing=True
    )
    print("Scheduled: File watcher every 2 hours")

    scheduler.start()
    print(f"[{datetime.now()}] Scheduler started. Press Ctrl+C to stop.")

    try:
        # Keep running
        while True:
            time.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        print(f"[{datetime.now()}] Scheduler stopped.")

if __name__ == "__main__":
    main()
