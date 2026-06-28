# Shared test constants.

# A valid placeholder SECRET_KEY for fixtures: long enough (64 chars) to clear
# create_app's guardrail, obviously synthetic. Not a real secret. Used by every
# DB-backed fixture so the placeholder is consistent and easy to grep.
TEST_SECRET_KEY = "0123456789abcdef" * 4
