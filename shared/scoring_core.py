"""Shared scoring core — single source of truth for scoring logic.

Used by both api/ and agent/. Stateless functions with explicit params.
Agent adapter (agent/scoring.py) wraps these with profile globals.
"""
