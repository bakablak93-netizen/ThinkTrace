"""LLMClient abstraction: real provider (key from env) and TemplateClient (offline).
Falls back to TemplateClient automatically when no key is configured or a call fails.
"""
