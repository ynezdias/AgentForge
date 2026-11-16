import os

# Test-only signing key; real deployments must provide their own AUTH_SECRET_KEY.
os.environ.setdefault("AUTH_SECRET_KEY", "test-only-signing-key-not-for-any-real-deployment")
os.environ.setdefault("APP_ENV", "test")
