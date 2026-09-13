from sqlalchemy import select
from flower.models import Device, Job
from flower.services.alerts import alert
from flower.worker import Worker


def test_deduplicated_alert_queues_one_mock_notification(system):
    with system["app"].state.sessions.begin() as db:
        device = db.get(Device, system["device_id"])
        first = alert(db, device, "LOW_WATER", "Mock low water")
        second = alert(db, device, "LOW_WATER", "Mock low water")
        assert first.id == second.id
    assert Worker(system["app"].state.sessions, system["settings"]).run_once()
    with system["app"].state.sessions() as db:
        jobs = list(db.scalars(select(Job).where(Job.job_type == "alert_notification")))
        assert len(jobs) == 1
        assert jobs[0].status == "succeeded"
        assert jobs[0].result["source_type"] == "mock"
