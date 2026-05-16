"""
WikiService Knowledge Base - Enhanced Version
Features: URL crawling, GitHub ingestion, File directory scan, Document upload, Knowledge graph
"""

import os
import sys
import json
import uuid
import re
import hashlib
import logging
from datetime import datetime
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS

# 端口配置（23100-23109）
PORT = int(os.getenv("PORT", 23100))
assert 23100 <= PORT <= 23109, f"PORT must be between 23100 and 23109, got {PORT}"

# 日志目录
LOG_DIR = os.getenv("LOG_DIR", "/opt/yuyutian/logs/WikiService")
os.makedirs(LOG_DIR, exist_ok=True)

# 配置日志：同时输出到 stderr 和文件
log_file = os.path.join(LOG_DIR, f"wikiservice_{PORT}.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(log_file, encoding="utf-8"),
        logging.StreamHandler(sys.stderr),
    ],
)
logger = logging.getLogger(__name__)

print(f"Starting WikiService Knowledge Base...", file=sys.stderr)
print(f"Log file: {log_file}", file=sys.stderr)

app = Flask(__name__, template_folder='templates')
CORS(app)

# Environment variables (all required)
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", os.getenv("deepseek_api_key", ""))
if not DEEPSEEK_API_KEY:
    print("ERROR: DEEPSEEK_API_KEY environment variable is required", file=sys.stderr)
    print("Set it via: export DEEPSEEK_API_KEY=your_api_key", file=sys.stderr)
    sys.exit(1)

DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
MODEL_NAME = os.getenv("MODEL_NAME", "deepseek-chat")
STORAGE_PATH = os.getenv("STORAGE_PATH", "/opt/yuyutian/WikiService/data")

print(f"STORAGE_PATH: {STORAGE_PATH}", file=sys.stderr)

# Ensure storage directory exists
os.makedirs(STORAGE_PATH, exist_ok=True)
os.makedirs(os.path.join(STORAGE_PATH, "sources"), exist_ok=True)


def _save_embedding(chunk_id: str, text: str):
    """后台计算并保存单个 chunk 的 embedding"""
    emb_file = os.path.join(STORAGE_PATH, "embeddings.json")
    cached = {}
    if os.path.exists(emb_file):
        try:
            with open(emb_file, 'r', encoding='utf-8') as f:
                cached = json.load(f)
        except Exception:
            cached = {}
    try:
        emb = get_embedding(text)
        h = hashlib.md5(text.encode('utf-8', errors='replace')).hexdigest()[:12]
        cached[chunk_id] = {"vec": emb, "_hash": h}
        with open(emb_file, 'w', encoding='utf-8') as f:
            json.dump(cached, f, ensure_ascii=False)
    except Exception as e:
        logger.warning(f"embedding 保存失败 {chunk_id}: {e}")


def save_chunk(text, source, metadata=None):
    """Save a text chunk to storage"""
    chunks_file = os.path.join(STORAGE_PATH, "text_chunks.json")
    chunks = []
    try:
        if os.path.exists(chunks_file):
            with open(chunks_file, 'r', encoding='utf-8') as f:
                chunks = json.load(f)
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        print(f"Warning: corrupted chunks file, resetting: {e}", file=sys.stderr)
        chunks = []

    # Ensure text is valid UTF-8
    if isinstance(text, bytes):
        text = text.decode('utf-8', errors='replace')
    elif not isinstance(text, str):
        text = str(text)

    # Check for duplicate by content hash
    content_hash = hashlib.md5(text.encode('utf-8', errors='replace')).hexdigest()
    for chunk in chunks:
        if chunk.get('content_hash') == content_hash:
            return chunk['id'], "duplicate"

    chunk_id = f"chunk-{len(chunks)}-{content_hash[:8]}"
    chunks.append({
        "id": chunk_id,
        "text": text,
        "source": source,
        "content_hash": content_hash,
        "metadata": metadata or {},
        "created_at": datetime.now().isoformat()
    })

    with open(chunks_file, 'w', encoding='utf-8') as f:
        json.dump(chunks, f, ensure_ascii=False, indent=2)

    # 异步计算 embedding（在后台线程，不阻塞响应）
    import threading
    t = threading.Thread(target=_save_embedding, args=(chunk_id, text))
    t.daemon = True
    t.start()

    return chunk_id, "added"


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/health')
def health():
    return jsonify({
        "status": "ok",
        "storage_path": STORAGE_PATH,
        "message": "WikiService Knowledge Base is running"
    })


