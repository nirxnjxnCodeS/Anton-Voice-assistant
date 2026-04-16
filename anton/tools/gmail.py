"""
Gmail tools — read, search, draft, and send emails via Google OAuth2.
Requires credentials.json in project root (see anton/google_auth.py).
"""

import asyncio
import base64
import re
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from googleapiclient.discovery import build

from anton.google_auth import get_credentials


_EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")


def _valid_email(address: str) -> bool:
    return bool(_EMAIL_RE.match(address.strip()))


def _build_service():
    return build("gmail", "v1", credentials=get_credentials(), cache_discovery=False)


def _decode_header_value(raw: str) -> str:
    """Strip angle-brackets and extra whitespace from email headers."""
    return raw.strip()


def _get_header(headers: list[dict], name: str) -> str:
    for h in headers:
        if h["name"].lower() == name.lower():
            return h["value"]
    return ""


def _snippet_clean(snippet: str) -> str:
    """Remove HTML entities from Gmail snippets."""
    snippet = re.sub(r"&amp;", "&", snippet)
    snippet = re.sub(r"&#39;", "'", snippet)
    snippet = re.sub(r"&quot;", '"', snippet)
    snippet = re.sub(r"&lt;", "<", snippet)
    snippet = re.sub(r"&gt;", ">", snippet)
    return snippet.strip()


def _make_message(to: str, subject: str, body: str) -> dict:
    msg = MIMEMultipart()
    msg["to"] = to
    msg["subject"] = subject
    msg.attach(MIMEText(body, "plain"))
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    return {"raw": raw}


def register(mcp):

    @mcp.tool()
    async def get_unread_emails(max_results: int = 5) -> str:
        """
        Fetch the most recent unread emails from Gmail inbox.
        Returns sender, subject, and a short snippet for each.
        Use when the user asks 'Any new emails?', 'Check my inbox', 'What did I miss?', etc.
        """
        def _fetch():
            service = _build_service()
            list_result = service.users().messages().list(
                userId="me",
                labelIds=["INBOX", "UNREAD"],
                maxResults=max_results,
            ).execute()

            messages = list_result.get("messages", [])
            if not messages:
                return []

            emails = []
            for msg in messages:
                detail = service.users().messages().get(
                    userId="me",
                    id=msg["id"],
                    format="metadata",
                    metadataHeaders=["From", "Subject", "Date"],
                ).execute()
                headers = detail.get("payload", {}).get("headers", [])
                snippet = _snippet_clean(detail.get("snippet", ""))
                emails.append({
                    "from": _get_header(headers, "From"),
                    "subject": _get_header(headers, "Subject"),
                    "snippet": snippet[:120],
                })
            return emails

        try:
            emails = await asyncio.to_thread(_fetch)
        except FileNotFoundError:
            return "Google credentials not found, sir. Please run the OAuth setup first."
        except Exception as e:
            return f"I couldn't reach your inbox, sir. Error: {e}"

        if not emails:
            return "No unread emails, sir. Your inbox is clear."

        count = len(emails)
        lines = [f"{count} unread email{'s' if count != 1 else ''}, sir."]
        for i, email in enumerate(emails):
            sender_name = email["from"].split("<")[0].strip().strip('"') or email["from"]
            lines.append(
                f"\n  {i + 1}. From {sender_name}\n"
                f"     Subject: {email['subject']}\n"
                f"     {email['snippet']}..."
            )

        return "\n".join(lines)

    @mcp.tool()
    async def search_emails(query: str) -> str:
        """
        Search Gmail using standard Gmail search syntax.
        Examples: 'from:boss@company.com', 'subject:invoice', 'is:unread after:2026/04/01'
        Use when the user asks 'Find emails from X', 'Search for invoice emails', etc.
        """
        def _fetch():
            service = _build_service()
            list_result = service.users().messages().list(
                userId="me",
                q=query,
                maxResults=5,
            ).execute()

            messages = list_result.get("messages", [])
            if not messages:
                return []

            emails = []
            for msg in messages:
                detail = service.users().messages().get(
                    userId="me",
                    id=msg["id"],
                    format="metadata",
                    metadataHeaders=["From", "Subject", "Date"],
                ).execute()
                headers = detail.get("payload", {}).get("headers", [])
                snippet = _snippet_clean(detail.get("snippet", ""))
                emails.append({
                    "from": _get_header(headers, "From"),
                    "subject": _get_header(headers, "Subject"),
                    "date": _get_header(headers, "Date"),
                    "snippet": snippet[:120],
                })
            return emails

        try:
            emails = await asyncio.to_thread(_fetch)
        except FileNotFoundError:
            return "Google credentials not found, sir. Please run the OAuth setup first."
        except Exception as e:
            return f"Email search failed, sir. Error: {e}"

        if not emails:
            return f"No emails matched '{query}', sir."

        lines = [f"Found {len(emails)} result(s) for '{query}', sir:\n"]
        for i, email in enumerate(emails):
            sender_name = email["from"].split("<")[0].strip().strip('"') or email["from"]
            lines.append(
                f"  {i + 1}. From {sender_name} — {email['subject']}\n"
                f"     {email['snippet']}..."
            )

        return "\n".join(lines)

    @mcp.tool()
    async def draft_email(to: str, subject: str, body: str) -> str:
        """
        Create an email draft in Gmail. Does NOT send it — saves to Drafts folder only.
        Use when the user says 'Draft an email to X', 'Write a message to Y but don't send it yet', etc.
        """
        if not _valid_email(to):
            return f"That doesn't look like a valid email address, sir: '{to}'."

        def _create_draft():
            service = _build_service()
            message = _make_message(to, subject, body)
            draft = service.users().drafts().create(
                userId="me",
                body={"message": message},
            ).execute()
            return draft["id"]

        try:
            draft_id = await asyncio.to_thread(_create_draft)
        except FileNotFoundError:
            return "Google credentials not found, sir. Please run the OAuth setup first."
        except Exception as e:
            return f"I couldn't create the draft, sir. Error: {e}"

        return (
            f"Draft saved, sir. To: {to} — Subject: '{subject}'. "
            f"It's sitting in your Drafts folder whenever you're ready to send. (Draft ID: {draft_id})"
        )

    @mcp.tool()
    async def send_email(to: str, subject: str, body: str) -> str:
        """
        Send an email immediately via Gmail.
        Use when the user explicitly says 'Send an email to X', 'Email Y about Z', etc.
        WARNING: This sends immediately — prefer draft_email unless the user explicitly confirms sending.
        """
        if not _valid_email(to):
            return f"That doesn't look like a valid email address, sir: '{to}'."

        def _send():
            service = _build_service()
            message = _make_message(to, subject, body)
            sent = service.users().messages().send(
                userId="me",
                body=message,
            ).execute()
            return sent["id"]

        try:
            msg_id = await asyncio.to_thread(_send)
        except FileNotFoundError:
            return "Google credentials not found, sir. Please run the OAuth setup first."
        except Exception as e:
            return f"Failed to send the email, sir. Error: {e}"

        return (
            f"Sent, sir. Email to {to} — '{subject}' — delivered successfully. "
            f"(Message ID: {msg_id})"
        )
