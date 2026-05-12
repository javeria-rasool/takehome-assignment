"""
Stage 6 — QA Agent
Playwright drives real Chromium → takes screenshots of every key interaction
→ AI Vision evaluates each acceptance criterion → bug-report.md produced.
"""
import asyncio
import base64
from datetime import datetime
from pathlib import Path
from typing import List, Tuple

from playwright.async_api import async_playwright, Page

from . import ai_client
from .logger import get_logger

logger = get_logger(__name__)


class QAAgent:
    def __init__(self, workspace_dir: str):
        self.workspace = Path(workspace_dir)

    # ------------------------------------------------------------------
    # Screenshot helper
    # ------------------------------------------------------------------

    async def _shot(self, page: Page, name: str, screenshots: list) -> None:
        path = self.workspace / name
        await page.screenshot(path=str(path), full_page=True)
        screenshots.append(name)
        logger.info(f"Screenshot: {name}")

    # ------------------------------------------------------------------
    # Interaction routines
    # ------------------------------------------------------------------

    async def _interact_todo(self, page: Page, screenshots: list, log: list) -> None:
        n = len(screenshots) + 1
        input_candidates = [
            'input[type="text"]', 'input[placeholder*="todo" i]',
            'input[placeholder*="add" i]', 'input[placeholder*="task" i]',
            "#todo-input", ".todo-input", "#new-todo",
        ]
        inp = None
        for sel in input_candidates:
            try:
                inp = await page.wait_for_selector(sel, timeout=2000)
                if inp:
                    break
            except Exception:
                pass

        if not inp:
            log.append("Could not find text input for todo app")
            return

        for item in ["Buy groceries", "Read a book"]:
            await inp.fill(item)
            await page.keyboard.press("Enter")
            await page.wait_for_timeout(400)
            log.append(f"Added todo: {item}")
            inp = await page.query_selector(input_candidates[0])

        await self._shot(page, f"screenshot-{n:02d}-after-add.png", screenshots)
        n += 1

        for sel in ['input[type="checkbox"]', ".todo-checkbox", ".complete-btn", "li button.check"]:
            items = await page.query_selector_all(sel)
            if items:
                await items[0].click()
                await page.wait_for_timeout(300)
                log.append(f"Marked first item complete ({sel})")
                await self._shot(page, f"screenshot-{n:02d}-marked-complete.png", screenshots)
                n += 1
                break

        for sel in ['button:has-text("Delete")', 'button:has-text("×")',
                    'button:has-text("✕")', 'button:has-text("Remove")',
                    ".delete-btn", 'button[aria-label*="delete" i]']:
            items = await page.query_selector_all(sel)
            if items:
                await items[0].click()
                await page.wait_for_timeout(300)
                log.append(f"Deleted an item ({sel})")
                await self._shot(page, f"screenshot-{n:02d}-after-delete.png", screenshots)
                n += 1
                break

        await page.reload(wait_until="networkidle")
        await page.wait_for_timeout(500)
        log.append("Reloaded page — testing localStorage persistence")
        await self._shot(page, f"screenshot-{n:02d}-after-reload.png", screenshots)

    async def _interact_calculator(self, page: Page, screenshots: list, log: list) -> None:
        n = len(screenshots) + 1
        try:
            for seq in [("1", "+", "2", "="), ("5", "*", "3", "=")]:
                for key in seq:
                    btn = await page.query_selector(f'button:has-text("{key}"), [data-key="{key}"]')
                    if btn:
                        await btn.click()
                        await page.wait_for_timeout(100)
            log.append("Performed basic calculations")
            await self._shot(page, f"screenshot-{n:02d}-calculation.png", screenshots)
        except Exception as exc:
            log.append(f"Calculator interaction error: {exc}")

    async def _interact_generic(self, page: Page, screenshots: list, log: list) -> None:
        n = len(screenshots) + 1
        try:
            buttons = await page.query_selector_all("button, input[type=button], input[type=submit]")
            for btn in buttons[:4]:
                try:
                    await btn.click()
                    await page.wait_for_timeout(200)
                except Exception:
                    pass
            log.append(f"Clicked {min(len(buttons), 4)} interactive elements")
            if buttons:
                await self._shot(page, f"screenshot-{n:02d}-after-interactions.png", screenshots)
        except Exception as exc:
            log.append(f"Generic interaction error: {exc}")

    # ------------------------------------------------------------------
    # Playwright runner
    # ------------------------------------------------------------------

    async def _run_playwright(self, url: str, requirements: str) -> Tuple[List[str], List[str], List[str]]:
        screenshots: List[str] = []
        console_errors: List[str] = []
        log: List[str] = []

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)

            # Desktop
            ctx = await browser.new_context(viewport={"width": 1280, "height": 720})
            page = await ctx.new_page()
            page.on("console", lambda m: (
                console_errors.append(f"{m.type.upper()}: {m.text}")
                if m.type in ("error", "warning") else None
            ))
            page.on("pageerror", lambda e: console_errors.append(f"PAGE_ERROR: {e}"))

            try:
                await page.goto(url, wait_until="networkidle", timeout=30_000)
                log.append(f"Navigated to {url}")
                await self._shot(page, "screenshot-01-initial-load.png", screenshots)

                req_lower = requirements.lower()
                if "todo" in req_lower or "task list" in req_lower:
                    await self._interact_todo(page, screenshots, log)
                elif "calculator" in req_lower or "calc" in req_lower:
                    await self._interact_calculator(page, screenshots, log)
                else:
                    await self._interact_generic(page, screenshots, log)

            except Exception as exc:
                logger.error(f"Playwright desktop error: {exc}")
                log.append(f"Desktop test error: {exc}")
                console_errors.append(f"TEST_ERROR: {exc}")

            await ctx.close()

            # Mobile viewport
            try:
                mctx = await browser.new_context(viewport={"width": 375, "height": 812})
                mpage = await mctx.new_page()
                await mpage.goto(url, wait_until="networkidle", timeout=20_000)
                log.append("Tested mobile viewport 375px")
                await self._shot(mpage, "screenshot-mobile-375px.png", screenshots)
                await mctx.close()
            except Exception as exc:
                log.append(f"Mobile test error: {exc}")

            await browser.close()

        return screenshots, console_errors, log

    # ------------------------------------------------------------------
    # AI Vision evaluation
    # ------------------------------------------------------------------

    def _evaluate(
        self, requirements: str, jira_key: str, url: str,
        screenshots: list, console_errors: list, log: list,
    ) -> str:
        now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

        # Build image content blocks
        image_content = []
        for i, name in enumerate(screenshots):
            path = self.workspace / name
            if not path.exists():
                continue
            data = base64.b64encode(path.read_bytes()).decode()
            image_content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{data}"},
            })
            image_content.append({"type": "text", "text": f"[Screenshot {i + 1}: {name}]"})

        prompt = (
            f"You are a senior QA engineer evaluating a deployed web application.\n\n"
            f"**Jira story:** {jira_key}\n"
            f"**URL:** {url}\n"
            f"**Tested at:** {now}\n\n"
            f"=== REQUIREMENTS ===\n{requirements}\n\n"
            f"=== INTERACTIONS PERFORMED ===\n"
            + "\n".join(f"- {l}" for l in log)
            + f"\n\n=== CONSOLE ERRORS ===\n"
            + ("\n".join(console_errors) if console_errors else "None detected")
            + "\n\nThe screenshots above were taken during testing.\n"
            "Evaluate EVERY acceptance criterion in the requirements.\n\n"
            f"Write a bug report in EXACTLY this format:\n\n"
            f"# QA Report – {jira_key}\n"
            f"**Deployment URL:** {url}\n"
            f"**Tested at:** {now}\n"
            "**Overall status:** PASS / PARTIAL / FAIL\n\n"
            "## Test Results\n"
            "| Acceptance Criterion | Result | Notes |\n"
            "|----------------------|--------|-------|\n"
            "| <criterion> | ✅ PASS or ❌ FAIL | <notes> |\n\n"
            "## Console Errors\n<list or None>\n\n"
            "## Screenshots\n<list filenames>\n\n"
            "## Summary\n<plain English — what works, what doesn't, severity>\n\n"
            "Base every judgement ONLY on what you see in the screenshots. Be honest."
        )

        return ai_client.simple_completion(prompt, vision_content=image_content if image_content else None)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def _parse_status(self, report: str) -> str:
        for line in report.splitlines():
            if "**Overall status:**" in line:
                upper = line.upper()
                if "PARTIAL" in upper:
                    return "PARTIAL"
                if "FAIL" in upper:
                    return "FAIL"
                if "PASS" in upper:
                    return "PASS"
        upper = report.upper()
        if "PARTIAL" in upper:
            return "PARTIAL"
        if "FAIL" in upper:
            return "FAIL"
        return "PASS"

    def run(self, deployment_url: str, requirements: str, jira_key: str) -> dict:
        logger.info(f"[{jira_key}] QA Agent → {deployment_url}")

        screenshots, console_errors, log = asyncio.run(
            self._run_playwright(deployment_url, requirements)
        )
        logger.info(f"Playwright done. {len(screenshots)} screenshots, {len(console_errors)} console errors")

        logger.info("Evaluating with AI Vision…")
        bug_report = self._evaluate(requirements, jira_key, deployment_url, screenshots, console_errors, log)

        (self.workspace / "bug-report.md").write_text(bug_report, encoding="utf-8")
        logger.info("bug-report.md saved")

        overall_status = self._parse_status(bug_report)
        logger.info(f"[{jira_key}] QA status: {overall_status}")

        return {
            "overall_status": overall_status,
            "bug_report": bug_report,
            "screenshots": screenshots,
            "console_errors": console_errors,
        }
