from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID, uuid4

import httpx
from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from pmc_api.config import Settings, get_settings
from pmc_api.database import get_db, set_request_context
from pmc_api.models import (
    ApplicationSession,
    ExternalIdentity,
    Membership,
    OIDCLoginTransaction,
    Tenant,
    User,
)
from pmc_api.oidc import OIDCProvider, OIDCValidationError
from pmc_api.security import (
    TransactionCipher,
    generate_pkce,
    generate_token,
    token_hash,
    token_matches,
)

router = APIRouter(prefix="/auth", tags=["identity"])
DBSession = Annotated[Session, Depends(get_db)]


class UserResponse(BaseModel):
    id: UUID
    display_name: str
    email: str | None
    current_tenant_id: UUID | None


class TenantResponse(BaseModel):
    id: UUID
    name: str
    slug: str
    role: str


class TenantSelection(BaseModel):
    tenant_id: UUID


@dataclass
class AuthenticatedSession:
    record: ApplicationSession
    token: str
    user: User


def _now() -> datetime:
    return datetime.now(UTC)


def require_session(
    db: DBSession,
    settings: Annotated[Settings, Depends(get_settings)],
    session_token: Annotated[str | None, Cookie(alias="pm_session")] = None,
) -> AuthenticatedSession:
    if not session_token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "authentication required")
    digest = token_hash(session_token)
    set_request_context(db, session_hash=digest)
    record = db.scalar(select(ApplicationSession).where(ApplicationSession.token_hash == digest))
    now = _now()
    if record is None or record.revoked_at is not None or record.expires_at <= now:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "session expired or invalid")
    set_request_context(db, user_id=record.user_id, session_hash=digest)
    user = db.get(User, record.user_id)
    if user is None or user.status != "active":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "identity unavailable")
    return AuthenticatedSession(record=record, token=session_token, user=user)


Authenticated = Annotated[AuthenticatedSession, Depends(require_session)]


def require_csrf(
    request: Request,
    authenticated: Authenticated,
    settings: Annotated[Settings, Depends(get_settings)],
    csrf_header: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
    csrf_cookie: Annotated[str | None, Cookie(alias="pm_csrf")] = None,
) -> None:
    if request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
        return
    if not csrf_header or not csrf_cookie:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "CSRF validation failed")
    if not token_matches(csrf_header, authenticated.record.csrf_token_hash):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "CSRF validation failed")
    if not token_matches(csrf_cookie, authenticated.record.csrf_token_hash):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "CSRF validation failed")
    origin = request.headers.get("origin")
    if origin and origin.rstrip("/") != settings.web_url.rstrip("/"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "request origin denied")


CSRFProtected = Annotated[None, Depends(require_csrf)]


