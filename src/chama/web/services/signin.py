
"""Complete Google sign-in for existing Kibaba accounts."""
from __future__ import annotations

from sqlalchemy.engine import Connection

from chama.web import auth
from chama.web.data import users
from chama.web.data.users import User
from chama.web.errors import ApiError
from chama.web.settings import WebSettings


NO_ACCESS = (
    "This account has no access to a chama yet. "
    "Ask your chama's admin to add it."
)

MISMATCH = (
    "This Google account does not match the identity linked to "
    "your Kibaba account. Ask your chama's admin to check it."
)


def complete_google_sign_in(
    conn: Connection,
    response,
    user: User | None,
    identity: auth.Identity,
    settings: WebSettings,
) -> User:
    """Verify a Google identity, link it if necessary, and open a session.

    The Kibaba database remains authoritative for account status, role,
    chama membership and member access.

    A Google identity may only be linked to one existing Kibaba account.
    An already-linked account cannot be taken over by another identity.
    """
    # The Google identity must have an email address.
    if not identity.email or not identity.email.strip():
        raise ApiError(
            403,
            "no_access",
            NO_ACCESS,
        )

    # Only existing, active Kibaba accounts may sign in.
    if user is None or not user.active:
        raise ApiError(
            403,
            "no_access",
            NO_ACCESS,
        )

    # The Google email must match the account selected by the callback.
    account_email = (user.email or "").strip().casefold()
    google_email = identity.email.strip().casefold()

    if not account_email or account_email != google_email:
        raise ApiError(
            403,
            "mismatch",
            MISMATCH,
        )

    # If an identity is already linked, it must be the same Google identity.
    if user.identity_id and user.identity_id != identity.id:
        raise ApiError(
            403,
            "mismatch",
            MISMATCH,
        )

    # Link the Google identity on the first successful sign-in.
    # The database operation should only populate an empty identity_id.
    users.link_identity(conn, user.id, identity.id)

    # Read the account again after linking. This confirms that the link
    # actually belongs to this Google identity, including if another
    # sign-in attempt raced with this one.
    linked_user = users.by_email(conn, identity.email)

    if linked_user is None or not linked_user.active:
        raise ApiError(
            403,
            "no_access",
            NO_ACCESS,
        )

    if (
        linked_user.id != user.id
        or linked_user.identity_id != identity.id
    ):
        raise ApiError(
            403,
            "mismatch",
            MISMATCH,
        )

    # Create Kibaba's own session. Supabase access and refresh tokens
    # are not exposed to the browser.
    auth.open_session(
        conn,
        response,
        linked_user,
        settings,
    )

    return linked_user
