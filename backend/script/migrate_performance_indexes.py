from sqlalchemy import inspect, text

from backend.database.session import engine


INDEXES = [
    (
        "ix_leads_org_created",
        """
        CREATE INDEX IF NOT EXISTS
        ix_leads_org_created
        ON leads (organization_id, created_at)
        """,
    ),
    (
        "ix_leads_org_status",
        """
        CREATE INDEX IF NOT EXISTS
        ix_leads_org_status
        ON leads (organization_id, status)
        """,
    ),
    (
        "ix_leads_org_followup",
        """
        CREATE INDEX IF NOT EXISTS
        ix_leads_org_followup
        ON leads (organization_id, next_follow_up)
        """,
    ),
]


def main():
    inspector = inspect(engine)

    if "leads" not in inspector.get_table_names():
        raise RuntimeError(
            "The leads table does not exist."
        )

    with engine.begin() as connection:
        for index_name, statement in INDEXES:
            connection.execute(text(statement))
            print(
                f"Created/verified index: {index_name}"
            )

    print(
        "Performance indexes migration completed."
    )


if __name__ == "__main__":
    main()