@app.route('/api/ingest', methods=['POST'])
def ingest():
    """Add text content to knowledge base"""
    data = request.json
    text = data.get('text', '')
    source = data.get('source', 'manual')
    metadata = data.get('metadata', {})

    if not text:
        return jsonify({"error": "No text provided"}), 400

    try:
        chunk_id, status = save_chunk(text, source, metadata)
        return jsonify({
            "success": True,
            "chunk_id": chunk_id,
            "status": status,
            "source": source
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route('/api/ingest/url', methods=['POST'])
def ingest_url():
    """Crawl content from URL — supports raw .md, MiniMax docs, and standard HTML"""
    data = request.json
    url = data.get('url', '')

    if not url:
        return jsonify({"error": "No URL provided"}), 400

    try:
        import httpx
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

        content = None
        title_text = url
        raw_source = "html"

        # --- Strategy 1: Raw .md files (MiniMax docs and similar) ---
        if url.endswith('.md'):
            with httpx.Client(timeout=30.0, headers=headers, follow_redirects=True) as client:
                response = client.get(url)
                response.raise_for_status()
                try:
                    content = response.text
                except UnicodeDecodeError:
                    content = response.content.decode('utf-8', errors='replace')
            raw_source = "md"

        # --- Strategy 2: MiniMax platform docs (convert .md path automatically) ---
        elif 'platform.minimaxi.com/docs/' in url or 'platform.minimaxi.com/' in url:
            # Try .md path first for MiniMax docs
            md_url = url
            if not md_url.endswith('.md'):
                # Convert page URL to raw MDX: /docs/guides/xxx → /docs/guides/xxx.md
                md_url = url.rstrip('/') + '.md'

            try:
                with httpx.Client(timeout=30.0, headers=headers, follow_redirects=True) as client:
                    md_response = client.get(md_url)
                    if md_response.status_code == 200:
                        content = md_response.text
                        raw_source = "md"
                        url = md_url  # update to md path
            except httpx.HTTPError:
                pass

            # Fallback: try llms.txt (documentation index) for MiniMax
            if not content:
                try:
                    with httpx.Client(timeout=30.0, headers=headers) as client:
                        idx_resp = client.get('https://platform.minimaxi.com/docs/llms.txt')
                        if idx_resp.status_code == 200:
                            content = idx_resp.text
                            title_text = 'MiniMax 开放平台文档中心 - 文档索引'
                            raw_source = "md-index"
                            url = 'https://platform.minimaxi.com/docs/llms.txt'
                except httpx.HTTPError:
                    pass

        # --- Strategy 3: Standard HTML page ---
        if content is None:
            with httpx.Client(timeout=30.0, headers=headers, follow_redirects=True) as client:
                response = client.get(url)
                response.raise_for_status()
                try:
                    html = response.text
                except UnicodeDecodeError:
                    html = response.content.decode('utf-8', errors='replace')

            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, 'html.parser')

            # Remove scripts and styles
            for tag in soup(["script", "style", "nav", "footer", "header"]):
                tag.decompose()

            # Get title
            title_tag = soup.find('title')
            title_text = title_tag.get_text().strip() if title_tag else url

            # Get main content
            main_content = soup.find('main') or soup.find('article') or soup.find('body')
            content = main_content.get_text(separator="\n", strip=True) if main_content else ""

            # Clean up whitespace
            content = re.sub(r'\n{3,}', '\n\n', content)
            content = content.strip()

        if not content or len(content.strip()) < 50:
            return jsonify({
                "error": "页面内容过少，可能是 JS 渲染页面（如 Next.js SPA）。建议使用 .md 路径或 GitHub 地址。"
            }), 400

        # Strip MDX frontmatter/comments if present
        content = re.sub(r'^> .*\n', '', content, flags=re.MULTILINE)  # Remove blockquotes like "Documentation Index"
        content = re.sub(r'<AgentInstructions>.*?</AgentInstructions>', '', content, flags=re.DOTALL)
        content = re.sub(r'```json[\s\S]*?```', '', content)  # Remove code blocks
        content = content.strip()

        # Extract title from markdown heading if available
        title_match = re.search(r'^# (.+)$', content, re.MULTILINE)
        if title_match:
            title_text = title_match.group(1).strip()

        # Save to knowledge base
        metadata = {
            "url": url,
            "title": title_text,
            "raw_source": raw_source,
            "crawled_at": datetime.now().isoformat(),
            "type": "web"
        }
        chunk_id, status = save_chunk(content, f"url:{url}", metadata)

        return jsonify({
            "success": True,
            "chunk_id": chunk_id,
            "title": title_text,
            "url": url,
            "content_length": len(content),
            "raw_source": raw_source,
            "status": status
        })

    except ImportError:
        return jsonify({"error": "BeautifulSoup4 not installed. Run: pip install beautifulsoup4 lxml"}), 500
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route('/api/ingest/minimax', methods=['POST'])
def ingest_minimax():
    """Batch ingest all MiniMax platform documentation"""
    data = request.json or {}
    max_pages = data.get('max_pages', 20)

    try:
        import httpx
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

        # 1. Get full documentation index
        with httpx.Client(timeout=30.0, headers=headers) as client:
            resp = client.get('https://platform.minimaxi.com/docs/llms.txt')
            resp.raise_for_status()
            index_content = resp.text

        # 2. Parse all doc links from index
        doc_links = re.findall(r'\((https://platform\.minimaxi\.com(/docs/[^\)]+\.md))\)', index_content)
        results = []

        for doc_url, doc_path in doc_links[:max_pages]:
            try:
                with httpx.Client(timeout=30.0, headers=headers) as client:
                    r = client.get(doc_url)
                    if r.status_code != 200:
                        continue
                    content = r.text
                    # Extract title from first heading
                    title = re.search(r'^# (.+)$', content, re.MULTILINE)
                    title_text = title.group(1).strip() if title else doc_path

                    # Clean MDX artifacts
                    content = re.sub(r'^> .*\n', '', content, flags=re.MULTILINE)
                    content = re.sub(r'<AgentInstructions>.*?</AgentInstructions>', '', content, flags=re.DOTALL)
                    content = re.sub(r'```json[\s\S]*?```', '', content)
                    content = content.strip()

                    if len(content) < 100:
                        continue

                    metadata = {
                        "url": doc_url,
                        "title": title_text,
                        "source": "minimax",
                        "type": "doc",
                        "crawled_at": datetime.now().isoformat()
                    }
                    chunk_id, status = save_chunk(content, f"minimax:{doc_path}", metadata)
                    results.append({
                        "url": doc_url,
                        "title": title_text,
                        "chunk_id": chunk_id,
                        "status": status,
                        "chars": len(content)
                    })
            except Exception as e:
                print(f"Error fetching {doc_url}: {e}", file=sys.stderr)
                continue

        return jsonify({
            "success": True,
            "total_indexed": len(doc_links),
            "pages_ingested": len(results),
            "pages": results
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route('/api/ingest/github', methods=['POST'])
def ingest_github():
    """Ingest GitHub repository documentation"""
    data = request.json
    repo_url = data.get('url', '')

    if not repo_url:
        return jsonify({"error": "No GitHub URL provided"}), 400

    try:
        # Parse GitHub URL - handle .git suffix and trailing slashes
        match = re.match(r'https?://github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$', repo_url)
        if not match:
            match = re.match(r'([^/]+)/([^/]+?)(?:\.git)?$', repo_url)

        if not match:
            return jsonify({"error": "Invalid GitHub URL format. Example: https://github.com/username/repo"}), 400

        owner, repo = match.groups()
        repo = repo.rstrip('/')

        import httpx
        github_token = os.getenv("GITHUB_TOKEN", "")
        headers = {
            "User-Agent": "WikiService-KnowledgeBase",
            "Accept": "application/vnd.github.v3+json"
        }
        if github_token:
            headers["Authorization"] = f"token {github_token}"

        results = []
        file_urls = []

        # First get the default branch name
        default_branch = "main"  # default fallback
        try:
            with httpx.Client(timeout=30.0, headers=headers, follow_redirects=True) as client:
                repo_info = client.get(f"https://api.github.com/repos/{owner}/{repo}")
                if repo_info.status_code == 200:
                    default_branch = repo_info.json().get('default_branch', 'main')
                    logger.info(f"GitHub repo {owner}/{repo} default branch: {default_branch}")
        except Exception as e:
            logger.warning(f"Failed to get repo info for {owner}/{repo}: {e}")

        # Use tree API to get all files recursively
        tree_url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{default_branch}?recursive=1"
        logger.info(f"Fetching GitHub tree: {tree_url}")

        try:
            with httpx.Client(timeout=60.0, headers=headers, follow_redirects=True) as client:
                response = client.get(tree_url)
                logger.info(f"Tree API response: {response.status_code}")
                if response.status_code == 200:
                    tree_data = response.json()
                    logger.info(f"Tree items: {len(tree_data.get('tree', []))}")
                    for item in tree_data.get('tree', []):
                        if item['type'] == 'blob':
                            path = item['path']
                            ext = path.split('.')[-1].lower() if '.' in path else ''
                            if ext in ['md', 'txt', 'rst', 'html', 'json', 'yaml', 'yml', 'toml', 'py', 'js', 'ts', 'go', 'java', 'cpp', 'c', 'h']:
                                # Construct raw URL
                                raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{default_branch}/{path}"
                                file_urls.append({
                                    "path": path,
                                    "name": path.split('/')[-1],
                                    "url": f"https://github.com/{owner}/{repo}/blob/{default_branch}/{path}",
                                    "download_url": raw_url
                                })
        except Exception as e:
            print(f"Tree API error: {e}", file=sys.stderr)

        # If tree API failed, try contents API
        if not file_urls:
            def fetch_contents(path=""):
                nonlocal file_urls
                api_url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
                try:
                    with httpx.Client(timeout=30.0, headers=headers, follow_redirects=True) as client:
                        response = client.get(api_url)
                        if response.status_code == 200:
                            items = response.json()
                            if isinstance(items, dict):
                                items = [items]
                            for item in items:
                                if item['type'] == 'file':
                                    ext = item['name'].split('.')[-1].lower()
                                    if ext in ['md', 'txt', 'rst', 'html', 'json', 'yaml', 'yml', 'toml', 'py', 'js', 'ts', 'go', 'java', 'cpp', 'c', 'h']:
                                        file_urls.append({
                                            "path": item['path'],
                                            "name": item['name'],
                                            "url": item.get('html_url', ''),
                                            "download_url": item.get('download_url')
                                        })
                                elif item['type'] == 'dir' and item['name'] not in ['node_modules', '.git', 'vendor', 'dist', 'build', '__pycache__']:
                                    fetch_contents(item['path'])
                except Exception as e:
                    print(f"Error fetching {path}: {e}", file=sys.stderr)
            fetch_contents()

        # Download files: raw URL first (high rate limit), then Contents API fallback
        # raw.githubusercontent.com has ~10k req/hour vs API's 60 req/hour
        processed = 0
        download_errors = []
        rate_limited = False
        for item in file_urls[:200]:
            try:
                content = None
                path = item['path']
                # Prefer raw URL (much higher rate limit)
                raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{default_branch}/{path}"
                with httpx.Client(timeout=30.0, headers=headers, follow_redirects=True) as client:
                    resp = client.get(raw_url)
                    if resp.status_code == 200:
                        content = resp.text
                    elif resp.status_code in (403, 404):
                        # Fall back to Contents API for binary/special files
                        contents_url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
                        resp2 = client.get(contents_url)
                        if resp2.status_code == 200:
                            data = resp2.json()
                            if data.get('encoding') == 'base64' and data.get('content'):
                                import base64
                                content = base64.b64decode(data['content']).decode('utf-8', errors='replace')
                            elif data.get('content'):
                                content = data['content']
                        elif resp2.status_code == 403:
                            rate_limited = True
                if content and len(content) > 100:
                    metadata = {
                        "type": "github",
                        "repo": f"{owner}/{repo}",
                        "path": path,
                        "url": item['url']
                    }
                    chunk_id, status = save_chunk(content, f"github:{owner}/{repo}", metadata)
                    results.append({
                        "file": item['name'],
                        "path": path,
                        "chunk_id": chunk_id,
                        "status": status
                    })
                    processed += 1
            except Exception as e:
                print(f"Error processing {item['path']}: {e}", file=sys.stderr)

        return jsonify({
            "success": True,
            "repo": f"{owner}/{repo}",
            "files_found": len(file_urls),
            "files_processed": processed,
            "files": results[:20],
            "rate_limited": rate_limited,
            "errors": download_errors[:5] if download_errors else None
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route('/api/ingest/directory', methods=['POST'])
def ingest_directory():
    """Scan and ingest files from a directory path"""
    data = request.json
    directory = data.get('directory', '')
    extensions = data.get('extensions', ['md', 'txt', 'py', 'js', 'ts', 'html', 'json', 'yaml', 'yml'])

    if not directory:
        return jsonify({"error": "No directory path provided"}), 400

    try:
        if not os.path.exists(directory):
            return jsonify({"error": f"Directory not found: {directory}"}), 400

        if not os.path.isdir(directory):
            return jsonify({"error": f"Not a directory: {directory}"}), 400

        results = []
        extensions = [ext.lower().strip('.') for ext in extensions]

        def scan_dir(path, depth=0):
            if depth > 5:  # Max depth
                return

            try:
                for item in os.listdir(path):
                    if item.startswith('.') or item in ['node_modules', '__pycache__', 'vendor', '.git']:
                        continue

                    item_path = os.path.join(path, item)
                    if os.path.isfile(item_path):
                        ext = item.split('.')[-1].lower() if '.' in item else ''
                        if ext in extensions:
                            try:
                                with open(item_path, 'r', encoding='utf-8', errors='ignore') as f:
                                    content = f.read()
                                if len(content) > 100:
                                    metadata = {
                                        "type": "file",
                                        "directory": directory,
                                        "path": item_path,
                                        "relative_path": os.path.relpath(item_path, directory)
                                    }
                                    chunk_id, status = save_chunk(content, f"dir:{directory}", metadata)
                                    results.append({
                                        "file": item,
                                        "path": os.path.relpath(item_path, directory),
                                        "chunk_id": chunk_id,
                                        "status": status
                                    })
                            except Exception as e:
                                pass
                    elif os.path.isdir(item_path):
                        scan_dir(item_path, depth + 1)
            except PermissionError:
                pass

        scan_dir(directory)

        return jsonify({
            "success": True,
            "directory": directory,
            "files_found": len(results),
            "files": results[:50]
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route('/api/ingest/file', methods=['POST'])
def ingest_file():
    """Upload and ingest a file"""
    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "Empty filename"}), 400

    try:
        content = file.read().decode('utf-8', errors='ignore')
        if not content.strip():
            return jsonify({"error": "Empty file"}), 400

        metadata = {
            "type": "upload",
            "filename": file.filename,
            "size": len(content)
        }
        chunk_id, status = save_chunk(content, f"file:{file.filename}", metadata)

        return jsonify({
            "success": True,
            "filename": file.filename,
            "chunk_id": chunk_id,
            "status": status,
            "size": len(content)
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# ============================================================
# 语义搜索模块：Embedding + 文档聚合 + LLM 评分
# ============================================================

# Embedding 提供者配置（默认 Ollama 本地，后续换成内网模型）
# 优先级：Ollama > DeepSeek > 关键词搜索
EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "ollama")  # ollama | deepseek | keyword
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")
EMBEDDING_BASE_URL = os.getenv("EMBEDDING_BASE_URL", "http://localhost:11434")  # Ollama 地址


def get_embedding(text: str) -> list:
    """获取文本向量（支持 Ollama / DeepSeek / OpenAI 兼容端点）"""
    import httpx
    provider = EMBEDDING_PROVIDER.lower()

    if provider == "ollama":
        payload = {"model": EMBEDDING_MODEL, "prompt": text[:8000]}
        with httpx.Client(timeout=120.0) as client:
            resp = client.post(f"{EMBEDDING_BASE_URL}/api/embeddings", json=payload)
            resp.raise_for_status()
            return resp.json()["embedding"]

    # DeepSeek / OpenAI 兼容格式
    # 注意：端点是 /v1/embeddings，模型名是 deepseek-embedding
    api_key = os.getenv("DEEPSEEK_API_KEY", "")
    base_url = os.getenv("EMBEDDING_BASE_URL", "https://api.deepseek.com")
    model = os.getenv("EMBEDDING_MODEL", "deepseek-embedding")

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {"model": model, "input": text[:8000]}

    with httpx.Client(timeout=60.0) as client:
        resp = client.post(f"{base_url}/v1/embeddings", headers=headers, json=payload)
        resp.raise_for_status()
        return resp.json()["data"][0]["embedding"]


def cosine_similarity(a: list, b: list) -> float:
    """计算两个向量的余弦相似度"""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    return dot / (norm_a * norm_b + 1e-9)


def compute_all_embeddings(chunks: list) -> dict:
    """批量计算所有 chunks 的 embedding，结果缓存到文件"""
    emb_file = os.path.join(STORAGE_PATH, "embeddings.json")
    cached = {}
    if os.path.exists(emb_file):
        try:
            with open(emb_file, 'r', encoding='utf-8') as f:
                cached = json.load(f)
        except Exception:
            cached = {}

    def text_hash(t):
        return hashlib.md5(t.encode('utf-8', errors='replace')).hexdigest()[:12]

    chunks_needing_emb = []
    for chunk in chunks:
        cid = chunk['id']
        h = text_hash(chunk['text'])
        if cid not in cached or cached[cid].get('_hash') != h:
            chunks_needing_emb.append(chunk)

    if chunks_needing_emb:
        logger.info(f"需要计算 {len(chunks_needing_emb)}/{len(chunks)} 个 chunk 的 embedding...")
        for i, chunk in enumerate(chunks_needing_emb):
            try:
                emb = get_embedding(chunk['text'])
                cached[chunk['id']] = {"vec": emb, "_hash": text_hash(chunk['text'])}
                if (i + 1) % 10 == 0:
                    logger.info(f"  embedding 进度: {i+1}/{len(chunks_needing_emb)}")
            except Exception as e:
                logger.warning(f"  embedding 失败 {chunk['id']}: {e}")

        with open(emb_file, 'w', encoding='utf-8') as f:
            json.dump(cached, f, ensure_ascii=False)
        logger.info(f"embedding 已缓存到 {emb_file}")

    return cached


def get_doc_id(chunk: dict) -> str:
    """根据 chunk 来源生成文档 ID，实现文档聚合"""
    src = chunk.get('source', '')
    meta = chunk.get('metadata', {}) or {}
    src_type = src.split(':')[0]

    if src_type == 'dir':
        rel = meta.get('relative_path', '')
        directory = meta.get('directory', '')
        return f"dir:{directory}:{rel}"
    elif src_type == 'url':
        return f"url:{src.replace('url:', '')}"
    elif src_type == 'github':
        path = meta.get('path', '')
        parts = src.split(':')
        repo = parts[1] if len(parts) > 1 else ''
        return f"github:{repo}:{path}" if path else f"github:{repo}"
    elif src_type == 'minimax':
        parts = src.split(':')
        return f"minimax:{':'.join(parts[1:])}"
    elif src_type == 'manual':
        return f"manual:{chunk.get('id', '')}"
    else:
        return f"other:{src}"


def get_doc_info(chunk: dict) -> dict:
    """从 chunk 构建文档信息"""
    src = chunk.get('source', '')
    src_type = src.split(':')[0]
    meta = chunk.get('metadata', {}) or {}
    text = chunk.get('text', '')

    # 提取第一个 markdown 标题
    m = re.search(r'^#{1,6}\s+(.+)$', text, re.MULTILINE)
    doc_title = m.group(1).strip()[:80] if m else ''

    badge_map = {'manual': '手动输入', 'dir': '文件', 'url': '网页',
                 'github': 'GitHub', 'minimax': 'MiniMax', 'file': '文件'}
    icon_map = {'manual': 'ri-edit-line', 'dir': 'ri-folder-line', 'url': 'ri-global-line',
                'github': 'ri-github-line', 'minimax': 'ri-robot-line', 'file': 'ri-file-text-line'}

    title = doc_title
    sub = ''

    if src_type == 'dir':
        rel = meta.get('relative_path', '')
        title = f"文件:{rel}" if rel else (doc_title or '目录文件')
        sub = meta.get('directory', '')
    elif src_type == 'url':
        title = doc_title or meta.get('title', '') or src.replace('url:', '')
        domain = src.replace('url:', '').replace('https://', '').replace('http://', '').split('/')[0]
        sub = domain
    elif src_type == 'github':
        # source 中不含 path，path 在 metadata 里
        file_path = meta.get('path', '') or ':'.join(src.split(':')[2:])
        file_name = file_path.split('/')[-1] if file_path else ''
        title = doc_title or meta.get('title', '') or file_name or 'GitHub 文档'
        sub = ':'.join(src.split(':')[1:])  # repo 名
    elif src_type == 'minimax':
        name = ':'.join(src.split(':')[1:])
        title = doc_title or meta.get('title', '') or name
    elif src_type == 'manual':
        title = doc_title or '手动输入'

    return {
        "id": get_doc_id(chunk),
        "title": title,
        "sub": sub,
        "source": src,
        "source_type": src_type,
        "badge": badge_map.get(src_type, '其他'),
        "icon": icon_map.get(src_type, 'ri-file-text-line'),
        "metadata": meta,
        "text": text,
        "chunk_id": chunk.get('id', ''),
        "created_at": chunk.get('created_at', '')
    }


def semantic_search(query: str, chunks: list, embeddings: dict, top_k: int = 20) -> list:
    """语义向量搜索：返回 top_k 最相似的 (score, chunk)"""
    try:
        q_emb = get_embedding(query)
    except Exception as e:
        logger.warning(f"embedding 查询失败，降级为关键词搜索: {e}")
        return []

    scored = []
    for chunk in chunks:
        emb_data = embeddings.get(chunk['id'])
        if emb_data and 'vec' in emb_data:
            sim = cosine_similarity(q_emb, emb_data['vec'])
            scored.append((sim, chunk))

    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[:top_k]


def keyword_search(query: str, chunks: list, top_k: int = 20) -> list:
    """关键词 fallback 搜索"""
    q_lower = query.lower()
    en_words = re.findall(r'[a-zA-Z]{2,}', q_lower)
    cn_phrases = re.findall(r'[一-鿿]{2,}', query)

    def extract_cn_bigrams(text):
        result = []
        i = 0
        while i < len(text) - 1:
            c1, c2 = text[i], text[i + 1]
            if '一' <= c1 <= '鿿' and '一' <= c2 <= '鿿':
                result.append(c1 + c2)
                i += 1
            else:
                i += 1
        return result

    q_bigrams = extract_cn_bigrams(query)
    scored = []
    for chunk in chunks:
        text_lower = chunk['text'].lower()
        chunk_bigrams = extract_cn_bigrams(chunk['text'])
        score = 0
        for kw in en_words:
            if kw in text_lower:
                score += 2
        matched_bigrams = set(q_bigrams) & set(chunk_bigrams)
        score += len(matched_bigrams) * 3
        for phrase in cn_phrases:
            if phrase in chunk['text']:
                score += 5
        if score > 0:
            scored.append((score, chunk))

    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[:top_k]



@app.route('/api/query', methods=['POST'])
def query():
    """语义搜索 + 关键词 fallback，完全本地（Ollama），毫秒级响应"""
    data = request.json
    question = data.get('question', '')

    if not question:
        return jsonify({"error": "No question provided"}), 400

    try:
        chunks_file = os.path.join(STORAGE_PATH, "text_chunks.json")
        if not os.path.exists(chunks_file):
            return jsonify({"documents": {"high": [], "medium": []}})

        with open(chunks_file, 'r', encoding='utf-8') as f:
            chunks = json.load(f)

        if not chunks:
            return jsonify({"documents": {"high": [], "medium": []}})

        # 1. 尝试语义搜索（Ollama，本地）
        embeddings = compute_all_embeddings(chunks)
        scored = semantic_search(question, chunks, embeddings, top_k=len(chunks))

        # 2. 无语义结果时降级为关键词搜索
        search_mode = "semantic"
        if not scored:
            logger.info("语义搜索无结果，降级为关键词搜索")
            scored = keyword_search(question, chunks, top_k=len(chunks))
            search_mode = "keyword"

        # 3. 按文档聚合：优先保留有意义的标题（markdown 标题），同时取最高语义分
        doc_map = {}
        GENERIC_TITLES = {'GitHub 文档', 'manual', '其他', '未命名文档'}
        for sim_score, chunk in scored:
            did = get_doc_id(chunk)
            new_info = get_doc_info(chunk)
            new_title = new_info.get('title', '')
            new_is_generic = new_title in GENERIC_TITLES
            if did not in doc_map:
                doc_map[did] = new_info
                doc_map[did]['_score'] = sim_score
            else:
                curr = doc_map[did]
                curr_is_generic = curr.get('title', '') in GENERIC_TITLES
                # 有意义标题优先，无论分数高低都替换通用标题
                if new_is_generic and not curr_is_generic:
                    # 当前有意义，新的是通用：保留当前
                    curr['_score'] = max(curr['_score'], sim_score)
                elif not new_is_generic and curr_is_generic:
                    # 当前是通用，新的是有意义：替换
                    doc_map[did] = new_info
                    doc_map[did]['_score'] = sim_score
                elif not new_is_generic and not curr_is_generic:
                    # 两者都有意义：保留更高语义分的
                    if sim_score > curr['_score']:
                        doc_map[did] = new_info
                        doc_map[did]['_score'] = sim_score
                    else:
                        curr['_score'] = max(curr['_score'], sim_score)
                else:
                    # 两者都是通用：取更高语义分
                    curr['_score'] = max(curr['_score'], sim_score)

        # 4. 语义排序 + 关键词过滤（title 命中为强信号）
        def keyword_signals(doc_title: str, q: str) -> dict:
            """
            返回 title 的关键词命中详情：
            - phrase_hit: 完整查询词组是否在 title 中
            - n_bigrams: query 中非重叠 bigram 的 title 命中数
            - en_hit: EN 词命中（词边界，最短3字符）
            """
            cn_chars = re.findall(r'[一-鿿]', q)
            en_words = re.findall(r'[a-zA-Z]{2,}', q.lower())
            cn_phrases = re.findall(r'[一-鿿]{2,}', q)

            # 完整词组命中
            phrase_hit = any(doc_title.find(ph) >= 0 for ph in cn_phrases)

            # EN 词命中：词边界 + 最短3字符（避免 "js" 匹配 "labeler.js"）
            en_hit = any(re.search(r'\b' + re.escape(w) + r'\b', doc_title.lower()) for w in en_words if len(w) >= 3)

            # 非重叠 bigram 计数（每 2 相邻字为一组，title 含该 2 字即算命中）
            # 对于 "微服务架构" -> ['微服务', '架构'] -> 2 组
            # 对于 "微信朋友圈" -> ['微信', '朋友圈'] -> 2 组
            # 对于 "部署" -> [] -> 0 组（无 bigram）
            n_bigrams = 0
            for i in range(0, len(cn_chars) - 1, 2):  # 步长 2，非重叠
                bg = cn_chars[i] + cn_chars[i + 1]
                if doc_title.find(bg) >= 0:
                    n_bigrams += 1

            return {
                'phrase_hit': phrase_hit,
                'en_hit': en_hit,
                'n_bigrams': n_bigrams
            }

        def reason_text(sig: dict, sem: float, text_hit: bool, is_ultra_short: bool, title: str, q: str) -> str:
            """Generate a concise reason why this doc was recommended"""
            pct = f"{sem:.0%}"
            cn_phrases = re.findall(r'[一-鿿]{2,}', q)
            if sig['phrase_hit']:
                matched = [ph for ph in cn_phrases if title.find(ph) >= 0]
                kw = '、'.join(matched[:2])
                return f"标题匹配「{kw}」，语义相似度 {pct}"
            if sig['en_hit']:
                return f"英文关键词匹配，语义相似度 {pct}"
            if sig['n_bigrams'] >= 2:
                return f"标题高度相关，语义相似度 {pct}"
            if sig['n_bigrams'] >= 1:
                return f"标题部分匹配，语义相似度 {pct}"
            if text_hit:
                return f"正文内容匹配「{q}」，语义相似度 {pct}"
            return f"语义相似度 {pct}"

        def one_sentence(text: str, max_len: int = 100) -> str:
            """Extract the first meaningful sentence as a summary"""
            t = text.strip()
            # Strip markdown headings (# Title) and RST headings (Title\n=====)
            t = re.sub(r'^#{1,6}\s+[^\n]+\n', '', t)
            t = re.sub(r'^[^\n]+\n[=\-~^]{3,}\n', '', t)
            # Strip leading blockquote markers and whitespace
            t = re.sub(r'^>\s*', '', t.strip())
            t = t.strip()
            # Find first sentence ending with 。.!?！？\n
            m = re.search(r'^(.+?[。.!?！？\n])(?:\s|$)', t, re.DOTALL)
            if m:
                s = m.group(1).strip()
                if len(s) > max_len:
                    s = s[:max_len] + '...'
                return s
            if len(t) > max_len:
                return t[:max_len] + '...'
            return t if t else ''

        scored_docs = []
        for doc in doc_map.values():
            sem_score = doc['_score']
            sig = keyword_signals(doc.get('title', ''), question)
            phrase_hit = sig['phrase_hit']
            en_hit = sig['en_hit']
            n_bigrams = sig['n_bigrams']

            # 关键词匹配强度 (0-1)
            if phrase_hit:
                kw_strength = 0.9
            elif en_hit:
                kw_strength = 0.8
            elif n_bigrams >= 3:
                kw_strength = 0.65
            elif n_bigrams >= 2:
                kw_strength = 0.5
            elif n_bigrams >= 1:
                kw_strength = 0.3
            else:
                kw_strength = 0.0

            doc_text = doc.get('text', '')
            # 正文命中：精确匹配 或 中文短语命中 或 首 bigram 命中（首词最具区分度）
            cn_chars = re.findall(r'[一-鿿]', question)
            cn_phrases = re.findall(r'[一-鿿]{2,}', question)
            first_bigram = cn_chars[0] + cn_chars[1] if len(cn_chars) >= 2 else ''
            text_hit = (question.lower() in doc_text.lower()
                        or any(ph in doc_text for ph in cn_phrases)
                        or (first_bigram and first_bigram in doc_text))
            is_ultra_short = len(question.strip()) <= 4 and re.match(r'^[a-zA-Z]+$', question.strip())

            # 正文匹配信号（标题无中文关键词时，正文命中作为弱信号）
            if kw_strength == 0 and text_hit and not is_ultra_short:
                kw_strength = 0.15

            # 综合关联度 = 语义相似度(55%) + 关键词匹配强度(45%)
            doc['_rank'] = round(sem_score * 0.55 + kw_strength * 0.45, 4)

            # HIGH: 关键词命中（phrase/bigram/en）且 语义 >= 0.50
            # MEDIUM A: 关键词命中（phrase/bigram/en）且 语义 >= 0.30
            # MEDIUM B: 极短 EN 查询（≤4 字符）且文本命中
            # MEDIUM C: 中文查询正文命中但标题无关键词，语义 >= 0.50
            if (phrase_hit or n_bigrams >= 2 or en_hit) and sem_score >= 0.50:
                doc['_rel'] = 'high'
            elif (phrase_hit or n_bigrams >= 1 or en_hit) and sem_score >= 0.30:
                doc['_rel'] = 'medium'
            elif is_ultra_short and sem_score >= 0.40 and text_hit:
                doc['_rel'] = 'medium'
            elif text_hit and sem_score >= 0.50 and kw_strength == 0.15:
                doc['_rel'] = 'medium'
            else:
                doc['_rel'] = 'skip'

            if doc['_rel'] != 'skip':
                doc['_reason'] = reason_text(sig, sem_score, text_hit, is_ultra_short,
                                             doc.get('title', ''), question)
                doc['_summary'] = one_sentence(doc_text)
            scored_docs.append(doc)

        # 按综合关联度降序排列（skip 排最后，rank 高的排前面）
        scored_docs.sort(key=lambda x: (0 if x['_rel'] == 'skip' else 1, x['_rank']), reverse=True)

        documents = []
        seen_ids = set()
        for doc in scored_docs:
            rel = doc.pop('_rel')
            if rel == 'skip':
                continue
            dedup_key = doc.get('source', '') + '|' + doc.get('title', '')
            if dedup_key in seen_ids:
                continue
            seen_ids.add(dedup_key)
            doc['_rel'] = rel  # 保留分类标签供前端样式区分
            documents.append(doc)
            if len(documents) >= 20:
                break

        # 清理内部字段
        for doc in documents:
            doc.pop('_score', None)
            doc.pop('_idx', None)

        return jsonify({
            "documents": documents,
            "chunks_searched": len(scored),
            "search_mode": search_mode
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route('/api/graph')
def knowledge_graph():
    """Get knowledge relationship graph with rich entity extraction"""
    try:
        chunks_file = os.path.join(STORAGE_PATH, "text_chunks.json")
        if not os.path.exists(chunks_file):
            return jsonify({"nodes": [], "links": []})

        with open(chunks_file, 'r', encoding='utf-8') as f:
            chunks = json.load(f)

        nodes = []
        links = []
        entity_map = {}
        # Known tech/entity patterns
        TECH_TERMS = {
            'docker', 'kubernetes', 'python', 'javascript', 'typescript',
            'java', 'golang', 'rust', 'react', 'vue', 'angular', 'flask',
            'fastapi', 'django', 'nodejs', 'postgresql', 'mongodb', 'redis',
            'neo4j', 'pgvector', 'nginx', 'linux', 'git', 'github', 'api',
            'rest', 'graphql', 'http', 'websocket', 'grpc', 'jwt', 'oauth',
            'minimax', 'deepseek', 'openai', 'claude', 'anthropic', 'jina',
            'siliconflow', 'weknora', 'lightrag', 'flask', 'crawl4ai',
            'microservice', 'dockerfile', 'docker compose', 'elasticsearch',
            'prometheus', 'grafana', 'nginx', 'terraform', 'ansible',
            'helm', 'istio', 'linkerd', 'kafka', 'rabbitmq',
        }
        TECH_RE = r'\b(?:' + '|'.join(re.escape(t) for t in TECH_TERMS) + r')\b'

        for chunk in chunks:
            text = chunk['text']
            source = chunk['source']
            source_type = source.split(':')[0]

            # --- Chunk node ---
            # Label: priority — metadata.title > metadata.path filename > GitHub path > first meaningful line
            metadata = chunk.get('metadata', {}) or {}
            label = ''
            if metadata.get('title'):
                label = metadata['title']
            elif metadata.get('relative_path'):
                label = metadata['relative_path']
            elif metadata.get('path') and source_type == 'github':
                # GitHub: extract filename from file path
                label = metadata['path'].split('/')[-1]
            # Fall back to first meaningful text line (skip chunk ID comments)
            if not label:
                text_lines = [l.strip() for l in chunk['text'].split('\n') if l.strip()]
                # Skip lines that look like chunk ID headers: "# chunk-0-abc123" or "chunk-0-abc123"
                meaningful = [l for l in text_lines if not re.match(r'^#?\s*chunk-\d+-[\w]+', l, re.I)]
                first_line = meaningful[0] if meaningful else (text_lines[0] if text_lines else chunk['text'][:80])
                label = re.sub(r'^[#*`>\-_]+\s*', '', first_line).strip()[:60]
            # Last resort
            if not label or re.match(r'^[\d\w\-]{1,6}$', label):
                label = re.sub(r'^[#*`>\-_]+\s*', '', chunk['text']).strip()[:40]
            if not label:
                label = f"条目 {chunk['id'].split('-')[1][:6] if '-' in chunk['id'] else chunk['id']}"

            text_len = len(chunk['text'])
            # Truncate preview only for very large chunks (>2MB)
            preview_text = chunk['text'] if text_len <= 2 * 1024 * 1024 else chunk['text'][:102400]
            chunk_node = {
                "id": chunk['id'],
                "label": label,
                "type": "chunk",
                "source": source,
                "preview": preview_text,
                "text_size": text_len,
                "large": text_len > 2 * 1024 * 1024,
                "source_type": source_type
            }
            nodes.append(chunk_node)

            # --- Extract entities ---
            entities_in_chunk = set()

            # 1. Tech terms (known list, min 3 chars)
            for m in re.finditer(TECH_RE, text, re.I):
                val = m.group().lower()
                if len(val) >= 3:
                    entities_in_chunk.add(val)

            # 2. Chinese tech/philosophy phrases (Chinese chars + copula)
            for m in re.finditer(r'([一-鿿]{2,6})\s+(?:是|为|有|指|提供|支持|通过)', text):
                entities_in_chunk.add(m.group(1))

            # 3. Chinese proper nouns with known suffixes
            for m in re.finditer(r'([一-鿿]{2,10})(?:平台|工具|系统|服务|框架|协议|模型|语言|库|引擎)', text):
                entities_in_chunk.add(m.group(1))

            # 4. Model/product names (specific patterns: version numbers, known products)
            for m in re.finditer(r'\b([A-Z][a-z]+(?:[A-Z][a-z]+)*\d*(?:\.\d+)+)\b', text):
                entities_in_chunk.add(m.group(1))
            for m in re.finditer(r'\b([A-Z][a-z]+(?:[-][A-Z][a-z]+)+)\b', text):
                entities_in_chunk.add(m.group(1))

            # 5. Book/doc titles in 《》
            for m in re.finditer(r'《([^》]{2,20})》', text):
                entities_in_chunk.add(m.group(1))

            # 6. Chinese tech concept phrases (exact match)
            CHINESE_TECH = {
                '人工智能','机器学习','深度学习','神经网络','大模型','向量数据库',
                '知识图谱','智能问答','语义搜索','知识库','自然语言','文本生成',
                '语音合成','图像生成','视频生成','代码生成','智能助手','智能体',
                '混合检索','智能分块','语义理解','知识管理','文档解析'
            }
            for phrase in CHINESE_TECH:
                if phrase in text:
                    entities_in_chunk.add(phrase)

            # Add entities to graph
            for entity in entities_in_chunk:
                eid = f"entity:{entity[:25]}"
                if eid not in entity_map:
                    entity_map[eid] = {
                        "id": eid,
                        "label": entity,
                        "type": "entity"
                    }
                    nodes.append(entity_map[eid])
                links.append({
                    "source": eid,
                    "target": chunk['id'],
                    "type": "mentions"
                })

        # Limit: cap entity→chunk links for visual clarity
        entity_chunk_count = {}
        for link in links:
            if link['type'] == 'mentions':
                eid = link['source']
                entity_chunk_count[eid] = entity_chunk_count.get(eid, 0) + 1

        entity_nodes = sorted(entity_chunk_count.items(), key=lambda x: x[1], reverse=True)
        # Keep entities that appear in 2-5 chunks (avoid noise, avoid hub nodes)
        good_entities = {eid for eid, cnt in entity_chunk_count.items() if 2 <= cnt <= 5}
        # Also keep top 8 by connectivity
        for eid, _ in entity_nodes[:8]:
            good_entities.add(eid)
        # Cap at 60 total entity nodes for performance
        if len(good_entities) > 60:
            good_entities = set(eid for eid, _ in entity_nodes[:60])

        # Filter nodes/links
        filtered_nodes = [n for n in nodes if n['type'] != 'entity' or n['id'] in good_entities]
        filtered_links = [l for l in links
                          if l['type'] != 'mentions' or l['source'] in good_entities]

        # Add link_count to entity nodes for tooltip
        for n in filtered_nodes:
            if n['type'] == 'entity':
                n['link_count'] = entity_chunk_count.get(n['id'], 0)

        return jsonify({
            "nodes": filtered_nodes,
            "links": filtered_links,
            "stats": {
                "total_chunks": len(chunks),
                "total_entities": len(good_entities),
                "total_sources": len({c['source'].split(':')[0] for c in chunks}),
                "total_links": len(filtered_links)
            }
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route('/api/stats')
def stats():
    """Get knowledge base statistics"""
    try:
        chunks_file = os.path.join(STORAGE_PATH, "text_chunks.json")
        stats = {
            "storage_path": STORAGE_PATH,
            "chunks_count": 0,
            "sources": {},
            "types": {}
        }

        if os.path.exists(chunks_file):
            with open(chunks_file, 'r', encoding='utf-8') as f:
                chunks = json.load(f)
                stats["chunks_count"] = len(chunks)

                for chunk in chunks:
                    # Count by source type
                    source_type = chunk['source'].split(':')[0] if ':' in chunk['source'] else 'manual'
                    stats["sources"][source_type] = stats["sources"].get(source_type, 0) + 1

                    # Count by metadata type
                    meta_type = chunk.get('metadata', {}).get('type', 'unknown')
                    stats["types"][meta_type] = stats["types"].get(meta_type, 0) + 1

        return jsonify(stats)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/chunks')
def list_chunks():
    """List all chunks"""
    try:
        chunks_file = os.path.join(STORAGE_PATH, "text_chunks.json")
        if not os.path.exists(chunks_file):
            return jsonify({"chunks": []})

        with open(chunks_file, 'r', encoding='utf-8') as f:
            chunks = json.load(f)

        # Return full info including text for modal
        result = [{
            "id": c['id'],
            "source": c['source'],
            "text": c.get('text', ''),
            "text_size": len(c.get('text', '')),
            "large": len(c.get('text', '')) > 2 * 1024 * 1024,
            "created_at": c.get('created_at', ''),
            "metadata": c.get('metadata', {})
        } for c in chunks]

        return jsonify({"chunks": result, "total": len(result)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/chunks/<chunk_id>/download')
def download_chunk(chunk_id):
    """Download full chunk text as a file"""
    try:
        chunks_file = os.path.join(STORAGE_PATH, "text_chunks.json")
        if not os.path.exists(chunks_file):
            return jsonify({"error": "Not found"}), 404

        with open(chunks_file, 'r', encoding='utf-8') as f:
            chunks = json.load(f)

        chunk = next((c for c in chunks if c['id'] == chunk_id), None)
        if not chunk:
            return jsonify({"error": "Chunk not found"}), 404

        text = chunk.get('text', '')
        metadata = chunk.get('metadata', {}) or {}
        # Build a filename from metadata
        if metadata.get('relative_path'):
            filename = metadata['relative_path'].replace('/', '_')
        elif metadata.get('title'):
            filename = metadata['title'][:80] + '.txt'
        elif metadata.get('path'):
            filename = metadata['path'].replace('/', '_')
        else:
            filename = f"chunk_{chunk_id[:8]}.txt"

        from flask import Response
        return Response(
            text,
            mimetype='text/plain; charset=utf-8',
            headers={
                'Content-Disposition': f'attachment; filename*=UTF-8\'\'{filename}',
                'Content-Length': str(len(text))
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/clear', methods=['POST'])
def clear():
    """Clear all knowledge"""
    try:
        chunks_file = os.path.join(STORAGE_PATH, "text_chunks.json")
        if os.path.exists(chunks_file):
            os.remove(chunks_file)
        return jsonify({"success": True, "message": "Knowledge base cleared"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/delete/<chunk_id>', methods=['DELETE'])
def delete_chunk(chunk_id):
    """Delete a specific chunk"""
    try:
        chunks_file = os.path.join(STORAGE_PATH, "text_chunks.json")
        if not os.path.exists(chunks_file):
            return jsonify({"error": "No chunks found"}), 404

        with open(chunks_file, 'r', encoding='utf-8') as f:
            chunks = json.load(f)

        original_len = len(chunks)
        chunks = [c for c in chunks if c['id'] != chunk_id]

        if len(chunks) == original_len:
            return jsonify({"error": f"Chunk {chunk_id} not found"}), 404

        with open(chunks_file, 'w', encoding='utf-8') as f:
            json.dump(chunks, f, ensure_ascii=False, indent=2)

        return jsonify({"success": True, "deleted": chunk_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    print(f"Starting WikiService on port {PORT}", file=sys.stderr)
    app.run(host='0.0.0.0', port=PORT, debug=False, threaded=True)
