"""Phase 2L — add example_scenarios to each line item in case_files.line_items.

DEVIATION FROM THE PHASE PROMPT: the prompt assumed line items live in their own
table and said "ALTER TABLE ... ADD COLUMN example_scenarios JSONB". In this
codebase line_items is a JSONB array on case_files (see 0003), so there is no
column to add — example_scenarios is a nested field inside each line-item
object. This migration is therefore a JSONB backfill: it ensures every existing
line-item object carries an example_scenarios key (default []) so pre-2L rows
stay shape-compatible. The runtime fills the actual content on read
(app/agents/example_scenarios.backfill_scenarios). Idempotent.

Revision ID: 0006
Revises:     0005
"""

from __future__ import annotations

from alembic import op

# Alembic identifiers
revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE case_files
        SET line_items = (
            SELECT COALESCE(jsonb_agg(
                CASE WHEN elem ? 'example_scenarios'
                     THEN elem
                     ELSE elem || '{"example_scenarios": []}'::jsonb
                END
            ), '[]'::jsonb)
            FROM jsonb_array_elements(line_items) AS elem
        )
        WHERE jsonb_typeof(line_items) = 'array'
          AND EXISTS (
              SELECT 1 FROM jsonb_array_elements(line_items) AS e
              WHERE NOT (e ? 'example_scenarios')
          )
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE case_files
        SET line_items = (
            SELECT COALESCE(jsonb_agg(elem - 'example_scenarios'), '[]'::jsonb)
            FROM jsonb_array_elements(line_items) AS elem
        )
        WHERE jsonb_typeof(line_items) = 'array'
        """
    )
