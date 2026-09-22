from sqlalchemy import inspect, text

from backend.database.session import engine


ORGANIZATION_ID = 1


def main():
    inspector = inspect(engine)

    tables = inspector.get_table_names()

    print("Existing tables:", tables)

    if "leads" not in tables:
        raise RuntimeError("The leads table does not exist.")

    if "lead_analysis" not in tables:
        raise RuntimeError("The lead_analysis table does not exist.")

    print("Starting multitenancy migration...")

    # ---------------------------------------------------------
    # 1. Create organizations table
    # ---------------------------------------------------------

    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS organizations (
                    id INTEGER PRIMARY KEY,
                    name VARCHAR(200) NOT NULL,
                    slug VARCHAR(100) NOT NULL UNIQUE,
                    plan VARCHAR(50) NOT NULL DEFAULT 'standard',
                    monthly_lead_limit INTEGER NOT NULL DEFAULT 500,
                    is_active BOOLEAN NOT NULL DEFAULT 1,
                    created_at DATETIME NOT NULL
                )
                """
            )
        )

    print("Verified organizations table.")

    # ---------------------------------------------------------
    # 2. Add organization_id to leads
    # ---------------------------------------------------------

    inspector = inspect(engine)

    lead_columns = [
        column["name"]
        for column in inspector.get_columns("leads")
    ]

    if "organization_id" not in lead_columns:
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    ALTER TABLE leads
                    ADD COLUMN organization_id INTEGER
                    """
                )
            )

        print("Added organization_id to leads.")
    else:
        print("organization_id already exists on leads.")

    # ---------------------------------------------------------
    # 3. Add organization_id to lead_analysis
    # ---------------------------------------------------------

    inspector = inspect(engine)

    analysis_columns = [
        column["name"]
        for column in inspector.get_columns("lead_analysis")
    ]

    if "organization_id" not in analysis_columns:
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    ALTER TABLE lead_analysis
                    ADD COLUMN organization_id INTEGER
                    """
                )
            )

        print("Added organization_id to lead_analysis.")
    else:
        print("organization_id already exists on lead_analysis.")

    # ---------------------------------------------------------
    # 4. Create default organization
    # ---------------------------------------------------------

    with engine.begin() as connection:

        existing = connection.execute(
            text(
                """
                SELECT id
                FROM organizations
                WHERE slug = 'leadforge-dev'
                """
            )
        ).fetchone()

        if existing is None:

            connection.execute(
                text(
                    """
                    INSERT INTO organizations (
                        id,
                        name,
                        slug,
                        plan,
                        monthly_lead_limit,
                        is_active,
                        created_at
                    )
                    VALUES (
                        1,
                        'LeadForge Development',
                        'leadforge-dev',
                        'standard',
                        500,
                        1,
                        CURRENT_TIMESTAMP
                    )
                    """
                )
            )

            print("Created default organization.")

        else:
            print("Default organization already exists.")

    # ---------------------------------------------------------
    # 5. Assign existing records
    # ---------------------------------------------------------

    with engine.begin() as connection:

        connection.execute(
            text(
                """
                UPDATE leads
                SET organization_id = :organization_id
                WHERE organization_id IS NULL
                """
            ),
            {
                "organization_id": ORGANIZATION_ID
            }
        )

        connection.execute(
            text(
                """
                UPDATE lead_analysis
                SET organization_id = :organization_id
                WHERE organization_id IS NULL
                """
            ),
            {
                "organization_id": ORGANIZATION_ID
            }
        )

    print("Assigned existing records to default organization.")

    # ---------------------------------------------------------
    # 6. Create indexes
    # ---------------------------------------------------------

    with engine.begin() as connection:

        connection.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS
                ix_leads_organization_id
                ON leads (organization_id)
                """
            )
        )

        connection.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS
                ix_lead_analysis_organization_id
                ON lead_analysis (organization_id)
                """
            )
        )

    print("Created organization indexes.")

    print("Multitenancy migration completed successfully.")


if __name__ == "__main__":
    main()