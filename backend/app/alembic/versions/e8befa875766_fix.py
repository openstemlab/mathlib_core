"""fix

Revision ID: e8befa875766
Revises: beda2048ad39
Create Date: 2025-12-29 20:00:49.417118

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision = 'e8befa875766'
down_revision = 'beda2048ad39'
branch_labels = None
depends_on = None


def upgrade():
    op.create_index(
    'idx_active_quiz_per_user',
    'quiz',
    ['owner_id'],
    unique=True,
    postgresql_where=sa.sql.text("status = 'active'")
    )
    # ### end Alembic commands ###


def downgrade():
    op.drop_index('idx_active_quiz_per_user', table_name='quiz')
    pass
    # ### end Alembic commands ###
