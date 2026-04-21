# ============================================================
# Fazle Tool Execution Engine — Secure Tool Orchestration
# Manages tool registration, permission control, and execution
# for web search, HTTP APIs, code sandbox, and DB queries
# ============================================================
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings
from prometheus_fastapi_instrumentator import Instrumentator
import httpx
import json
import logging
import uuid
import asyncio
import ipaddress
import os
import re
import socket
from typing import Optional, Any
from datetime import datetime
from enum import Enum
from urllib.parse import urlparse
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fazle-tool-engine")


class Settings(BaseSettings):
    tools_url: str = "http://fazle-tool-engine:9200"
    memory_url: str = "http://fazle-memory:8300"
    llm_gateway_url: str = "http://fazle-brain:8200"
    serper_api_key: str = ""
    tavily_api_key: str = ""
    search_provider: str = "serper"
    redis_url: str = "redis://redis:6379/7"
    max_execution_time: int = 30
    sandbox_enabled: bool = True
    # Permission defaults
    allow_web_search: bool = True
    allow_http_request: bool = True
    allow_code_sandbox: bool = False
    allow_db_query: bool = False
    allow_file_access: bool = False

    class Config:
        env_prefix = "TOOL_ENGINE_"


settings = Settings()

app = FastAPI(title="Fazle Tool Execution Engine", version="1.0.0")
Instrumentator().instrument(app).expose(app, endpoint="/metrics")

ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "https://fazle.iamazim.com,https://iamazim.com").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Models ───────────────────────────────────────────────────

class ToolCategory(str, Enum):
    web_search = "web_search"
    http_request = "http_request"
    code_sandbox = "code_sandbox"
    memory_ops = "memory_ops"
    summarize = "summarize"
    notify = "notify"


class ToolStatus(str, Enum):
    available = "available"
    disabled = "disabled"
    error = "error"


class ToolDefinition(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str
    category: ToolCategory
    description: str
    parameters_schema: dict = Field(default_factory=dict)
    enabled: bool = True
    requires_approval: bool = False
    status: ToolStatus = ToolStatus.available
    usage_count: int = 0
    last_used: Optional[str] = None


class ExecuteToolRequest(BaseModel):
    tool_name: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    user_id: Optional[str] = None
    timeout: Optional[int] = None


class ExecuteToolResponse(BaseModel):
    tool_name: str
    status: str
    result: Any = None
    error: Optional[str] = None
    execution_time_ms: int = 0
    execution_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])


class ToolPermissions(BaseModel):
    web_search: bool = True
    http_request: bool = True
    code_sandbox: bool = False
    db_query: bool = False
    file_access: bool = False


class SearchRequest(BaseModel):
    query: str
    max_results: int = 5


class ScrapeRequest(BaseModel):
    url: str
    extract_text: bool = True


class SummarizeRequest(BaseModel):
    url: Optional[str] = None
    text: Optional[str] = None


# ── Built-in tools registry ─────────────────────────────────

_tools: dict[str, ToolDefinition] = {}
_execution_log: list[dict] = []

# Permission map (category → setting)
_permission_map = {
    ToolCategory.web_search: "allow_web_search",
    ToolCategory.http_request: "allow_http_request",
    ToolCategory.code_sandbox: "allow_code_sandbox",
}


def _register_defaults():
    defaults = [
        ToolDefinition(
            name="web_search",
            category=ToolCategory.web_search,
            description="Search the web using Serper or Tavily APIs",
            parameters_schema={"query": "string", "max_results": "integer"},
        ),
        ToolDefinition(
            name="http_request",
            category=ToolCategory.http_request,
            description="Make HTTP requests to external APIs",
            parameters_schema={"url": "string", "method": "string", "body": "object"},
            requires_approval=True,
        ),
        ToolDefinition(
            name="memory_search",
            category=ToolCategory.memory_ops,
            description="Search Fazle's vector memory",
            parameters_schema={"query": "string", "top_k": "integer"},
        ),
        ToolDefinition(
            name="memory_store",
            category=ToolCategory.memory_ops,
            description="Store information in Fazle's memory",
            parameters_schema={"content": "string", "type": "string"},
        ),
        ToolDefinition(
            name="summarize",
            category=ToolCategory.summarize,
            description="Summarize text using LLM",
            parameters_schema={"text": "string", "max_length": "integer"},
        ),
        ToolDefinition(
            name="code_sandbox",
            category=ToolCategory.code_sandbox,
            description="Execute Python code in a sandboxed environment",
            parameters_schema={"code": "string", "timeout": "integer"},
            requires_approval=True,
            enabled=settings.sandbox_enabled,
        ),
    ]
    for tool in defaults:
        _tools[tool.name] = tool


