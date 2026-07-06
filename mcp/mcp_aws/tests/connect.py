import logging
import aws_session
from aws_session import *

# Uncomment the level you need:
# logging.basicConfig(level=logging.DEBUG)   # everything — very verbose
logging.basicConfig(level=logging.INFO)      # just high-level request info
# logging.getLogger("botocore").setLevel(logging.DEBUG)
# logging.getLogger("urllib3").setLevel(logging.DEBUG)

print("[1] Building SessionManager...")
manager = aws_session.SessionManager()

print("[2] Calling whoami (sts:GetCallerIdentity) to test AssumeRole...")
try:
    identity = manager.whoami()
    print(f"  Identity: {identity}")
except Exception as e:
    print(f"  whoami FAILED: {e}")
    raise

print("[3] Calling s3:ListBuckets...")
resp = manager.client("s3").list_buckets()
print(resp)
