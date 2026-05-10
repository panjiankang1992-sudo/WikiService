"""
Crawl4AI Web Crawler - Periodic deep crawling with authentication support
Outputs Markdown files for WeKnora ingestion
"""
import os
import sys
import yaml
import asyncio
import hashlib
import json
from datetime import datetime
from pathlib import Path
import requests

# WeKnora API configuration
WEKNORA_API = os.getenv("WEKNORA_API_URL", "http://weknora-api:8080")
DEFAULT_KB_ID = os.getenv("WEKNORA_KB_ID", "kb_default")

class WebCrawler:
    """Crawl4AI-based web crawler with scheduled execution"""

    def __init__(self, config_path: str = "sources.yaml"):
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
        self.output_base = Path("/data/output")

    def _get_content_hash(self, content: str) -> str:
        """Generate SHA256 hash for deduplication"""
        return hashlib.sha256(content.encode()).hexdigest()

    def _save_markdown(self, source_id: str, url: str, content: str, metadata: dict):
        """Save crawled content as Markdown"""
        output_dir = self.output_base / source_id
        output_dir.mkdir(parents=True, exist_ok=True)

        # Generate filename from URL
        filename = url.replace("https://", "").replace("http://", "")
        filename = filename.replace("/", "_").replace("?", "_").replace("=", "_")
        filename = filename[:100] + ".md"  # Limit filename length

        filepath = output_dir / filename

        # Add frontmatter
        frontmatter = f"""---
source: {url}
crawled_at: {datetime.now().isoformat()}
content_hash: {self._get_content_hash(content)}
kb_id: {metadata.get('kb_id', DEFAULT_KB_ID)}
---

"""
        filepath.write_text(frontmatter + content, encoding='utf-8')
        return filepath

    def _push_to_weknora(self, filepath: Path, kb_id: str):
        """Push Markdown file to WeKnora"""
        api_url = f"{WEKNORA_API}/api/v1/knowledge-bases/{kb_id}/knowledge/file"

        with open(filepath, 'rb') as f:
            files = {"file": (filepath.name, f)}
            data = {"metadata": json.dumps({"source": "crawl4ai"})}

            try:
                resp = requests.post(api_url, files=files, data=data, timeout=30)
                resp.raise_for_status()
                return True
            except Exception as e:
                print(f"Failed to push {filepath} to WeKnora: {e}")
                return False

    async def crawl_source(self, source: dict) -> int:
        """
        Crawl a single source using Crawl4AI

        Note: This is a skeleton implementation.
        Full Crawl4AI integration requires async crawler setup.
        """
        from crawl4ai import AsyncWebCrawler, CrawlerConfig

        source_id = source['id']
        print(f"[{datetime.now()}] Starting crawl: {source['name']}")

        # Build Crawl4AI config
        config = CrawlerConfig(
            seed_urls=source['seed_urls'],
            max_depth=source.get('max_depth', 3),
            max_pages=source.get('max_pages', 500),
            output_format="markdown",
        )

        # Add URL filters
        if 'include_patterns' in source:
            config.include_patterns = source['include_patterns']
        if 'exclude_patterns' in source:
            config.exclude_patterns = source['exclude_patterns']

        # Add authentication if configured
        if 'auth' in source:
            config.auth = source['auth']

        crawled_count = 0

        async with AsyncWebCrawler(config) as crawler:
            results = await crawler.crawl()

            for result in results:
                if result.success and result.markdown:
                    filepath = self._save_markdown(
                        source_id,
                        result.url,
                        result.markdown,
                        {'kb_id': source.get('kb_id', DEFAULT_KB_ID)}
                    )
                    print(f"  Saved: {filepath}")
                    crawled_count += 1

                    # Push to WeKnora
                    kb_id = source.get('kb_id', DEFAULT_KB_ID)
                    self._push_to_weknora(filepath, kb_id)

        print(f"[{source['name']}] ✅ Crawled {crawled_count} pages")
        return crawled_count

    def run_all(self):
        """Run all enabled sources"""
        for source in self.config.get('sources', []):
            if not source.get('enabled', True):
                print(f"[{source['id']}] Skipped (disabled)")
                continue

            try:
                asyncio.run(self.crawl_source(source))
            except Exception as e:
                print(f"[{source['id']}] Error: {e}")


if __name__ == "__main__":
    crawler = WebCrawler()
    crawler.run_all()