# ── Tool Execution Logic ────────────────────────────────────

async def _exec_web_search(params: dict) -> Any:
    query = params.get("query", params.get("description", ""))
    if not query:
        return {"error": "No query provided"}
    results = await _search_web(query, params.get("max_results", 5))
    return {"query": query, "results": results, "count": len(results)}


async def _search_serper(query: str, max_results: int) -> list[dict]:
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            "https://google.serper.dev/search",
            headers={
                "X-API-KEY": settings.serper_api_key,
                "Content-Type": "application/json",
            },
            json={"q": query, "num": max_results},
        )
        resp.raise_for_status()
        data = resp.json()

    results = []
    for item in data.get("organic", [])[:max_results]:
        results.append(
            {
                "title": item.get("title", ""),
                "url": item.get("link", ""),
                "snippet": item.get("snippet", ""),
            }
        )
    return results


async def _search_tavily(query: str, max_results: int) -> list[dict]:
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            "https://api.tavily.com/search",
            json={
                "api_key": settings.tavily_api_key,
                "query": query,
                "max_results": max_results,
            },
        )
        resp.raise_for_status()
        data = resp.json()

    results = []
    for item in data.get("results", [])[:max_results]:
        results.append(
            {
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "snippet": item.get("content", ""),
            }
        )
    return results


async def _search_web(query: str, max_results: int) -> list[dict]:
    if settings.search_provider == "tavily" and settings.tavily_api_key:
        return await _search_tavily(query, max_results)
    if settings.serper_api_key:
        return await _search_serper(query, max_results)
    raise HTTPException(status_code=503, detail="No search API configured")


def _is_private_ip(url: str) -> bool:
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname
        if not hostname:
            return True

        if hostname in {"localhost", "0.0.0.0", "[::1]", "[::]"}:
            return True
        if hostname.endswith(".internal") or hostname.endswith(".local"):
            return True

        try:
            addr_infos = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
        except socket.gaierror:
            return True

        if not addr_infos:
            return True

        for addr_info in addr_infos:
            raw_ip = addr_info[4][0]
            try:
                ip = ipaddress.ip_address(raw_ip)
            except ValueError:
                return True
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved:
                return True
        return False
    except Exception:
        return True


async def _scrape_url(request: ScrapeRequest) -> dict:
    if not re.match(r"^https?://", request.url):
        raise HTTPException(status_code=400, detail="URL must start with http:// or https://")

    if _is_private_ip(request.url):
        raise HTTPException(status_code=400, detail="URL resolves to internal/private IP range")

    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            resp = await client.get(
                request.url,
                headers={"User-Agent": "Fazle-AI/1.0 (Personal Assistant)"},
            )
            resp.raise_for_status()
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch URL: {str(e)}")

    if request.extract_text:
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()

        text = soup.get_text(separator="\n", strip=True)
        text = re.sub(r"\n{3,}", "\n\n", text)
        title = soup.title.string if soup.title else ""
        return {
            "url": request.url,
            "title": title,
            "text": text[:10000],
            "length": len(text),
        }

    return {"url": request.url, "html": resp.text[:50000]}


async def _exec_http_request(params: dict) -> Any:
    url = params.get("url", "")
    if not url:
        return {"error": "No URL provided"}

    # SSRF protection — block private/internal IPs
    from urllib.parse import urlparse
    parsed = urlparse(url)
    blocked_hosts = {"localhost", "127.0.0.1", "0.0.0.0", "169.254.169.254", "metadata.google.internal"}
    if parsed.hostname and (parsed.hostname in blocked_hosts or parsed.hostname.startswith("10.") or parsed.hostname.startswith("192.168.") or parsed.hostname.startswith("172.")):
        return {"error": "Request to internal/private addresses is blocked"}

    method = params.get("method", "GET").upper()
    if method not in ("GET", "POST", "PUT", "DELETE", "PATCH"):
        return {"error": f"Unsupported HTTP method: {method}"}

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.request(
            method,
            url,
            json=params.get("body"),
            headers={"User-Agent": "Fazle-AI/1.0"},
        )
        return {
            "status_code": resp.status_code,
            "body": resp.text[:5000],
            "headers": dict(resp.headers),
        }


async def _exec_memory_search(params: dict) -> Any:
    query = params.get("query", params.get("description", ""))
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            f"{settings.memory_url}/search",
            json={"query": query, "top_k": params.get("top_k", 5)},
        )
        resp.raise_for_status()
        return resp.json()


