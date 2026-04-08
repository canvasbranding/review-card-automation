"""HubSpot contact matching for review card automation."""

import logging

import requests

import config

logger = logging.getLogger(__name__)

SEARCH_URL = "https://api.hubapi.com/crm/v3/objects/contacts/search"
CONTACT_PROPERTIES = [
    "firstname",
    "lastname",
    "address",
    "city",
    "state",
    "zip",
    "email",
    "phone",
]


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {config.HUBSPOT_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }


def _search_contacts(filters: list[dict]) -> list[dict]:
    """Search HubSpot contacts with given filters."""
    payload = {
        "filterGroups": [{"filters": filters}],
        "properties": CONTACT_PROPERTIES,
        "limit": 10,
    }
    try:
        resp = requests.post(
            SEARCH_URL, headers=_headers(), json=payload, timeout=15
        )
        resp.raise_for_status()
        return resp.json().get("results", [])
    except requests.exceptions.RequestException:
        logger.exception("HubSpot search failed")
        return []


def _get_company_address(contact_id: str) -> dict | None:
    """Check associated company for address if contact has none."""
    assoc_url = (
        f"https://api.hubapi.com/crm/v3/objects/contacts/{contact_id}"
        f"/associations/companies"
    )
    try:
        resp = requests.get(assoc_url, headers=_headers(), timeout=15)
        resp.raise_for_status()
        results = resp.json().get("results", [])
        if not results:
            return None

        company_id = results[0]["id"]
        company_url = (
            f"https://api.hubapi.com/crm/v3/objects/companies/{company_id}"
        )
        resp = requests.get(
            company_url,
            headers=_headers(),
            params={"properties": "address,city,state,zip"},
            timeout=15,
        )
        resp.raise_for_status()
        props = resp.json().get("properties", {})
        if props.get("address") and props.get("city") and props.get("state"):
            return {
                "street": props["address"],
                "city": props["city"],
                "state": props["state"],
                "zip": props.get("zip", ""),
            }
    except requests.exceptions.RequestException:
        logger.exception("Failed to fetch company address for contact %s", contact_id)
    return None


def _extract_address(contact: dict) -> dict | None:
    """Extract mailing address from a HubSpot contact, falling back to company."""
    props = contact.get("properties", {})
    if props.get("address") and props.get("city") and props.get("state"):
        return {
            "street": props["address"],
            "city": props["city"],
            "state": props["state"],
            "zip": props.get("zip", ""),
        }
    # Fall back to associated company
    return _get_company_address(contact["id"])


def _has_valid_address(contact: dict) -> bool:
    return _extract_address(contact) is not None


def _parse_name(display_name: str) -> tuple[str, str]:
    """Parse a display name into (first, last).

    Handles cases like "John S." where last name is abbreviated.
    """
    parts = display_name.strip().split()
    if len(parts) == 0:
        return ("", "")
    if len(parts) == 1:
        return (parts[0], "")
    first = parts[0]
    last = " ".join(parts[1:])
    return (first, last)


def match_contact(reviewer_name: str) -> dict | None:
    """Try to match a reviewer name to a HubSpot contact.

    Returns dict with keys: contact_id, address (or None), firstname, lastname
    or None if no match found.
    """
    first, last = _parse_name(reviewer_name)
    if not first:
        logger.warning("Could not parse reviewer name: %s", reviewer_name)
        return None

    # Try exact match first
    if last:
        # Check if last name looks abbreviated (e.g. "S." or "S")
        clean_last = last.rstrip(".")
        if len(clean_last) <= 1:
            # Abbreviated last name — search by first name + last initial
            filters = [
                {
                    "propertyName": "firstname",
                    "operator": "EQ",
                    "value": first,
                },
                {
                    "propertyName": "lastname",
                    "operator": "CONTAINS_TOKEN",
                    "value": f"{clean_last}*",
                },
            ]
        else:
            filters = [
                {
                    "propertyName": "firstname",
                    "operator": "EQ",
                    "value": first,
                },
                {
                    "propertyName": "lastname",
                    "operator": "EQ",
                    "value": last,
                },
            ]
    else:
        # Only first name available
        filters = [
            {
                "propertyName": "firstname",
                "operator": "EQ",
                "value": first,
            }
        ]

    results = _search_contacts(filters)

    if not results:
        logger.info("No HubSpot match for '%s'", reviewer_name)
        return None

    # If multiple matches, prefer the one with a valid address
    best = None
    for contact in results:
        if _has_valid_address(contact):
            best = contact
            break
    if best is None:
        best = results[0]

    address = _extract_address(best)
    props = best.get("properties", {})

    return {
        "contact_id": best["id"],
        "firstname": props.get("firstname", ""),
        "lastname": props.get("lastname", ""),
        "address": address,
    }
