from typing import DefaultDict, Optional
from uuid import UUID

from fastapi import Depends, Header
from fastapi.exceptions import HTTPException
from fastapi.security.utils import get_authorization_scheme_param

from opal.common.authentication.signer import JWTSigner, JWTClaims, Unauthorized
from opal.common.logger import logger

def get_token_from_header(authorization_header: str) -> Optional[str]:
    """
    extracts a bearer token from an HTTP Authorization header.

    when provided bearer token via websocket,
    we cannot use the fastapi built-in: oauth2_scheme.
    """
    if not authorization_header:
        return None

    scheme, token = get_authorization_scheme_param(authorization_header)
    if not token or scheme.lower() != "bearer":
        return None

    return token

def verify_logged_in(signer: JWTSigner, token: str) -> UUID:
    """
    forces bearer token authentication with valid JWT or throws 401 (can not be used for websocket endpoints)
    """
    if not signer.enabled:
        logger.debug("signer diabled, cannot verify request!")
        return
    claims: JWTClaims = signer.verify(token)
    subject = claims.get("sub", "")

    invalid = Unauthorized(token=token, description="invalid sub claim")
    if not subject:
        raise invalid
    try:
        return UUID(subject)
    except ValueError:
        raise invalid


class JWTVerifier:
    """
    bearer token authentication for http(s) api endpoints.
    throws 401 if a valid jwt is not provided.
    """
    def __init__(self, signer: JWTSigner):
        self.signer = signer

    def __call__(self, authorization: str = Header(...)) -> UUID:
        token = get_token_from_header(authorization)
        return verify_logged_in(self.signer, token)


class JWTVerifierWebsocket:
    """
    bearer token authentication for websocket endpoints.

    with fastapi ws endpoint, we cannot throw http exceptions inside dependencies.
    instead we return a boolean to the endpoint, in order for it to gracefully
    close the connection in case authentication was unsuccessful.
    """
    def __init__(self, signer: JWTSigner):
        self.signer = signer

    def __call__(self, authorization: str = Header(...)) -> bool:
        token = get_token_from_header(authorization)
        try:
            verify_logged_in(self.signer, token)
            return True
        except (Unauthorized, HTTPException):
            return False
