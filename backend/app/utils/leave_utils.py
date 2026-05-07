"""
Utilitaires métier pour le module Congés & Permissions.

- Calcul des jours ouvrables
- Validation du délai minimum 48h
- Validation des plages horaires
- Architecture prévue pour jours fériés configurables
"""

from datetime import date, datetime, timedelta, timezone
from typing import Optional


# ── Jours fériés ───────────────────────────────────────────────────────────────
# Architecture extensible : à terme, charger depuis la DB par pays/région

DEFAULT_PUBLIC_HOLIDAYS: list[date] = [
    # France 2025 — à adapter selon le pays de l'entreprise
    date(2025, 1,  1),   # Jour de l'An
    date(2025, 5,  1),   # Fête du Travail
    date(2025, 5,  8),   # Victoire 1945
    date(2025, 7,  14),  # Fête Nationale
    date(2025, 8,  15),  # Assomption
    date(2025, 11, 1),   # Toussaint
    date(2025, 11, 11),  # Armistice
    date(2025, 12, 25),  # Noël
]


def is_working_day(d: date, holidays: Optional[list[date]] = None) -> bool:
    """Retourne True si le jour est ouvrable (lun-ven, hors jours fériés)."""
    if holidays is None:
        holidays = DEFAULT_PUBLIC_HOLIDAYS
    return d.weekday() < 5 and d not in holidays


def calculate_working_days(
    start: date,
    end:   date,
    holidays: Optional[list[date]] = None,
) -> float:
    """
    Calcule le nombre de jours ouvrables entre deux dates incluses.
    Retourne 0.0 si start > end.
    """
    if start > end:
        return 0.0

    count = 0.0
    current = start
    while current <= end:
        if is_working_day(current, holidays):
            count += 1.0
        current += timedelta(days=1)
    return count


def calculate_permission_hours(time_start: str, time_end: str) -> float:
    """
    Calcule la durée en heures d'une permission horaire.
    time_start/time_end au format "HH:MM".
    """
    h_start, m_start = map(int, time_start.split(":"))
    h_end,   m_end   = map(int, time_end.split(":"))
    total_minutes = (h_end * 60 + m_end) - (h_start * 60 + m_start)
    return round(total_minutes / 60, 2)


def validate_minimum_notice(date_start: datetime) -> bool:
    """
    Vérifie que la demande est faite au minimum 48h avant le début.
    Retourne True si le délai est respecté.
    """
    now = datetime.now(timezone.utc)
    if date_start.tzinfo is None:
        date_start = date_start.replace(tzinfo=timezone.utc)
    delta = date_start - now
    return delta.total_seconds() >= 48 * 3600


def validate_time_range(time_start: str, time_end: str) -> bool:
    """
    Vérifie que les heures sont dans la plage 08:00 → 17:00
    et que time_end > time_start.
    """
    allowed_start = "08:00"
    allowed_end   = "17:00"

    if time_start < allowed_start or time_end > allowed_end:
        return False
    if time_start >= time_end:
        return False
    return True