from sqlalchemy import inspect
from sqlalchemy import text

from backend.database.session import engine


NEW_COLUMNS = {
    "status": "VARCHAR(50) NOT NULL DEFAULT 'New'",
    "notes": "VARCHAR(2000)",
    "last_contacted": "DATETIME",
    "next_follow_up": "DATETIME",
}


def migrate():

    inspector = inspect(engine)

    columns = {
        column["name"]
        for column in inspector.get_columns("leads")
    }

    with engine.begin() as connection:

        for column_name, column_definition in NEW_COLUMNS.items():

            if column_name not in columns:

                print(
                    f"Adding column: {column_name}"
                )

                connection.execute(
                    text(
                        f"""
                        ALTER TABLE leads
                        ADD COLUMN {column_name}
                        {column_definition}
                        """
                    )
                )

    print("Lead lifecycle migration completed.")


if __name__ == "__main__":
    migrate()