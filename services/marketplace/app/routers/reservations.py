"""`GET /api/reservations/{reservationId}` -- reservation status lookup."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Path
from sqlalchemy.orm import Session
from surplusflow_provider_common.converters import reservation_to_schema
from surplusflow_provider_common.errors import ApiException
from surplusflow_provider_common.models import ReservationRow
from surplusflow_provider_common.schemas import Reservation

from ..dependencies import get_db

router = APIRouter(prefix="/api", tags=["Providers"])

ReservationIdPath = Annotated[str, Path(pattern=r"^[a-z][a-z0-9_-]{2,63}$")]


@router.get("/reservations/{reservation_id}", response_model=Reservation)
def get_reservation(reservation_id: ReservationIdPath, db: Session = Depends(get_db)) -> Reservation:
    row = db.get(ReservationRow, reservation_id)
    if row is None:
        raise ApiException(
            error="not_found",
            message=f"Reservation {reservation_id!r} does not exist.",
            status_code=404,
            retryable=False,
            details={"reservationId": reservation_id},
        )
    return reservation_to_schema(row)
