"""
MCP Server - Enhanced tools for WikiService
Extends WeKnora built-in MCP with custom tools for:
- Obsidian-style relation exploration
- Graph traversal and community detection
- Multi-source ingestion triggers
"""
import os
import json
import requests
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

WEKNORA_API = os.getenv("WEKNORA_API_URL", "http://localhost:3000")

@dataclass
class SearchResult:
    """Search result item"""
    id: str
    title: str
    score: float
    summary: str
    kb_id: str

@dataclass
class Relation:
    """Knowledge graph relation"""
    source_id: str
    target_id: str
    type: str  # semantic, reference, tag, share_source
    weight: float

class WikiServiceMCP:
    """MCP Server for WikiService knowledge base operations"""

    def __init__(self, weknora_api: str = WEKNORA_API):
        self.weknora_api = weknora_api

    # ============== Search Tools ==============

    def search_wiki(
        self,
        query: str,
        top_k: int = 10,
        include_relations: bool = True,
        kb_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Search Wiki with hybrid retrieval (vector + BM25 + graph)

        Args:
            query: Search query string
            top_k: Number of top results to return
            include_relations: Whether to include relation graph
            kb_id: Knowledge base ID (optional, searches all if not specified)

        Returns:
            {
                "query": str,
                "results": [SearchResult],
                "relations": [Relation],
                "graph": {"nodes": [...], "edges": [...]}
            }
        """
        # Build search request
        payload = {
            "query": query,
            "top_k": top_k,
            "include_relations": include_relations,
        }
        if kb_id:
            payload["kb_id"] = kb_id

        # Call WeKnora search API
        resp = requests.post(
            f"{self.weknora_api}/api/v1/search",
            json=payload,
            timeout=30
        )
        resp.raise_for_status()
        data = resp.json()

        # Parse results
        results = [
            SearchResult(
                id=r["id"],
                title=r["title"],
                score=r["score"],
                summary=r.get("summary", ""),
                kb_id=r.get("kb_id", "")
            )
            for r in data.get("results", [])
        ]

        # Parse relations
        relations = [
            Relation(
                source_id=r["source"],
                target_id=r["target"],
                type=r["type"],
                weight=r["weight"]
            )
            for r in data.get("relations", [])
        ]

        return {
            "query": query,
            "results": results,
            "relations": relations,
            "graph": data.get("graph", {"nodes": [], "edges": []})
        }

    def explore_relations(
        self,
        doc_id: str,
        depth: int = 1,
        relation_types: Optional[List[str]] = None,
        kb_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Explore related documents from a starting document

        Args:
            doc_id: Starting document ID
            depth: Graph traversal depth (1-3 recommended)
            relation_types: Filter by relation types (semantic, reference, tag, share_source)
            kb_id: Knowledge base ID

        Returns:
            {
                "center_doc": {"id": ..., "title": ...},
                "related_docs": [...],
                "relations": [...],
                "graph": {"nodes": [...], "edges": [...]}
            }
        """
        payload = {
            "doc_id": doc_id,
            "depth": depth,
        }
        if relation_types:
            payload["relation_types"] = relation_types
        if kb_id:
            payload["kb_id"] = kb_id

        resp = requests.post(
            f"{self.weknora_api}/api/v1/graph/explore",
            json=payload,
            timeout=30
        )
        resp.raise_for_status()
        return resp.json()

    # ============== Ingestion Tools ==============

    def ingest_webpage(
        self,
        url: str,
        kb_id: str,
        deep_crawl: bool = False,
        auth: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Manually trigger web page ingestion

        Args:
            url: URL to crawl
            kb_id: Target knowledge base ID
            deep_crawl: Whether to recursively crawl linked pages
            auth: Authentication config (cookie/form)

        Returns:
            {"status": "success", "pages_crawled": int, "docs_ingested": int}
        """
        payload = {
            "url": url,
            "kb_id": kb_id,
            "deep_crawl": deep_crawl,
        }
        if auth:
            payload["auth"] = auth

        resp = requests.post(
            f"{self.weknora_api}/api/v1/ingest/web",
            json=payload,
            timeout=60
        )
        resp.raise_for_status()
        return resp.json()

    def ingest_git_repo(
        self,
        repo_url: str,
        kb_id: str,
        branch: str = "main",
        include_patterns: Optional[List[str]] = None,
        exclude_patterns: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Manually trigger Git repository ingestion

        Args:
            repo_url: Git repository URL
            kb_id: Target knowledge base ID
            branch: Branch to clone
            include_patterns: File patterns to include
            exclude_patterns: File patterns to exclude

        Returns:
            {"status": "success", "docs_ingested": int}
        """
        payload = {
            "repo_url": repo_url,
            "kb_id": kb_id,
            "branch": branch,
        }
        if include_patterns:
            payload["include_patterns"] = include_patterns
        if exclude_patterns:
            payload["exclude_patterns"] = exclude_patterns

        resp = requests.post(
            f"{self.weknora_api}/api/v1/ingest/git",
            json=payload,
            timeout=120
        )
        resp.raise_for_status()
        return resp.json()

    # ============== Graph Tools ==============

    def get_wiki_graph(
        self,
        kb_id: str,
        center_doc_id: Optional[str] = None,
        depth: int = 2
    ) -> Dict[str, Any]:
        """
        Get knowledge graph structure

        Args:
            kb_id: Knowledge base ID
            center_doc_id: Optional center document for subgraph query
            depth: Graph traversal depth

        Returns:
            {
                "nodes": [{"id": ..., "title": ..., "type": ...}],
                "edges": [{"source": ..., "target": ..., "type": ...}]
            }
        """
        payload = {"kb_id": kb_id, "depth": depth}
        if center_doc_id:
            payload["center_doc_id"] = center_doc_id

        resp = requests.get(
            f"{self.weknora_api}/api/v1/graph",
            params=payload,
            timeout=30
        )
        resp.raise_for_status()
        return resp.json()

    def get_community_detection(
        self,
        kb_id: str,
        algorithm: str = "louvain"
    ) -> Dict[str, Any]:
        """
        Run community detection on knowledge graph

        Args:
            kb_id: Knowledge base ID
            algorithm: Detection algorithm (louvain, leiden, pagerank)

        Returns:
            {
                "communities": [{"id": ..., "name": ..., "members": [...]}],
                "node_community_map": {doc_id: community_id}
            }
        """
        payload = {
            "kb_id": kb_id,
            "algorithm": algorithm
        }

        resp = requests.post(
            f"{self.weknora_api}/api/v1/graph/community-detect",
            json=payload,
            timeout=60
        )
        resp.raise_for_status()
        return resp.json()


# ============== MCP Tool Registration ==============

def register_mcp_tools(server):
    """Register WikiService MCP tools with MCP server"""

    @server.tool(name="search_wiki")
    async def search_wiki(
        query: str,
        top_k: int = 10,
        include_relations: bool = True,
        kb_id: Optional[str] = None
    ) -> str:
        """Search Wiki with hybrid retrieval, return Top-K docs + relation graph"""
        mcp = WikiServiceMCP()
        result = mcp.search_wiki(query, top_k, include_relations, kb_id)
        return json.dumps(result, ensure_ascii=False, indent=2)

    @server.tool(name="explore_relations")
    async def explore_relations(
        doc_id: str,
        depth: int = 1,
        relation_types: Optional[List[str]] = None,
        kb_id: Optional[str] = None
    ) -> str:
        """Explore related documents from a starting document"""
        mcp = WikiServiceMCP()
        result = mcp.explore_relations(doc_id, depth, relation_types, kb_id)
        return json.dumps(result, ensure_ascii=False, indent=2)

    @server.tool(name="ingest_webpage")
    async def ingest_webpage(
        url: str,
        kb_id: str,
        deep_crawl: bool = False,
        auth: Optional[Dict] = None
    ) -> str:
        """Manually trigger web page ingestion"""
        mcp = WikiServiceMCP()
        result = mcp.ingest_webpage(url, kb_id, deep_crawl, auth)
        return json.dumps(result, ensure_ascii=False, indent=2)

    @server.tool(name="ingest_git_repo")
    async def ingest_git_repo(
        repo_url: str,
        kb_id: str,
        branch: str = "main",
        include_patterns: Optional[List[str]] = None,
        exclude_patterns: Optional[List[str]] = None
    ) -> str:
        """Manually trigger Git repository ingestion"""
        mcp = WikiServiceMCP()
        result = mcp.ingest_git_repo(repo_url, kb_id, branch, include_patterns, exclude_patterns)
        return json.dumps(result, ensure_ascii=False, indent=2)

    @server.tool(name="get_wiki_graph")
    async def get_wiki_graph(
        kb_id: str,
        center_doc_id: Optional[str] = None,
        depth: int = 2
    ) -> str:
        """Get knowledge graph structure"""
        mcp = WikiServiceMCP()
        result = mcp.get_wiki_graph(kb_id, center_doc_id, depth)
        return json.dumps(result, ensure_ascii=False, indent=2)

    @server.tool(name="get_community_detection")
    async def get_community_detection(
        kb_id: str,
        algorithm: str = "louvain"
    ) -> str:
        """Run community detection on knowledge graph"""
        mcp = WikiServiceMCP()
        result = mcp.get_community_detection(kb_id, algorithm)
        return json.dumps(result, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    # Test MCP tools
    mcp = WikiServiceMCP()

    # Example: search
    print("Testing search_wiki...")
    try:
        result = mcp.search_wiki("microservices", top_k=5)
        print(f"Found {len(result['results'])} results")
    except Exception as e:
        print(f"Search error (expected if server not running): {e}")
