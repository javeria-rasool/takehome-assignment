"""
Pipeline Orchestrator
Runs a cron-style poll every N minutes, picks up Jira stories labelled 'ai-ready',
and drives them through all 8 pipeline stages end-to-end.

Usage:
    python -m pipeline.main
"""
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

import schedule

from .config import Config
from .email_client import EmailClient
from .github_client import GitHubClient
from .jira_client import JiraClient
from .logger import get_logger
from .build_agent import BuildAgent
from .qa_agent import QAAgent
from .test_runner import TestRunner
from .vercel_client import VercelClient

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Single-story processor
# ---------------------------------------------------------------------------

def _process_story(issue: dict, requirements: str) -> None:
    jira_key: str = issue["key"]
    summary: str = issue["fields"]["summary"]

    logger.info("=" * 65)
    logger.info(f"  Processing {jira_key}: {summary}")
    logger.info("=" * 65)

    jira = JiraClient()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    workspace = Path(Config.WORKSPACE_DIR) / f"{jira_key}_{timestamp}"
    workspace.mkdir(parents=True, exist_ok=True)

    ws = str(workspace)
    qa_results: dict = {}
    gh_result: dict = {}
    deployment_url: str = ""

    try:
        # ----------------------------------------------------------------
        # Stage 2 — Build
        # ----------------------------------------------------------------
        logger.info(f"[{jira_key}] ► Stage 2: Build")
        BuildAgent(ws).build(requirements, jira_key)
        jira.add_comment(jira_key, "✅ Stage 2: Web app built successfully.")

        # ----------------------------------------------------------------
        # Stage 3 — Unit Tests
        # ----------------------------------------------------------------
        logger.info(f"[{jira_key}] ► Stage 3: Unit Tests")
        test_result = TestRunner(ws).run(requirements)
        icon = "✅" if test_result["passed"] else "⚠️"
        status_word = "PASSED" if test_result["passed"] else "had failures (see log)"
        jira.add_comment(
            jira_key,
            f"{icon} Stage 3: Tests {status_word}.\n\n"
            f"```\n{test_result['results'][:1500]}\n```",
        )

        # ----------------------------------------------------------------
        # Stage 4 — Push to GitHub
        # ----------------------------------------------------------------
        logger.info(f"[{jira_key}] ► Stage 4: Push to GitHub")
        gh_result = GitHubClient().push_and_create_pr(ws, jira_key, summary, requirements)
        jira.add_comment(jira_key, f"✅ Stage 4: PR opened → {gh_result['pr_url']}")

        # ----------------------------------------------------------------
        # Stage 5 — Deploy to Vercel
        # ----------------------------------------------------------------
        logger.info(f"[{jira_key}] ► Stage 5: Deploy to Vercel")
        project_name = f"pipeline-{jira_key.lower().replace('_', '-')}"
        vercel = VercelClient()
        deployment_url = vercel.deploy(ws, project_name)
        vercel.health_check(deployment_url)
        jira.add_comment(jira_key, f"✅ Stage 5: Deployed → {deployment_url}")

        # ----------------------------------------------------------------
        # Stage 6 — QA via Playwright
        # ----------------------------------------------------------------
        logger.info(f"[{jira_key}] ► Stage 6: QA")
        qa_results = QAAgent(ws).run(deployment_url, requirements, jira_key)

        # ----------------------------------------------------------------
        # Stage 7 — Email report
        # ----------------------------------------------------------------
        logger.info(f"[{jira_key}] ► Stage 7: Email report")
        EmailClient().send_report(
            jira_key,
            qa_results["overall_status"],
            qa_results["bug_report"],
            qa_results["screenshots"],
            ws,
        )
        jira.add_comment(
            jira_key,
            f"✅ Stage 7: QA report emailed to {Config.EMAIL_TO}",
        )

        # ----------------------------------------------------------------
        # Stage 8 — Close Jira loop
        # ----------------------------------------------------------------
        logger.info(f"[{jira_key}] ► Stage 8: Close Jira loop")
        passed = qa_results["overall_status"] == "PASS"
        jira.add_comment(
            jira_key,
            (
                f"{'✅ ALL TESTS PASSED' if passed else '❌ TESTS FAILED / PARTIAL'}\n\n"
                f"Deployment: {deployment_url}\n"
                f"PR: {gh_result.get('pr_url', 'N/A')}\n\n"
                f"{qa_results['bug_report'][:3000]}"
            ),
        )
        jira.transition_to_terminal(jira_key, passed)

        logger.info(f"[{jira_key}] Pipeline complete — {qa_results['overall_status']}")

    except Exception:
        err = traceback.format_exc()
        logger.error(f"[{jira_key}] PIPELINE ERROR:\n{err}")

        try:
            jira.add_comment(
                jira_key,
                f"❌ Pipeline error at stage — check logs.\n\n```\n{err[-1500:]}\n```",
            )
        except Exception:
            pass

        # Always leave the story in a terminal state
        try:
            jira.transition_to_terminal(jira_key, passed=False)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Polling function
