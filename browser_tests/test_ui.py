import os
import tempfile
from datetime import timedelta
from unittest import skipUnless

from django.contrib.auth.models import User
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
from django.utils import timezone

from chat.models import Message, PrivateChat


@skipUnless(os.environ.get("RUN_BROWSER_TESTS") == "1", "Set RUN_BROWSER_TESTS=1 to run Chromium tests.")
class BrowserTests(StaticLiveServerTestCase):
    def setUp(self):
        from playwright.sync_api import sync_playwright
        self.alice = User.objects.create_user("alice", password="browser-password")
        self.bob = User.objects.create_user("bob", password="browser-password")
        self.chat = PrivateChat.get_or_create_chat(self.alice, self.bob)
        for days, text in [(2, "Earlier conversation"), (1, "Yesterday's message"), (0, "Hello today")]:
            message = Message.objects.create(chat=self.chat, sender=self.bob, receiver=self.alice, content=text)
            Message.objects.filter(pk=message.pk).update(timestamp=timezone.now() - timedelta(days=days))
        self.directory = tempfile.TemporaryDirectory()
        self.settings_override = override_settings(MEDIA_ROOT=self.directory.name)
        self.settings_override.enable()
        import asyncio
        import sys
        if sys.platform == "win32":
            policy = asyncio.get_event_loop_policy()
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
            self.addCleanup(asyncio.set_event_loop_policy, policy)
        self.playwright = sync_playwright().start()
        options = {}
        if os.environ.get("BROWSER_CHANNEL"):
            options["channel"] = os.environ["BROWSER_CHANNEL"]
        if self._testMethodName == "test_voice_record_preview_and_send":
            options["args"] = ["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream"]
        self.browser = self.playwright.chromium.launch(**options)
        self.page = self.browser.new_page()
        self.errors = []
        self.page.on("pageerror", lambda exc: self.errors.append(str(exc)))
        self.page.goto(f"{self.live_server_url}/login/")
        self.page.get_by_label("Username", exact=True).fill("alice")
        self.page.get_by_label("Password", exact=True).fill("browser-password")
        self.page.get_by_role("button", name="Sign in", exact=True).click()
        self.page.wait_for_url(self.live_server_url + "/")
        self.page.goto(f"{self.live_server_url}/chat/{self.bob.profile.public_id}/")

    def tearDown(self):
        self.browser.close()
        self.playwright.stop()
        self.settings_override.disable()
        self.directory.cleanup()

    def test_dates_send_file_theme_and_mobile(self):
        from playwright.sync_api import expect
        page = self.page
        expect(page.locator('.date-divider')).to_have_count(3)
        expect(page.locator('.date-divider').last).to_have_text('Today')
        expect(page.locator('.date-divider').nth(1)).to_have_text('Yesterday')
        page.get_by_role('textbox', name='Message', exact=True).fill('A new message')
        page.get_by_role('button', name='Send message', exact=True).click()
        expect(page.locator('.message-text').last).to_have_text('A new message')
        page.locator('#file-input').set_input_files({'name':'notes.txt', 'mimeType':'text/plain', 'buffer':b'hello from a file'})
        expect(page.locator('#attachment-name')).to_contain_text('notes.txt')
        page.get_by_role('button', name='Send message', exact=True).click()
        expect(page.locator('.file-link').last).to_contain_text('notes.txt')
        original = page.locator('html').get_attribute('data-theme')
        page.locator('#theme-toggle').click()
        expected = 'dark' if original == 'light' else 'light'
        expect(page.locator('html')).to_have_attribute('data-theme', expected)
        incoming = page.locator('.message-row.other .message-bubble').first
        self.assertEqual(incoming.evaluate('(el) => getComputedStyle(el).backgroundColor'), 'rgb(238, 241, 248)' if expected == 'light' else 'rgb(22, 29, 44)')
        page.reload()
        expect(page.locator('html')).to_have_attribute('data-theme', expected)
        if os.environ.get("BROWSER_SCREENSHOT_DIR"):
            from pathlib import Path
            directory = Path(os.environ["BROWSER_SCREENSHOT_DIR"])
            directory.mkdir(parents=True, exist_ok=True)
            page.screenshot(animations="disabled", path=str(directory / "chat-desktop.png"))
            page.locator('#theme-toggle').click()
            page.screenshot(animations="disabled", path=str(directory / "chat-other-theme.png"))
        page.set_viewport_size({'width':390, 'height':844})
        expect(page.get_by_role('textbox', name='Message', exact=True)).to_be_visible()
        self.assertTrue(page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'))
        if os.environ.get("BROWSER_SCREENSHOT_DIR"):
            page.screenshot(animations="disabled", path=os.path.join(os.environ["BROWSER_SCREENSHOT_DIR"], "chat-mobile.png"))
        page.get_by_role('link', name='Back to conversations', exact=True).click()
        expect(page.locator('.sidebar')).to_be_visible()
        self.assertEqual(self.errors, [])

    def test_oversize_file_and_microphone_fallback(self):
        from playwright.sync_api import expect
        self.page.locator('#file-input').set_input_files({'name':'large.bin', 'mimeType':'application/octet-stream', 'buffer':b'x' * (5 * 1024 * 1024 + 1)})
        expect(self.page.locator('#chat-error')).to_contain_text('5 MB')
        self.page.get_by_role('button', name='Record voice message', exact=True).click()
        expect(self.page.locator('#chat-error')).to_be_visible()
        self.assertEqual(self.errors, [])

    def test_mobile_newline_and_send_keeps_composer_focused(self):
        from playwright.sync_api import expect
        context = self.browser.new_context(viewport={"width": 390, "height": 844},
                                           is_mobile=True, has_touch=True)
        try:
            page = context.new_page()
            page.goto(f"{self.live_server_url}/login/")
            page.get_by_label("Username", exact=True).fill("alice")
            page.get_by_label("Password", exact=True).fill("browser-password")
            page.get_by_role("button", name="Sign in", exact=True).click()
            page.goto(f"{self.live_server_url}/chat/{self.bob.profile.public_id}/")
            composer = page.get_by_role("textbox", name="Message", exact=True)
            composer.fill("First line")
            composer.press("Enter")
            composer.type("Second line")
            expect(composer).to_have_value("First line\nSecond line")
            page.get_by_role("button", name="Send message", exact=True).click()
            expect(page.locator(".message-text").last).to_have_text("First line\nSecond line")
            expect(composer).to_be_focused()
            expect(composer).to_have_value("")
        finally:
            context.close()

    def test_voice_record_preview_and_send(self):
        from playwright.sync_api import expect
        page = self.page
        page.get_by_role('button', name='Record voice message', exact=True).click()
        expect(page.locator('#record-status')).to_contain_text('Recording')
        page.wait_for_timeout(1200)
        page.get_by_role('button', name='Stop recording', exact=True).click()
        expect(page.locator('#voice-preview')).to_be_visible()
        page.get_by_role('button', name='Send message', exact=True).click()
        expect(page.locator('.message-bubble audio')).to_have_count(1)
        expect(page.locator('.file-link').last).to_contain_text('Voice message')
        expect(page.locator('#attachment-preview')).to_be_hidden()
        self.assertEqual(self.errors, [])

    def test_edit_profile_photo_and_view_contact(self):
        import io
        from PIL import Image
        from playwright.sync_api import expect
        page = self.page
        page.get_by_role("link", name="My profile", exact=True).click()
        page.wait_for_url("**/people/**/")
        page.get_by_role("link", name="Edit profile", exact=True).click()
        page.get_by_label("First name", exact=True).fill("Alice")
        page.get_by_label("Last name", exact=True).fill("Example")
        page.get_by_label("Phone", exact=True).fill("+989121234567")
        data = io.BytesIO()
        Image.new("RGB", (32, 32), "blue").save(data, "PNG")
        page.locator('#id_avatar').set_input_files({'name':'profile.png', 'mimeType':'image/png', 'buffer':data.getvalue()})
        page.get_by_role('button', name='Save changes', exact=True).click()
        expect(page.locator('.profile-card h2')).to_have_text('Alice Example')
        expect(page.locator('.profile-card img')).to_be_visible()
        expect(page.locator('.profile-details')).to_contain_text('+989121234567')
        page.set_viewport_size({'width':390, 'height':844})
        self.assertTrue(page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'))
        if os.environ.get("BROWSER_SCREENSHOT_DIR"):
            page.screenshot(animations="disabled", path=os.path.join(os.environ["BROWSER_SCREENSHOT_DIR"], "profile-mobile.png"))
        page.get_by_role('link', name='Back to conversations', exact=True).click()
        page.locator('.chat-row').first.click()
        page.get_by_role('link', name='View profile', exact=True).click()
        expect(page.locator('.profile-card h2')).to_have_text('bob')
        expect(page.get_by_role('link', name='Edit profile', exact=True)).to_have_count(0)
        self.assertEqual(self.errors, [])
