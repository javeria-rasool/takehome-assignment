"""
Stage 2 — Build Agent
Reads requirements.md and runs an agentic tool-use loop (via ai_client)
to produce a deployable web application in the workspace directory.
"""
import subprocess
from pathlib import Path

from . import ai_client
from .logger import get_logger

logger = get_logger(__name__)

TOOLS = [
    {
        "name": "write_file",
        "description": "Write (or overwrite) a file inside the workspace. Creates parent dirs automatically.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative path inside the workspace"},
                "content": {"type": "string", "description": "Full file content"},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "read_file",
        "description": "Read a file from the workspace.",
        "parameters": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    },
    {
        "name": "run_command",
        "description": "Run a shell command in the workspace directory and return stdout+stderr.",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {"type": "string"},
                "timeout": {"type": "integer", "default": 60},
            },
            "required": ["command"],
        },
    },
    {
        "name": "list_files",
        "description": "List all files currently in the workspace (recursive).",
        "parameters": {
            "type": "object",
            "properties": {
                "directory": {"type": "string", "default": "."},
            },
        },
    },
]

SYSTEM = """You are a senior web developer building a complete, production-ready web application.

Rules you MUST follow:
1. Read the full requirements before writing a single line of code.
2. Build EVERY feature described — do not skip or simplify.
3. Output must be a static site deployable to Vercel with zero configuration.
   - For plain HTML/CSS/JS: produce index.html (+ separate CSS/JS if helpful).
   - If a framework is required: create a proper project structure with package.json.
4. Do NOT ask for clarification. Make reasonable decisions and ship.
5. Prefer embedding CSS and JS directly in index.html for simplicity.
6. Use only CDN-hosted external libraries (no npm build step) unless a framework is explicitly required.
7. Always create a vercel.json containing exactly: {"version": 2}
8. When you are done, call list_files to confirm all files are present, then stop.
"""


class BuildAgent:
    def __init__(self, workspace_dir: str):
        self.workspace = Path(workspace_dir)
        self.workspace.mkdir(parents=True, exist_ok=True)

    def _write_file(self, path: str, content: str) -> str:
        full = self.workspace / path
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content, encoding="utf-8")
        return f"Written: {path} ({len(content)} chars)"

    def _read_file(self, path: str) -> str:
        full = self.workspace / path
        return full.read_text(encoding="utf-8") if full.exists() else f"ERROR: Not found: {path}"

    def _run_command(self, command: str, timeout: int = 60) -> str:
        try:
            r = subprocess.run(
                command, shell=True, cwd=self.workspace,
                capture_output=True, text=True, timeout=timeout,
            )
            return f"STDOUT:\n{r.stdout}\nSTDERR:\n{r.stderr}\nEXIT: {r.returncode}"
        except subprocess.TimeoutExpired:
            return f"ERROR: Timed out after {timeout}s"
        except Exception as exc:
            return f"ERROR: {exc}"

    def _list_files(self, directory: str = ".") -> str:
        base = self.workspace / directory
        if not base.exists():
            return "Directory not found"
        files = sorted(
            str(p.relative_to(self.workspace))
            for p in base.rglob("*")
            if p.is_file() and ".git" not in p.parts
        )
        return "\n".join(files) if files else "(empty)"

    def _dispatch(self, name: str, inputs: dict) -> str:
        if name == "write_file":
            return self._write_file(inputs["path"], inputs["content"])
        if name == "read_file":
            return self._read_file(inputs["path"])
        if name == "run_command":
            return self._run_command(inputs["command"], inputs.get("timeout", 60))
        if name == "list_files":
            return self._list_files(inputs.get("directory", "."))
        return f"Unknown tool: {name}"

    def build(self, requirements: str, jira_key: str) -> str:
        logger.info(f"[{jira_key}] BuildAgent starting")

        ai_client.tool_loop(
            system=SYSTEM,
            user_message=(
                f"Build a web application for Jira story **{jira_key}**.\n\n"
                f"## Requirements\n\n{requirements}\n\n"
                "Build the complete application now. Write all files to the workspace."
            ),
            tools=TOOLS,
            dispatch=self._dispatch,
            max_iterations=30,
        )

        files = self._list_files()
        logger.info(f"[{jira_key}] Build complete. Files:\n{files}")
        return files