# ---------------------------------------------------------------------------

def poll_and_process() -> None:
    logger.info(f"Polling Jira for new stories (project={Config.JIRA_PROJECT_KEY})…")
    try:
        jira = JiraClient()
        issues = jira.get_new_stories()
    except Exception:
        logger.error(f"Jira poll failed:\n{traceback.format_exc()}")
        return

    if not issues:
        logger.info("No new stories found.")
        return

    logger.info(f"Found {len(issues)} story/stories to process.")
    for issue in issues:
        jira_key = issue["key"]
        try:
            requirements = jira.get_requirements_attachment(jira_key)
        except Exception:
            logger.error(f"[{jira_key}] Failed to fetch attachment: {traceback.format_exc()}")
            continue

        if not requirements:
            logger.warning(f"[{jira_key}] No requirements.md found — skipping.")
            jira.add_comment(
                jira_key,
                "⚠️ No requirements.md attachment found. "
                "Please attach a file named exactly 'requirements.md'.",
            )
            continue

        # Transition immediately so the next cron tick doesn't re-pick it
        try:
            jira.transition_issue(jira_key, "In Progress")
            jira.add_comment(jira_key, "🚀 AI Pipeline picked up this story — processing started.")
        except Exception:
            logger.warning(f"[{jira_key}] Could not transition to In Progress: {traceback.format_exc()}")

        _process_story(issue, requirements)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def _validate_config() -> None:
    required = [
        ("JIRA_BASE_URL", Config.JIRA_BASE_URL),
        ("JIRA_EMAIL", Config.JIRA_EMAIL),
        ("JIRA_API_TOKEN", Config.JIRA_API_TOKEN),
        ("JIRA_PROJECT_KEY", Config.JIRA_PROJECT_KEY),
        # At least one AI key must be set
        ("GITHUB_TOKEN", Config.GITHUB_TOKEN),
        ("GITHUB_REPO", Config.GITHUB_REPO),
        ("VERCEL_TOKEN", Config.VERCEL_TOKEN),
        ("EMAIL_FROM", Config.EMAIL_FROM),
        ("EMAIL_TO", Config.EMAIL_TO),
    ]
    missing = [k for k, v in required if not v]
    if missing:
        logger.error(f"Missing required config: {', '.join(missing)}")
        logger.error("Copy .env.example → .env and fill in all values.")
        sys.exit(1)

    if not Config.ANTHROPIC_API_KEY and not Config.GEMINI_API_KEY:
        logger.error("Set at least one AI key: ANTHROPIC_API_KEY or GEMINI_API_KEY")
        sys.exit(1)

    # Email-provider-specific check
    provider = Config.EMAIL_PROVIDER.lower()
    if provider == "sendgrid" and not Config.SENDGRID_API_KEY:
        logger.error("EMAIL_PROVIDER=sendgrid but SENDGRID_API_KEY is empty")
        sys.exit(1)
    if provider == "resend" and not Config.RESEND_API_KEY:
        logger.error("EMAIL_PROVIDER=resend but RESEND_API_KEY is empty")
        sys.exit(1)
    if provider == "smtp" and not (Config.SMTP_HOST and Config.SMTP_USER and Config.SMTP_PASS):
        logger.error("EMAIL_PROVIDER=smtp but SMTP_HOST/SMTP_USER/SMTP_PASS are incomplete")
        sys.exit(1)


def main() -> None:
    logger.info("━" * 65)
    logger.info("  AI Pipeline starting")
    logger.info(f"  Poll interval : {Config.POLL_INTERVAL_MINUTES} minutes")
    logger.info(f"  Workspace     : {Config.WORKSPACE_DIR}")
    logger.info(f"  Jira project  : {Config.JIRA_PROJECT_KEY}")
    logger.info(f"  GitHub repo   : {Config.GITHUB_REPO}")
    logger.info("━" * 65)

    _validate_config()
    Path(Config.WORKSPACE_DIR).mkdir(parents=True, exist_ok=True)

    # Run once immediately on startup
    poll_and_process()

    # Then on a schedule
    schedule.every(Config.POLL_INTERVAL_MINUTES).minutes.do(poll_and_process)
    logger.info(f"Scheduler running — next poll in {Config.POLL_INTERVAL_MINUTES} minutes")

    while True:
        schedule.run_pending()
        time.sleep(1)


if __name__ == "__main__":
    main()
