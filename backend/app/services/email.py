"""Resend email delivery with simple branded HTML templates."""

from __future__ import annotations

import html

import resend


def _layout(company: str, title: str, body_html: str) -> str:
    return f"""<!doctype html>
<html><body style="margin:0;background:#f4f5f7;font-family:Segoe UI,Helvetica,Arial,sans-serif;color:#1f2937">
  <table width="100%" cellpadding="0" cellspacing="0" style="padding:24px 0"><tr><td align="center">
    <table width="560" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:12px;overflow:hidden">
      <tr><td style="background:#0f766e;color:#ffffff;padding:20px 28px;font-size:18px;font-weight:600">
        {html.escape(company)}
      </td></tr>
      <tr><td style="padding:28px">
        <h2 style="margin:0 0 16px;font-size:20px">{html.escape(title)}</h2>
        {body_html}
      </td></tr>
      <tr><td style="padding:16px 28px;background:#f9fafb;color:#6b7280;font-size:12px">
        Sent automatically by PropPulse AI on behalf of {html.escape(company)}.
      </td></tr>
    </table>
  </td></tr></table>
</body></html>"""


def paragraphs(text: str) -> str:
    """Convert plain text (blank-line separated) into escaped HTML paragraphs."""
    blocks = [b.strip() for b in text.split("\n\n") if b.strip()]
    return "".join(
        f'<p style="margin:0 0 14px;line-height:1.55">{html.escape(b).replace(chr(10), "<br>")}</p>' for b in blocks
    )


def details_table(rows: list[tuple[str, str]]) -> str:
    cells = "".join(
        f'<tr><td style="padding:8px 12px;color:#6b7280;border-bottom:1px solid #eef0f3">{html.escape(k)}</td>'
        f'<td style="padding:8px 12px;font-weight:600;border-bottom:1px solid #eef0f3">{html.escape(v)}</td></tr>'
        for k, v in rows
    )
    return f'<table cellpadding="0" cellspacing="0" style="width:100%;border:1px solid #eef0f3;border-radius:8px;margin:8px 0 18px">{cells}</table>'


class Mailer:
    def __init__(self, api_key: str, sender: str, company: str):
        resend.api_key = api_key
        self.sender = sender
        self.company = company

    def send(self, to: str, subject: str, title: str, body_html: str) -> str:
        result = resend.Emails.send(
            {"from": self.sender, "to": [to], "subject": subject, "html": _layout(self.company, title, body_html)}
        )
        return result.get("id", "") if isinstance(result, dict) else getattr(result, "id", "")
