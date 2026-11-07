"""Print the current TOTP code for a seeded dev account: ``python scripts/totp.py admin``.

Equivalent to scanning the secret into Google Authenticator / Authy.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vps.config import Settings  # noqa: E402
from vps.security import totp  # noqa: E402

if __name__ == "__main__":
    s = Settings.from_env()
    who = sys.argv[1] if len(sys.argv) > 1 else "admin"
    secret = {"admin": s.admin_totp_secret, "manager": s.manager_totp_secret}.get(who)
    if not secret:
        sys.exit("only 'admin' and 'manager' have TOTP in the dev seed")
    print(totp(secret))
