import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # Jira
    JIRA_BASE_URL: str = os.getenv("JIRA_BASE_URL", "")
    JIRA_EMAIL: str = os.getenv("JIRA_EMAIL", "")
    JIRA_API_TOKEN: str = os.getenv("JIRA_API_TOKEN", "")
    JIRA_PROJECT_KEY: str = os.getenv("JIRA_PROJECT_KEY", "")

    # AI — set ONE of these (Gemini is free, Anthropic needs billing)
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")

    # GitHub
    GITHUB_TOKEN: str = os.getenv("GITHUB_TOKEN", "")
    GITHUB_REPO: str = os.getenv("GITHUB_REPO", "")  # owner/repo
    GITHUB_DEFAULT_BRANCH: str = os.getenv("GITHUB_DEFAULT_BRANCH", "main")

    # Vercel
    VERCEL_TOKEN: str = os.getenv("VERCEL_TOKEN", "")
    VERCEL_TEAM_ID: str = os.getenv("VERCEL_TEAM_ID", "")

    # Email
    EMAIL_PROVIDER: str = os.getenv("EMAIL_PROVIDER", "smtp")  # smtp | sendgrid | resend
    EMAIL_FROM: str = os.getenv("EMAIL_FROM", "")
    EMAIL_TO: str = os.getenv("EMAIL_TO", "")

    SENDGRID_API_KEY: str = os.getenv("SENDGRID_API_KEY", "")
    RESEND_API_KEY: str = os.getenv("RESEND_API_KEY", "")

    SMTP_HOST: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASS: str = os.getenv("SMTP_PASS", "")

    # Pipeline
    WORKSPACE_DIR: str = os.getenv("WORKSPACE_DIR", "/tmp/pipeline-workspace")
    POLL_INTERVAL_MINUTES: int = int(os.getenv("POLL_INTERVAL_MINUTES", "5"))
