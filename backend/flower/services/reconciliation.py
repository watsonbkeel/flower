from sqlalchemy import select

from flower.models import WateringSession


def verify_receipt(db, cmd, result, now):
    end = result.finished_at
    if (
        cmd.action != "dispense"
        or cmd.status not in {"executing", "succeeded", "timed_out"}
        or result.status != "succeeded"
        or result.provisional
        or end is None
        or cmd.started_at is None
        or cmd.session_deadline_at is None
        or not cmd.started_at <= end <= min(now, cmd.session_deadline_at)
        or result.actual_ml > cmd.parameters["target_ml"]
    ):
        return False
    pulses = result.pulses
    if (
        [p.pulse for p in pulses] != list(range(1, len(pulses) + 1))
        or len(pulses) > cmd.parameters["max_pulses"]
        or abs(sum(p.estimated_ml for p in pulses) - result.actual_ml) > 0.001
        or any(not cmd.started_at <= p.finished_at <= end for p in pulses)
        or any(a.finished_at > b.finished_at for a, b in zip(pulses, pulses[1:]))
    ):
        return False
    session = db.scalar(
        select(WateringSession).where(WateringSession.command_id == cmd.id).with_for_update()
    )
    if not session:
        return False
    previous = session.pulse_details or []
    serialized = result.model_dump(mode="json")["pulses"]
    if serialized[: len(previous)] != previous:
        return False
    session.actual_ml = result.actual_ml
    session.quota_ml = result.actual_ml
    session.pulse_details = serialized
    session.status, session.reconciled = "reconciled", True
    return True
