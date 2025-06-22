"""seed_fixed_content_data

Revision ID: 2d005eaae830
Revises: fc20b3c2d530
Create Date: 2025-06-22 09:36:13.645089

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2d005eaae830'
down_revision: Union[str, None] = 'fc20b3c2d530'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
