"""
Stage 5 — Vercel Deployment
Uses the Vercel REST API (v13) to deploy the workspace as a static site.
Polls until the deployment is READY, then health-checks the live URL.
"""
import time
import urllib.request
import urllib.error
from pathlib import Path

import requests

from .config import Config
from .logger import get_logger

logger = get_logger(__name__)

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".next", ".vercel"}
SKIP_SUFFIXES = {".log", ".pid", ".DS_Store", ".pyc"}


class VercelClient:
    API = "https://api.vercel.com"

    def __init__(self):
        self.token = Config.VERCEL_TOKEN
        self.team_id = Config.VERCEL_TEAM_ID
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    def _params(self) -> dict:
        return {"teamId": self.team_id} if self.team_id else {}

    # ------------------------------------------------------------------
    # File collection
    # ------------------------------------------------------------------

    def _collect_files(self, workspace_dir: str) -> list:
        workspace = Path(workspace_dir)
        files = []

        for path in workspace.rglob("*"):
            if not path.is_file():
                continue
            if any(part in SKIP_DIRS for part in path.parts):
                continue
            if path.suffix in SKIP_SUFFIXES or path.name.startswith("."):
                continue

            relative = str(path.relative_to(workspace))

            try:
                data = path.read_text(encoding="utf-8")
                files.append({"file": relative, "data": data})
            except UnicodeDecodeError:
                # Binary file: encode as base64
                import base64
                data = base64.b64encode(path.read_bytes()).decode()
                files.append({"file": relative, "data": data, "encoding": "base64"})

        return files

    # ------------------------------------------------------------------
    # Deploy
    # ------------------------------------------------------------------

    def deploy(self, workspace_dir: str, project_name: str) -> str:
        """Deploy workspace to Vercel. Returns the live deployment URL."""
        # Ensure vercel.json exists for a clean static deployment
        vercel_json = Path(workspace_dir) / "vercel.json"
        if not vercel_json.exists():
            vercel_json.write_text('{"version": 2}', encoding="utf-8")

        files = self._collect_files(workspace_dir)
        logger.info(f"Deploying {len(files)} files to Vercel project '{project_name}'")

        payload = {
            "name": project_name,
            "files": files,
            "projectSettings": {
                "framework": None,
                "devCommand": None,
                "buildCommand": None,
                "outputDirectory": None,
                "installCommand": None,
                "rootDirectory": None,
            },
        }

        resp = requests.post(
            f"{self.API}/v13/deployments",
            json=payload,
            headers=self.headers,
            params=self._params(),
            timeout=120,
        )
        resp.raise_for_status()
        deployment = resp.json()

        deployment_id = deployment["id"]
        deployment_url = f"https://{deployment['url']}"
        logger.info(f"Deployment created: {deployment_id} → {deployment_url}")

        # Poll until READY
        live_url = self._poll_until_ready(deployment_id, deployment_url)
        return live_url

    def _poll_until_ready(self, deployment_id: str, deployment_url: str, max_wait: int = 300) -> str:
        start = time.time()
        while time.time() - start < max_wait:
            resp = requests.get(
                f"{self.API}/v13/deployments/{deployment_id}",
                headers=self.headers,
                params=self._params(),
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            state = data.get("readyState", data.get("status", ""))
            logger.info(f"Deployment state: {state}")

            if state == "READY":
                logger.info(f"Deployment ready: {deployment_url}")
                return deployment_url
            if state in ("ERROR", "CANCELED"):
                raise RuntimeError(f"Deployment failed with state: {state}")

            time.sleep(10)

        raise TimeoutError(f"Deployment not ready after {max_wait}s")

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------

    def health_check(self, url: str, retries: int = 12, delay: int = 10) -> bool:
        """Verify the live URL returns HTTP 200."""
        for attempt in range(1, retries + 1):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "AI-Pipeline/1.0"})
                with urllib.request.urlopen(req, timeout=15) as response:
                    if response.status == 200:
                        logger.info(f"Health check passed: {url}")
                        return True
            except urllib.error.HTTPError as exc:
                logger.debug(f"Health check attempt {attempt}: HTTP {exc.code}")
            except Exception as exc:
                logger.debug(f"Health check attempt {attempt}: {exc}")

            if attempt < retries:
                time.sleep(delay)

        raise RuntimeError(f"Health check failed after {retries} attempts: {url}")
