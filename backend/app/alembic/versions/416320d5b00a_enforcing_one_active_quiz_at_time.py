"""enforcing_one_active_quiz_at_time

Revision ID: 416320d5b00a
Revises: b761b73e6061
Create Date: 2025-11-26 10:29:20.272771

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision = '416320d5b00a'
down_revision = 'b761b73e6061'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "idx_unique_active_quiz_per_user",
        "quiz",
        ["owner_id"],
        unique=True,
        postgresql_where="status = 'active'"
    )

def downgrade() -> None:
    op.drop_index("idx_unique_active_quiz_per_user", table_name="quiz")
