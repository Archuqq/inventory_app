"""Add status column to purchase_plan

Revision ID: 9fbb028b1cb6
Revises: 247d93a55ae4
Create Date: 2025-01-11 01:50:36.544642

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9fbb028b1cb6'
down_revision = '247d93a55ae4'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('purchase_plan', schema=None) as batch_op:
        batch_op.add_column(sa.Column('status', sa.String(length=50), nullable=True))

    with op.batch_alter_table('replacement_request', schema=None) as batch_op:
        batch_op.alter_column('quantity',
               existing_type=sa.INTEGER(),
               nullable=True)

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('replacement_request', schema=None) as batch_op:
        batch_op.alter_column('quantity',
               existing_type=sa.INTEGER(),
               nullable=False)

    with op.batch_alter_table('purchase_plan', schema=None) as batch_op:
        batch_op.drop_column('status')

    # ### end Alembic commands ###
