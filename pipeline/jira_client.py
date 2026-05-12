import requests
from .config import Config
from .logger import get_logger

logger = get_logger(__name__)


class JiraClient:
    def __init__(self):
        self.base = Config.JIRA_BASE_URL.rstrip("/")
        self.auth = (Config.JIRA_EMAIL, Config.JIRA_API_TOKEN)
        self.headers = {"Accept": "application/json", "Content-Type": "application/json"}

    # ------------------------------------------------------------------
    # Stage 1: polling
    # ------------------------------------------------------------------

    def get_new_stories(self) -> list:
        jql = (
            f'project = "{Config.JIRA_PROJECT_KEY}" '
            'AND labels = "ai-ready" '
            'AND status = "To Do" '
            'ORDER BY created ASC'
        )
        url = f"{self.base}/rest/api/3/search"
        params = {"jql": jql, "maxResults": 10, "fields": "summary,status,attachment,labels"}
        resp = requests.get(url, params=params, auth=self.auth, headers=self.headers, timeout=30)
        resp.raise_for_status()
        return resp.json().get("issues", [])

    def get_requirements_attachment(self, issue_key: str) -> str | None:
        url = f"{self.base}/rest/api/3/issue/{issue_key}"
        resp = requests.get(url, auth=self.auth, headers=self.headers,
                            params={"fields": "attachment"}, timeout=30)
        resp.raise_for_status()
        attachments = resp.json().get("fields", {}).get("attachment", [])

        for att in attachments:
            if att["filename"] == "requirements.md":
                content_resp = requests.get(att["content"], auth=self.auth, timeout=30)
                content_resp.raise_for_status()
                return content_resp.text

        return None

    # ------------------------------------------------------------------
    # Transitions
    # ------------------------------------------------------------------

    def _available_transitions(self, issue_key: str) -> list:
        url = f"{self.base}/rest/api/3/issue/{issue_key}/transitions"
        resp = requests.get(url, auth=self.auth, headers=self.headers, timeout=30)
        resp.raise_for_status()
        return resp.json().get("transitions", [])

    def transition_issue(self, issue_key: str, target_status: str) -> bool:
        transitions = self._available_transitions(issue_key)
        target_lower = target_status.lower()

        # Exact match first, then partial
        transition_id = None
        for t in transitions:
            if t["name"].lower() == target_lower:
                transition_id = t["id"]
                break
        if not transition_id:
            for t in transitions:
                if target_lower in t["name"].lower():
                    transition_id = t["id"]
                    break

        if not transition_id:
            available = [t["name"] for t in transitions]
            logger.error(f"No transition to '{target_status}' for {issue_key}. Available: {available}")
            return False

        url = f"{self.base}/rest/api/3/issue/{issue_key}/transitions"
        resp = requests.post(url, json={"transition": {"id": transition_id}},
                             auth=self.auth, headers=self.headers, timeout=30)
        resp.raise_for_status()
        logger.info(f"Transitioned {issue_key} → {target_status}")
        return True

    def transition_to_terminal(self, issue_key: str, passed: bool) -> None:
        """Always leave the story in a terminal state, never in-progress."""
        if passed:
            for s in ["Done", "Closed"]:
                if self.transition_issue(issue_key, s):
                    return
        else:
            for s in ["Bug Reported", "In Review", "Done", "Closed"]:
                if self.transition_issue(issue_key, s):
                    return
        logger.warning(f"Could not find any terminal transition for {issue_key}")

    # ------------------------------------------------------------------
    # Comments
    # ------------------------------------------------------------------

    def add_comment(self, issue_key: str, text: str) -> None:
        url = f"{self.base}/rest/api/3/issue/{issue_key}/comment"
        body = {
            "body": {
                "version": 1,
                "type": "doc",
                "content": [
                    {"type": "paragraph", "content": [{"type": "text", "text": text}]}
                ],
            }
        }
        resp = requests.post(url, json=body, auth=self.auth, headers=self.headers, timeout=30)
        resp.raise_for_status()
