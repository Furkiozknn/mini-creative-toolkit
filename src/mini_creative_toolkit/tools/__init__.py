"""Caller-facing operations.

Every function here is the single implementation of its operation: the MCP
server and the CLI both call these, so there is no second copy of the
business rules to drift out of sync.

Each one takes plain JSON-compatible arguments, validates them, and returns
a structured dict from :mod:`mini_creative_toolkit.results`.
"""