async def _exec_memory_store(params: dict) -> Any:
    content = params.get("content", params.get("description", ""))
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            f"{settings.memory_url}/store",
            json={"content": content, "type": params.get("type", "tool_result")},
        )
        resp.raise_for_status()
        return {"stored": True}


async def _exec_summarize(params: dict) -> Any:
    text = params.get("text", params.get("description", ""))
    if not text:
        return {"error": "No text to summarize"}
    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.post(
            f"{settings.llm_gateway_url}/llm/generate",
            json={
                "prompt": f"Summarize the following text concisely:\n\n{text[:5000]}",
                "system_prompt": "You are a concise summarizer.",
                "temperature": 0.2,
                "max_tokens": 500,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        return {"summary": data.get("response", data.get("text", ""))}


async def _exec_code_sandbox(params: dict) -> Any:
    """Execute code in restricted subprocess — intentionally limited."""
    if not settings.sandbox_enabled:
        return {"error": "Code sandbox is disabled"}

    code = params.get("code", "")
    if not code:
        return {"error": "No code provided"}

    # Safety: block dangerous operations
    blocked_keywords = ["import os", "import subprocess", "import sys", "__import__", "eval(", "exec(", "open(", "rmtree", "shutil"]
    code_lower = code.lower()
    for kw in blocked_keywords:
        if kw in code_lower:
            return {"error": f"Blocked: code contains restricted operation '{kw}'"}

    try:
        # Execute with timeout in an isolated subprocess
        proc = await asyncio.create_subprocess_exec(
            "python", "-c", code,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        timeout = min(params.get("timeout", 10), settings.max_execution_time)
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return {
            "stdout": stdout.decode()[:5000],
            "stderr": stderr.decode()[:2000],
            "returncode": proc.returncode,
        }
    except asyncio.TimeoutError:
        proc.kill()
        return {"error": "Execution timed out"}
    except Exception as e:
        return {"error": str(e)[:500]}


# Tool executor dispatch
_executors = {
    "web_search": _exec_web_search,
    "http_request": _exec_http_request,
    "memory_search": _exec_memory_search,
    "memory_store": _exec_memory_store,
    "summarize": _exec_summarize,
    "code_sandbox": _exec_code_sandbox,
}


# ── Endpoints ────────────────────────────────────────────────

@app.on_event("startup")
async def startup():
    _register_defaults()
    logger.info(f"Registered {len(_tools)} tools")


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "fazle-web-intelligence+tool-engine",
        "tools_count": len(_tools),
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.post("/search")
async def search(request: SearchRequest):
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    results = await _search_web(request.query, request.max_results)
    return {"query": request.query, "results": results, "count": len(results)}


@app.post("/scrape")
async def scrape(request: ScrapeRequest):
    return await _scrape_url(request)


@app.post("/summarize")
async def summarize(request: SummarizeRequest):
    content = request.text or ""

    if request.url:
        scrape_result = await _scrape_url(ScrapeRequest(url=request.url))
        content = scrape_result.get("text", "")

    if not content:
        raise HTTPException(status_code=400, detail="No content to summarize")

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            await client.post(
                f"{settings.memory_url}/ingest",
                json={
                    "text": content[:5000],
                    "source": request.url or "direct_input",
                    "title": f"Web content from {request.url}" if request.url else "Direct text",
                },
            )
        except Exception as e:
            logger.warning(f"Failed to store in knowledge base: {e}")

    return {
        "content": content[:5000],
        "source": request.url or "direct_input",
        "stored_in_knowledge": True,
    }


@app.post("/tools/execute", response_model=ExecuteToolResponse)
async def execute_tool(req: ExecuteToolRequest):
    """Execute a registered tool with permission checks."""
    tool = _tools.get(req.tool_name)
    if not tool:
        raise HTTPException(status_code=404, detail=f"Tool '{req.tool_name}' not found")

    if not tool.enabled:
        raise HTTPException(status_code=403, detail=f"Tool '{req.tool_name}' is disabled")

    # Check permissions
    perm_attr = _permission_map.get(tool.category)
    if perm_attr and not getattr(settings, perm_attr, True):
        raise HTTPException(status_code=403, detail=f"Tool category '{tool.category}' is not permitted")

    executor = _executors.get(req.tool_name)
    if not executor:
        raise HTTPException(status_code=501, detail=f"No executor for tool '{req.tool_name}'")

    start = datetime.utcnow()
    try:
        result = await asyncio.wait_for(
            executor(req.parameters),
            timeout=req.timeout or settings.max_execution_time,
        )
        elapsed = int((datetime.utcnow() - start).total_seconds() * 1000)

        # Update stats
        tool.usage_count += 1
        tool.last_used = datetime.utcnow().isoformat()

        # Log execution
        _execution_log.append({
            "tool": req.tool_name,
            "user_id": req.user_id,
            "status": "success",
            "time_ms": elapsed,
            "timestamp": datetime.utcnow().isoformat(),
        })

        return ExecuteToolResponse(
            tool_name=req.tool_name,
            status="success",
            result=result,
            execution_time_ms=elapsed,
        )

    except asyncio.TimeoutError:
        elapsed = int((datetime.utcnow() - start).total_seconds() * 1000)
        return ExecuteToolResponse(
            tool_name=req.tool_name,
            status="timeout",
            error="Execution timed out",
            execution_time_ms=elapsed,
        )
    except Exception as e:
        elapsed = int((datetime.utcnow() - start).total_seconds() * 1000)
        logger.error(f"Tool execution failed: {e}")
        return ExecuteToolResponse(
            tool_name=req.tool_name,
            status="error",
            error=str(e)[:500],
            execution_time_ms=elapsed,
        )


@app.get("/tools/list")
async def list_tools():
    """List all registered tools with their status."""
    return {"tools": list(_tools.values()), "total": len(_tools)}


@app.get("/tools/{tool_name}")
async def get_tool(tool_name: str):
    """Get details of a specific tool."""
    tool = _tools.get(tool_name)
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    return tool


@app.put("/tools/{tool_name}/toggle")
async def toggle_tool(tool_name: str):
    """Enable or disable a tool."""
    tool = _tools.get(tool_name)
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    tool.enabled = not tool.enabled
    tool.status = ToolStatus.available if tool.enabled else ToolStatus.disabled
    return {"tool": tool_name, "enabled": tool.enabled}


@app.get("/tools/permissions")
async def get_permissions():
    """Get current tool permission settings."""
    return ToolPermissions(
        web_search=settings.allow_web_search,
        http_request=settings.allow_http_request,
        code_sandbox=settings.allow_code_sandbox,
        db_query=settings.allow_db_query,
        file_access=settings.allow_file_access,
    )


@app.get("/tools/execution-log")
async def get_execution_log(limit: int = 50):
    """Get recent tool execution log."""
    return {"log": _execution_log[-limit:], "total": len(_execution_log)}


# ── Marketplace Endpoints ────────────────────────────────────

@app.get("/marketplace/tools")
async def marketplace_list():
    """List all tools with marketplace metadata."""
    tools_list = []
    for t in _tools.values():
        tools_list.append({
            "id": t.id,
            "name": t.name,
            "category": t.category.value if hasattr(t.category, 'value') else str(t.category),
            "description": t.description,
            "version": "1.0.0",
            "enabled": t.enabled,
            "installed": True,
            "requires_approval": t.requires_approval,
            "status": t.status.value if hasattr(t.status, 'value') else str(t.status),
            "usage_count": t.usage_count,
            "last_used": t.last_used,
        })
    return {"tools": tools_list}


@app.post("/marketplace/tools/install")
async def marketplace_install(body: dict):
    """Install a new tool by name (register in the engine)."""
    tool_name = body.get("tool_name", body.get("name", ""))
    if not tool_name:
        raise HTTPException(status_code=400, detail="tool_name is required")
    if tool_name in _tools:
        return {"status": "already_installed", "tool": tool_name}
    new_tool = ToolDefinition(
        name=tool_name,
        category=ToolCategory(body.get("category", "http_request")),
        description=body.get("description", f"User-installed tool: {tool_name}"),
        enabled=True,
    )
    _tools[tool_name] = new_tool
    return {"status": "installed", "tool": tool_name}


@app.post("/marketplace/tools/{tool_name}/enable")
async def marketplace_enable(tool_name: str):
    """Enable a specific tool."""
    tool = _tools.get(tool_name)
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    tool.enabled = True
    tool.status = ToolStatus.available
    return {"tool": tool_name, "enabled": True}


@app.post("/marketplace/tools/{tool_name}/disable")
async def marketplace_disable(tool_name: str):
    """Disable a specific tool."""
    tool = _tools.get(tool_name)
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    tool.enabled = False
    tool.status = ToolStatus.disabled
    return {"tool": tool_name, "enabled": False}


@app.delete("/marketplace/tools/{tool_name}")
async def marketplace_remove(tool_name: str):
    """Remove/uninstall a tool."""
    if tool_name not in _tools:
        raise HTTPException(status_code=404, detail="Tool not found")
    del _tools[tool_name]
    return {"status": "removed", "tool": tool_name}
