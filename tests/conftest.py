import pytest

from alloy.agent.loop import SEED_CLAIMS
from alloy.knowledge.extract import load_seed


@pytest.fixture
def seed_claims():
    return load_seed(SEED_CLAIMS)
