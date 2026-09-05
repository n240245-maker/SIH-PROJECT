"""Shared authoritative role-scope request validation."""

from __future__ import annotations

from fastapi import HTTPException, Query

from backend.schemas import Role
from backend.services.application import Scope


def request_scope(
    role: Role = Query(Role.MOSPI),
    state: str | None = Query(None),
    district: str | None = Query(None),
    mp_id: str | None = Query(None),
    agency_id: str | None = Query(None),
) -> Scope:
    scope = Scope(role=role, state=state, district=district, mp_id=mp_id, agency_id=agency_id)
    if role == Role.STATE and not state:
        raise HTTPException(422, "STATE role requires state")
    if role == Role.DISTRICT and (not state or not district):
        raise HTTPException(422, "DISTRICT role requires state and district")
    if role == Role.MP and not mp_id:
        raise HTTPException(422, "MP role requires mp_id")
    if role == Role.IA and not agency_id:
        raise HTTPException(422, "IA role requires agency_id")
    return scope
