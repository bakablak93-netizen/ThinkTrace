"""Diagnose a non-equivalent step against the bug catalog.

Runs every buggy_transform on the previous step, compares with the student's step,
returns (bug_id, confidence) or UNKNOWN. Distinguishes a one-off slip from a
repeated (persistent) error using the session history. No LLM in the decision.
"""
