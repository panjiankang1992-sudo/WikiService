"""
Git Ingester - Clone/pull repositories and extract documentation
References WikiServer v2 sources table design and recursive crawl state management
"""
import os
import subprocess
import hashlib
import yaml
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
import requests
import fnmatch
import git

WEKNORA_API = os.getenv("WEKNORA_API_URL", "http://weknora-api:8080")

class GitIngester:
    """Git repository documentation ingester"""

    def __init__(self, weknora_api: str = WEKNORA_API):
        self.weknora_api = weknora_api
        self.data_dir = Path("/data/repos")
        self.state_file = Path("/data/git_state.json")
        self.state = self._load_state()

    def _load_state(self) -> dict:
        """Load ingestion state for incremental updates"""
        if self.state_file.exists():
            import json
            return json.loads(self.state_file.read_text())
        return {}

    def _save_state(self):
        """Save ingestion state"""
        import json
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.state_file.write_text(json.dumps(self.state, indent=2))

    def _get_content_hash(self, filepath: Path) -> str:
        """Generate SHA256 hash for deduplication"""
        return hashlib.sha256(filepath.read_bytes()).hexdigest()

    def _clone_or_pull(self, repo_config: dict) -> Path:
        """Clone or incremental pull of repository"""
        repo_dir = Path(repo_config.get('local_path', self.data_dir / repo_config['id']))
        repo_url = repo_config['url']

        if not repo_dir.exists():
            print(f"  Cloning {repo_url} -> {repo_dir}")
            # Shallow clone for speed
            subprocess.run(
                ["git", "clone", "--depth", "1", repo_url, str(repo_dir)],
                check=True,
                capture_output=True
            )
        else:
            print(f"  Pulling {repo_dir}")
            subprocess.run(
                ["git", "-C", str(repo_dir), "pull"],
                check=True,
                capture_output=True
            )

        return repo_dir

    def _extract_docs(self, repo_dir: Path, include_patterns: List[str],
                      exclude_patterns: List[str]) -> List[dict]:
        """Extract matching documentation files"""
        docs = []

        for root, dirs, files in os.walk(repo_dir):
            # Exclude directories
            dirs[:] = [d for d in dirs if not any(
                fnmatch.fnmatch(d, pat) for pat in exclude_patterns
            )]

            for f in files:
                filepath = Path(root) / f
                rel_path = filepath.relative_to(repo_dir)

                # Include pattern filtering
                if not any(fnmatch.fnmatch(str(rel_path), pat)
                          for pat in include_patterns):
                    continue

                # Deduplication by content hash
                content_hash = self._get_content_hash(filepath)

                docs.append({
                    'path': str(filepath),
                    'rel_path': str(rel_path),
                    'content_hash': content_hash,
                    'source': f"git://{repo_dir.name}/{rel_path}",
                    'size': filepath.stat().st_size
                })

        return docs

    def _should_ingest(self, doc: dict, repo_id: str) -> bool:
        """Check if document needs ingestion (incremental update)"""
        key = f"{repo_id}:{doc['rel_path']}"
        old_hash = self.state.get(key, {}).get('content_hash')
        return old_hash != doc['content_hash']

    def _push_to_weknora(self, doc: dict, kb_id: str) -> bool:
        """Push document to WeKnora knowledge base"""
        api_url = f"{self.weknora_api}/api/v1/knowledge-bases/{kb_id}/knowledge/file"

        try:
            with open(doc['path'], 'rb') as f:
                files = {"file": (doc['rel_path'], f)}
                data = {
                    "metadata": str({
                        "source": doc['source'],
                        "ingested_at": datetime.now().isoformat()
                    })
                }
                resp = requests.post(api_url, files=files, data=data, timeout=60)
                resp.raise_for_status()
            return True
        except Exception as e:
            print(f"    Failed to push {doc['rel_path']}: {e}")
            return False

    def run_repo(self, repo_config: dict) -> int:
        """
        Run ingestion for a single repository

        Args:
            repo_config: Repository configuration dict

        Returns:
            Number of documents ingested
        """
        repo_id = repo_config['id']
        kb_id = repo_config.get('kb_id', 'kb_default')

        print(f"[{datetime.now()}] Processing: {repo_config['name']}")

        try:
            # Clone or pull
            repo_dir = self._clone_or_pull(repo_config)

            # Extract documents
            docs = self._extract_docs(
                repo_dir,
                repo_config.get('include_patterns', ['*.md', '*.rst', '*.txt']),
                repo_config.get('exclude_patterns', ['.git', 'node_modules', '__pycache__'])
            )

            # Ingest new/changed documents
            ingested = 0
            for doc in docs:
                if self._should_ingest(doc, repo_id):
                    if self._push_to_weknora(doc, kb_id):
                        ingested += 1
                        # Update state
                        self.state[f"{repo_id}:{doc['rel_path']}"] = {
                            'content_hash': doc['content_hash'],
                            'ingested_at': datetime.now().isoformat()
                        }

            # Save state
            self._save_state()

            print(f"[{repo_config['name']}] ✅ Ingested {ingested}/{len(docs)} docs")
            return ingested

        except Exception as e:
            print(f"[{repo_config['name']}] ❌ Error: {e}")
            return 0

    def run_all(self, config_path: str = "config.yaml") -> dict:
        """Run ingestion for all configured repositories"""
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        results = {}
        for source in config.get('git_sources', []):
            if not source.get('enabled', True):
                continue
            results[source['id']] = self.run_repo(source)

        return results


if __name__ == "__main__":
    ingester = GitIngester()
    ingester.run_all()
