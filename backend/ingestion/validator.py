import re


class LeadValidator:

    EMAIL_PATTERN = re.compile(
        r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"
    )

    def validate(self, lead: dict) -> tuple[bool, list[str]]:
        """
        Validate a lead record.

        Returns:
            (is_valid, errors)
        """

        errors = []

        company = lead.get("company", "").strip()
        email = lead.get("email", "").strip()
        source = lead.get("source", "").strip()

        if not company:
            errors.append("Company is required.")

        if not email:
            errors.append("Email is required.")

        elif not self.EMAIL_PATTERN.match(email):
            errors.append("Invalid email format.")

        if not source:
            errors.append("Source is required.")

        return len(errors) == 0, errors