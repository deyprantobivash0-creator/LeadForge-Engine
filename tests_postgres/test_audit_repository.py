"""I2 repository checks reused against the guarded disposable PostgreSQL fixture."""

import pytest
from sqlalchemy import create_engine

from tests.test_audit_repository import (
    test_append_is_provisional_caller_commits_and_read_is_immutable,
    test_later_database_failure_rolls_back_append,
    test_nested_e02_scope_no_early_commit_and_outer_failure,
    test_caught_nested_failure_preserves_e02_rollback_only,
    test_nested_e02_success_has_one_root_commit,
    test_append_requires_existing_caller_service_scope,
    test_arbitrary_dict_or_orm_cannot_enter_append,
    test_modified_builder_result_rejected_before_session_mutation,
    test_cross_tenant_lookup_and_not_found_are_indistinguishable,
    test_reads_require_valid_explicit_tenant,
    test_no_unscoped_read_or_history_mutation_surface,
    test_i1_guards_remain_effective_and_session_recovers,
    test_unrelated_models_still_mutate_and_history_needs_no_live_org,
    test_duplicate_append_is_not_upsert_or_silent_replacement,
)


@pytest.fixture
def audit_engine(pg_database):
    engine = create_engine(pg_database["url"])
    try:
        yield engine
    finally:
        engine.dispose()
