"""Exchange a Supabase email + password for an access token (for API testing).

This does NOT create users (create them in the database / Supabase Studio). It
just signs in and prints the JWT, the same password-grant the frontend will use.
Paste the output as a Bearer token in curl or an HTTP client.

Usage:
    python scripts/dev_token.py you@example.com your-password
"""

from __future__ import annotations

import sys

from alphaforge_api.db import service_client

if len(sys.argv) != 3:
    sys.exit("usage: python scripts/dev_token.py <email> <password>")

email, password = sys.argv[1], sys.argv[2]
session = service_client().auth.sign_in_with_password({"email": email, "password": password})
print(session.session.access_token)
