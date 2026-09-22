"""Create compact, model-safe observations from visible page content."""

from datetime import UTC, datetime
from typing import Any

from playwright.async_api import Page

from web_gui_agent.domain.observation import ElementCandidate, Observation, PageSignals, Viewport


class ObservationBuilder:
    async def build(self, page: Page) -> Observation:
        payload: dict[str, Any] = await page.locator("body").evaluate(
            """body => {
                const visible = el => {
                    const style = getComputedStyle(el);
                    const rect = el.getBoundingClientRect();
                    return style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0;
                };
                const kindFor = el => el.tagName.toLowerCase() === 'a' ? 'link' : el.tagName.toLowerCase() === 'button' ? 'button' : el.tagName.toLowerCase();
                const elements = [...body.querySelectorAll('a,button,input,select,textarea')]
                    .filter(el => visible(el) && !el.disabled)
                    .map((el, index) => {
                        const id = el.dataset.testid || `element-${index}`;
                        const hints = el.dataset.testid ? [{strategy: 'test_id', value: el.dataset.testid}] : [];
                        if (el.labels && el.labels[0]) hints.push({strategy: 'label', value: el.labels[0].innerText.trim()});
                        if (el.getAttribute('role')) hints.push({strategy: 'role', value: el.getAttribute('role')});
                        const text = (el.innerText || el.value || el.getAttribute('aria-label') || '').trim();
                        if (text) hints.push({strategy: 'text', value: text});
                        const isSecret = el instanceof HTMLInputElement && el.type === 'password';
                        return {element_id: id, role: el.getAttribute('role'), name: text || null, kind: kindFor(el), visible: true, enabled: true, value: isSecret ? null : (el.value || null), locator_hints: hints};
                    });
                const hasError = Boolean(body.querySelector('[role="alert"], .error, .alert-error, [data-error="true"]'));
                return {elements, text: body.innerText, viewport: {width: innerWidth, height: innerHeight, scroll_y: scrollY}, signals: {has_error: hasError}};
            }"""
        )
        return Observation(
            url=page.url,
            title=await page.title(),
            viewport=Viewport.model_validate(payload["viewport"]),
            elements=[ElementCandidate.model_validate(element) for element in payload["elements"]],
            text_summary=str(payload["text"]),
            page_signals=PageSignals.model_validate(payload.get("signals", {})),
            captured_at=datetime.now(UTC),
        )
