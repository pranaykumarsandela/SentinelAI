"""Add multi LLM provider, invocation, fallback, and benchmark entities

Revision ID: 001_multi_llm
Revises: 
Create Date: 2026-11-04 11:42:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '001_multi_llm'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. llm_providers
    op.create_table(
        'llm_providers',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('name', sa.String(length=50), nullable=False, unique=True),
        sa.Column('display_name', sa.String(length=100), nullable=False),
        sa.Column('is_enabled', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('is_connected', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('health_status', sa.String(length=30), nullable=False, server_default='NOT_CONFIGURED'),
        sa.Column('latency_ms', sa.Float(), nullable=True),
        sa.Column('last_health_check', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_llm_providers_name', 'llm_providers', ['name'])

    # 2. llm_model_configs
    op.create_table(
        'llm_model_configs',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('provider_id', sa.String(length=36), sa.ForeignKey('llm_providers.id', ondelete='CASCADE'), nullable=False),
        sa.Column('model_id', sa.String(length=100), nullable=False),
        sa.Column('display_name', sa.String(length=100), nullable=False),
        sa.Column('context_window', sa.Integer(), nullable=False, server_default='128000'),
        sa.Column('supports_streaming', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('supports_tool_calling', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('supports_structured_output', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('supports_json_mode', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('input_cost_per_million', sa.Float(), nullable=True),
        sa.Column('output_cost_per_million', sa.Float(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('is_default', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_llm_model_configs_model_id', 'llm_model_configs', ['model_id'])

    # 3. llm_invocations
    op.create_table(
        'llm_invocations',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('trace_id', sa.String(length=36), sa.ForeignKey('execution_traces.id', ondelete='CASCADE'), nullable=True),
        sa.Column('span_id', sa.String(length=36), nullable=True),
        sa.Column('request_id', sa.String(length=100), nullable=True),
        sa.Column('agent_id', sa.String(length=36), nullable=True),
        sa.Column('user_id', sa.String(length=100), nullable=True),
        sa.Column('provider', sa.String(length=50), nullable=False),
        sa.Column('provider_id', sa.String(length=36), sa.ForeignKey('llm_providers.id', ondelete='SET NULL'), nullable=True),
        sa.Column('model', sa.String(length=100), nullable=False),
        sa.Column('task_type', sa.String(length=50), nullable=False, server_default='general'),
        sa.Column('input_tokens', sa.Integer(), nullable=True),
        sa.Column('output_tokens', sa.Integer(), nullable=True),
        sa.Column('total_tokens', sa.Integer(), nullable=True),
        sa.Column('latency_ms', sa.Float(), nullable=True),
        sa.Column('provider_request_id', sa.String(length=150), nullable=True),
        sa.Column('finish_reason', sa.String(length=50), nullable=True),
        sa.Column('status', sa.String(length=30), nullable=False, server_default='SUCCESS'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('error_category', sa.String(length=50), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('fallback_occurred', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('is_mock', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_llm_invocations_provider', 'llm_invocations', ['provider'])
    op.create_index('ix_llm_invocations_trace_id', 'llm_invocations', ['trace_id'])

    # 4. llm_fallback_events
    op.create_table(
        'llm_fallback_events',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('trace_id', sa.String(length=36), sa.ForeignKey('execution_traces.id', ondelete='CASCADE'), nullable=True),
        sa.Column('invocation_id', sa.String(length=36), sa.ForeignKey('llm_invocations.id', ondelete='SET NULL'), nullable=True),
        sa.Column('primary_provider', sa.String(length=50), nullable=False),
        sa.Column('primary_model', sa.String(length=100), nullable=False),
        sa.Column('fallback_provider', sa.String(length=50), nullable=False),
        sa.Column('fallback_model', sa.String(length=100), nullable=False),
        sa.Column('fallback_reason', sa.String(length=100), nullable=False),
        sa.Column('original_error', sa.Text(), nullable=False),
        sa.Column('attempt_number', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('execution_result', sa.String(length=30), nullable=False, server_default='SUCCESS'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_llm_fallback_events_trace_id', 'llm_fallback_events', ['trace_id'])

    # 5. llm_benchmark_runs
    op.create_table(
        'llm_benchmark_runs',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('dataset_name', sa.String(length=100), nullable=False),
        sa.Column('dataset_version', sa.String(length=30), nullable=False, server_default='v1.0'),
        sa.Column('prompt_version', sa.String(length=30), nullable=False, server_default='v1.0'),
        sa.Column('selected_providers', sa.JSON(), nullable=True),
        sa.Column('total_samples', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('status', sa.String(length=30), nullable=False, server_default='RUNNING'),
        sa.Column('pricing_source', sa.String(length=100), nullable=True),
        sa.Column('pricing_version', sa.String(length=30), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )

    # 6. llm_benchmark_results
    op.create_table(
        'llm_benchmark_results',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('benchmark_run_id', sa.String(length=36), sa.ForeignKey('llm_benchmark_runs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('provider', sa.String(length=50), nullable=False),
        sa.Column('model', sa.String(length=100), nullable=False),
        sa.Column('total_requests', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('successful_requests', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('failed_requests', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('avg_latency_ms', sa.Float(), nullable=True),
        sa.Column('p50_latency_ms', sa.Float(), nullable=True),
        sa.Column('p95_latency_ms', sa.Float(), nullable=True),
        sa.Column('total_prompt_tokens', sa.Integer(), nullable=True),
        sa.Column('total_completion_tokens', sa.Integer(), nullable=True),
        sa.Column('total_tokens', sa.Integer(), nullable=True),
        sa.Column('faithfulness_score', sa.Float(), nullable=True),
        sa.Column('relevancy_score', sa.Float(), nullable=True),
        sa.Column('security_score', sa.Float(), nullable=True),
        sa.Column('total_cost_usd', sa.Float(), nullable=True),
        sa.Column('pricing_data', sa.JSON(), nullable=True),
        sa.Column('raw_metrics', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_llm_benchmark_results_run_id', 'llm_benchmark_results', ['benchmark_run_id'])


def downgrade() -> None:
    op.drop_table('llm_benchmark_results')
    op.drop_table('llm_benchmark_runs')
    op.drop_table('llm_fallback_events')
    op.drop_table('llm_invocations')
    op.drop_table('llm_model_configs')
    op.drop_table('llm_providers')

