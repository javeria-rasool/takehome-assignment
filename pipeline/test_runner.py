"""
Stage 3 — Test Runner
AI writes Jest/jsdom unit tests, runs them, reads failures, fixes, loops until green.
Final output saved to test-results.txt.
"""
import subprocess
from pathlib import Path

from . import ai_client
from .logger import get_logger

logger = get_logger(__name__)

TOOLS = [
    {
        "name": "write_file",
        "description": "Write a file to the workspace.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
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
        "description": "Run a shell command in the workspace (use to install deps and run tests).",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {"type": "string"},
                "timeout": {"type": "integer", "default": 120},
            },
            "required": ["command"],
        },
    },
]

SYSTEM = """You are a senior QA engineer writing unit tests for a web application.

Your job:
1. Read the built application files (start with index.html or the main JS file).
2. Write meaningful Jest + jsdom unit tests that cover EVERY acceptance criterion.
3. Install dependencies: npm install --save-dev jest jest-environment-jsdom
4. Run the tests. If they fail, read the output, fix the issue, re-run.
5. Repeat until ALL tests pass (0 failures).
6. Save the final jest output verbatim to test-results.txt.

Setup rules:
- Use Jest testEnvironment jsdom.
- For vanilla HTML/JS, load HTML via fs.readFileSync + new JSDOM(html, {runScripts:"dangerously"}).
- Write tests that actually exercise functionality (add/complete/delete items, localStorage reload).
- Do NOT write trivial tests that just check the page loads.
- If package.json doesn't exist, create one:
  {"scripts":{"test":"jest --forceExit"},"devDependencies":{"jest":"^29","jest-environment-jsdom":"^29"},"jest":{"testEnvironment":"jsdom"}}

When all tests pass with 0 failures, write the full jest stdout to test-results.txt and stop.
"""


class TestRunner:
    def __init__(self, workspace_dir: str):
        self.workspace = Path(workspace_dir)

    def _write_file(self, path: str, content: str) -> str:
        full = self.workspace / path
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content, encoding="utf-8")
        return f"Written: {path}"

    def _read_file(self, path: str) -> str:
        full = self.workspace / path
        return full.read_text(encoding="utf-8") if full.exists() else f"ERROR: Not found: {path}"

    def _run_command(self, command: str, timeout: int = 120) -> str:
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

    def _dispatch(self, name: str, inputs: dict) -> str:
        if name == "write_file":
            return self._write_file(inputs["path"], inputs["content"])
        if name == "read_file":
            return self._read_file(inputs["path"])
        if name == "run_command":
            return self._run_command(inputs["command"], inputs.get("timeout", 120))
        return f"Unknown tool: {name}"

    def _list_workspace(self) -> str:
        files = sorted(
            str(p.relative_to(self.workspace))
            for p in self.workspace.rglob("*")
            if p.is_file()
            and ".git" not in p.parts
            and "node_modules" not in p.parts
        )
        return "\n".join(files) if files else "(empty)"

    def run(self, requirements: str) -> dict:
        logger.info("TestRunner starting")

        ai_client.tool_loop(
            system=SYSTEM,
            user_message=(
                f"Write and run unit tests for the web application.\n\n"
                f"## Requirements\n\n{requirements}\n\n"
                f"## Files in workspace\n\n{self._list_workspace()}\n\n"
                "Read the app files, write meaningful tests, run them, "
                "fix any failures, iterate until all pass, "
                "then save the final output to test-results.txt."
            ),
            tools=TOOLS,
            dispatch=self._dispatch,
            max_iterations=20,
        )

        results_path = self.workspace / "test-results.txt"
        if results_path.exists():
            results_text = results_path.read_text(encoding="utf-8")
            lower = results_text.lower()
            has_failures = "failed" in lower and any(
                kw in lower for kw in ["tests failed", "test failed", "failures:", "● "]
            )
            passed = not has_failures
        else:
            results_text = "No test-results.txt generated"
            passed = False

        logger.info(f"Tests {'PASSED' if passed else 'FAILED'}")
        return {"passed": passed, "results": results_text}
