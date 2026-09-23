import re


def normalize_email(email: str) -> str:
    return email.strip().lower()


def normalize_company(company: str) -> str:
    value = company.strip()

    value = re.sub(r"\s+", " ", value)

    return value


def normalize_source(source: str) -> str:
    value = source.strip().lower()

    aliases = {
        "csv": "csv",
        "csv upload": "csv",
        "manual": "manual",
        "manual entry": "manual",
        "api": "api",
        "hubspot": "hubspot",
        "website": "website",
        "web": "website",
    }

    return aliases.get(value, value)


def normalize_status(status: str | None) -> str:
    if not status:
        return "New"

    value = status.strip().lower()

    aliases = {
        "new": "New",
        "qualified": "Qualified",
        "contacted": "Contacted",
        "meeting": "Meeting",
        "won": "Won",
        "lost": "Lost",
    }

    return aliases.get(value, "New")