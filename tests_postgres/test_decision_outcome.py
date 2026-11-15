"""The same outcome invariants on guarded disposable PostgreSQL storage."""
from tests_postgres.test_decision_ledger import ledger_database, ledger_engine
from tests.test_decision_outcome import (
    test_roundtrip_order_pages_actor_and_immutable_decision,
    test_effectiveness_is_observation_not_recommendation_accuracy,
    test_observation_must_follow_decision_and_not_be_future,
    test_scoped_relationship_not_found,
    test_record_requires_fresh_user_membership,
    test_outcomes_cannot_be_overwritten,
    test_append_failure_rolls_back_without_decision_mutation,
    test_database_scoped_foreign_key_rejects_cross_decision_link,
)