@router.get("/login")
async def login(db: DBSession, settings: Annotated[Settings, Depends(get_settings)]) -> Response:
    now = _now()
    state_value = generate_token()
    state_digest = token_hash(state_value)
    login_binding = generate_token()
    nonce = generate_token()
    pkce = generate_pkce()
    set_request_context(db, login_state_hash=state_digest)
    db.add(
        OIDCLoginTransaction(
            id=uuid4(),
            state_hash=state_digest,
            login_binding_hash=token_hash(login_binding),
            encrypted_pkce_verifier=TransactionCipher(settings.login_transaction_key).encrypt(
                pkce.verifier
            ),
            nonce=nonce,
            created_at=now,
            expires_at=now + timedelta(seconds=settings.login_ttl_seconds),
        )
    )
    db.commit()
    async with httpx.AsyncClient(timeout=10) as client:
        authorization_url = await OIDCProvider(settings, client).authorization_url(
            state=state_value, nonce=nonce, challenge=pkce.challenge
        )
    response = RedirectResponse(authorization_url, status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(
        settings.login_cookie_name,
        login_binding,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/auth",
        max_age=settings.login_ttl_seconds,
    )
    return response


@router.get("/callback")
async def callback(
    request: Request,
    code: str,
    state: str,
    db: DBSession,
    settings: Annotated[Settings, Depends(get_settings)],
) -> Response:
    now = _now()
    state_digest = token_hash(state)
    set_request_context(db, login_state_hash=state_digest)
    transaction = db.scalar(
        select(OIDCLoginTransaction).where(OIDCLoginTransaction.state_hash == state_digest)
    )
    if transaction is None or transaction.used_at is not None or transaction.expires_at <= now:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid or expired login state")
    login_binding = request.cookies.get(settings.login_cookie_name)
    if not login_binding or not token_matches(login_binding, transaction.login_binding_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid login binding")
    transaction.used_at = now
    db.commit()
    verifier = TransactionCipher(settings.login_transaction_key).decrypt(
        transaction.encrypted_pkce_verifier
    )
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            provider = OIDCProvider(settings, client)
            id_token = await provider.exchange_code(code=code, verifier=verifier)
            claims = await provider.validate_id_token(id_token, nonce=transaction.nonce)
    except (OIDCValidationError, httpx.HTTPError) as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "identity assertion rejected") from exc

    set_request_context(db, issuer=claims.issuer, subject=claims.subject)
    identity = db.scalar(
        select(ExternalIdentity).where(
            ExternalIdentity.issuer == claims.issuer,
            ExternalIdentity.subject == claims.subject,
        )
    )
    user_id = identity.user_id if identity else uuid4()
    set_request_context(db, user_id=user_id, issuer=claims.issuer, subject=claims.subject)
    user = db.get(User, user_id)
    if user is None:
        user = User(
            id=user_id,
            display_name=claims.display_name,
            email=claims.email,
            status="active",
            created_at=now,
            last_login_at=now,
        )
        db.add(user)
        db.flush()
        db.add(
            ExternalIdentity(
                id=uuid4(),
                user_id=user_id,
                issuer=claims.issuer,
                subject=claims.subject,
                created_at=now,
            )
        )
    elif user.status != "active":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "identity disabled")
    else:
        user.display_name = claims.display_name
        user.email = claims.email
        user.last_login_at = now

    active_memberships = db.scalars(
        select(Membership).where(Membership.user_id == user_id, Membership.status == "active")
    ).all()
    current_tenant_id = active_memberships[0].tenant_id if len(active_memberships) == 1 else None
    session_token = generate_token()
    csrf_token = generate_token()
    db.add(
        ApplicationSession(
            id=uuid4(),
            user_id=user_id,
            token_hash=token_hash(session_token),
            current_tenant_id=current_tenant_id,
            csrf_token_hash=token_hash(csrf_token),
            created_at=now,
            expires_at=now + timedelta(seconds=settings.session_ttl_seconds),
            last_seen_at=now,
        )
    )
    db.commit()

    response = RedirectResponse(settings.web_url, status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie(
        settings.login_cookie_name,
        path="/auth",
        secure=settings.cookie_secure,
        httponly=True,
        samesite="lax",
    )
    response.set_cookie(
        settings.session_cookie_name,
        session_token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
        max_age=settings.session_ttl_seconds,
    )
    response.set_cookie(
        settings.csrf_cookie_name,
        csrf_token,
        httponly=False,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
        max_age=settings.session_ttl_seconds,
    )
    return response


@router.get("/me", response_model=UserResponse)
def me(authenticated: Authenticated) -> UserResponse:
    return UserResponse(
        id=authenticated.user.id,
        display_name=authenticated.user.display_name,
        email=authenticated.user.email,
        current_tenant_id=authenticated.record.current_tenant_id,
    )


@router.get("/tenants", response_model=list[TenantResponse])
def tenants(db: DBSession, authenticated: Authenticated) -> list[TenantResponse]:
    set_request_context(
        db,
        user_id=authenticated.user.id,
        session_hash=authenticated.record.token_hash,
    )
    rows = db.execute(
        select(Tenant, Membership.role)
        .join(Membership, Membership.tenant_id == Tenant.id)
        .where(Membership.user_id == authenticated.user.id, Membership.status == "active")
        .order_by(Tenant.name)
    ).all()
    return [
        TenantResponse(id=tenant.id, name=tenant.name, slug=tenant.slug, role=role)
        for tenant, role in rows
    ]


@router.post("/tenant", response_model=TenantResponse, dependencies=[Depends(require_csrf)])
def select_tenant(
    selection: TenantSelection,
    db: DBSession,
    authenticated: Authenticated,
) -> TenantResponse:
    set_request_context(db, user_id=authenticated.user.id, tenant_id=selection.tenant_id)
    row = db.execute(
        select(Tenant, Membership.role)
        .join(Membership, Membership.tenant_id == Tenant.id)
        .where(
            Tenant.id == selection.tenant_id,
            Membership.user_id == authenticated.user.id,
            Membership.status == "active",
        )
    ).one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "tenant access denied")
    authenticated.record.current_tenant_id = selection.tenant_id
    db.commit()
    tenant, role = row
    return TenantResponse(id=tenant.id, name=tenant.name, slug=tenant.slug, role=role)


@router.post(
    "/logout", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_csrf)]
)
def logout(
    response: Response,
    db: DBSession,
    authenticated: Authenticated,
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    authenticated.record.current_tenant_id = None
    authenticated.record.revoked_at = _now()
    db.commit()
    response.delete_cookie(settings.session_cookie_name, path="/")
    response.delete_cookie(settings.csrf_cookie_name, path="/")
