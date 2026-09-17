"""Add staged recipe classification without changing planning eligibility."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
revision = "0030"
down_revision = "0029"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("managed_recipe_candidates", sa.Column("classification", JSONB(), nullable=True))
    op.create_check_constraint("ck_recipe_classification_object", "managed_recipe_candidates", "classification IS NULL OR jsonb_typeof(classification) = 'object'")

def downgrade():
    op.drop_constraint("ck_recipe_classification_object", "managed_recipe_candidates", type_="check")
    op.drop_column("managed_recipe_candidates", "classification")
