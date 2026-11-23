"""
Creates (or re-points) the first manager account on a new server.

    python -m app.create_admin you@company.com "Your Name"

The password is typed at the prompt rather than passed as an argument, so it does not end up in
the shell history, in `ps`, or in a CI log. `app.seed` is the other way to get an account, but it
creates demo users with published passwords and sample sales data: fine on a laptop, wrong on a
server that anyone can reach.

Run it from the backend folder, after `alembic upgrade head`.
"""

import getpass
import re
import sys

from .database import SessionLocal, schema_missing_message
from .models import User
from .security import hash_password

MIN_LENGTH = 12
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def ask_password() -> str:
    """Asks twice, and insists on something long enough to be worth asking twice about."""
    while True:
        first = getpass.getpass("Password: ")
        if len(first) < MIN_LENGTH:
            print(f"  At least {MIN_LENGTH} characters, please.")
            continue
        if first != getpass.getpass("Password again: "):
            print("  Those did not match.")
            continue
        return first


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__.strip())
        return 2
    email, full_name = argv[0].strip().lower(), argv[1].strip()
    if not EMAIL.match(email):
        print(f"{email!r} does not look like an email address.")
        return 2
    if (problem := schema_missing_message()):
        print(problem)
        return 1

    password = ask_password()
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).one_or_none()
        if user:
            # Re-running it is how somebody locked out of the only manager account gets back in.
            user.full_name, user.role, user.is_active = full_name, "manager", True
            user.password_hash = hash_password(password)
            action = "Updated"
        else:
            db.add(User(email=email, full_name=full_name, role="manager",
                        password_hash=hash_password(password), is_active=True))
            action = "Created"
        db.commit()
    finally:
        db.close()
    print(f"{action} manager {email}. Sign in at your server's address.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
