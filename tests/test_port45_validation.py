"""Expose PORT-45 checks to discovery without colliding with the script basename."""

from scripts.test_port45_no_overdraw import (  # noqa: F401
    TestPort45ArtifactsAndMemory,
    TestPort45HostSimulation,
)
