"""
Schémas Pydantic pour le module Congés & Permissions.
"""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.leave import (
    LeaveType, PermissionType, RequestCategory, RequestStatus
)


# ── Création ───────────────────────────────────────────────────────────────────

class LeaveRequestCreate(BaseModel):
    category:        RequestCategory
    leave_type:      Optional[LeaveType]      = None
    permission_type: Optional[PermissionType] = None
    date_start:      datetime
    date_end:        datetime
    time_start:      Optional[str] = Field(None, pattern=r"^\d{2}:\d{2}$")
    time_end:        Optional[str] = Field(None, pattern=r"^\d{2}:\d{2}$")
    description:     str = Field(..., min_length=10, max_length=1000)

    @model_validator(mode="after")
    def validate_category_fields(self) -> "LeaveRequestCreate":
        if self.category == RequestCategory.LEAVE and not self.leave_type:
            raise ValueError("leave_type est requis pour un congé.")
        if self.category == RequestCategory.PERMISSION and not self.permission_type:
            raise ValueError("permission_type est requis pour une permission.")
        if self.date_end < self.date_start:
            raise ValueError("date_end doit être après date_start.")
        return self


# ── Traitement (Manager/Admin) ─────────────────────────────────────────────────

class LeaveRequestReview(BaseModel):
    approved: bool
    comment:  Optional[str] = Field(None, max_length=500)


# ── Réponses API ───────────────────────────────────────────────────────────────

class UserMini(BaseModel):
    id:        uuid.UUID
    full_name: str
    email:     str
    role:      str

    model_config = {"from_attributes": True}


class LeaveRequestResponse(BaseModel):
    id:              uuid.UUID
    category:        RequestCategory
    leave_type:      Optional[LeaveType]
    permission_type: Optional[PermissionType]
    date_start:      datetime
    date_end:        datetime
    time_start:      Optional[str]
    time_end:        Optional[str]
    working_days:    float
    description:     str
    attachment_url:  Optional[str]
    status:          RequestStatus
    requester:       UserMini
    manager:         Optional[UserMini]
    admin:           Optional[UserMini]
    manager_comment: Optional[str]
    admin_comment:   Optional[str]
    manager_reviewed_at: Optional[datetime]
    admin_reviewed_at:   Optional[datetime]
    created_at:      datetime
    updated_at:      datetime

    model_config = {"from_attributes": True}


class LeaveRequestListResponse(BaseModel):
    items: list[LeaveRequestResponse]
    total: int
    page:  int
    size:  int
    pages: int


class LeaveStatsResponse(BaseModel):
    total:           int
    approved:        int
    rejected:        int
    pending_manager: int
    pending_admin:   int
    leaves:          int
    permissions:     int