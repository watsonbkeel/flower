from dataclasses import asdict, replace
from datetime import timedelta

from sqlalchemy import select, func

from flower.errors import DomainError
from flower.models import Device, FallbackPolicy, Memory, Event, Command, WateringSession, utcnow
from flower.services.commands import safety_context, quota_used, create_command
from flower.services.decision import DecisionInput, DecisionConfig, decide
from flower.services.knowledge import Knowledge, MemoryRule, compile_policy, Weather, CareSource
from flower.services.weather import current_weather


def research(provider, plant):
    sources = [
        CareSource.model_validate(source).model_dump(mode="json")
        for source in provider.search(plant)
    ]
    sources = [s for s in sources if s["confidence"] >= 0.6 and s["category"] != "other"]
    if len({s["url"] for s in sources}) < 2:
        raise DomainError("INSUFFICIENT_SOURCES")
    try:
        knowledge = Knowledge.model_validate(provider.structure_care(sources))
        if not set(knowledge.source_ids) <= {s["id"] for s in sources}:
            raise ValueError("unknown knowledge source")
    except (ValueError, DomainError):
        knowledge = Knowledge(
            needs_review=True,
            source_ids=[s["id"] for s in sources],
            notes=["结构化服务不可用，待用户复核保守知识模板"],
        )
    conflict = any(s["conflict"] for s in sources)
    if conflict:
        knowledge.needs_review = True
        knowledge.soil_target_min_pct = max(10, knowledge.soil_target_min_pct - 5)
    try:
        weather = Weather.model_validate(provider.weather(plant)).model_dump(mode="json")
    except (ValueError, DomainError):
        weather = None
    return knowledge.model_dump(mode="json") | {
        "sources": sources,
        "source_conflict": conflict,
        "source_type": "real" if all(s["source_type"] == "real" for s in sources) else "mock",
        "weather": weather,
    }


def profile_windows(profile):
    windows = []
    if "early_morning" in profile.get("watering_windows", []):
        windows.append(["06:00", "09:00"])
    if "early_evening" in profile.get("watering_windows", []):
        windows.append(["17:00", "20:00"])
    return windows or [["06:00", "09:00"]]


def issue_fallback(db, settings, plant, profile):
    db.refresh(db.get(Device, plant.device_id), with_for_update=True)
    version = (
        db.scalar(
            select(func.max(FallbackPolicy.policy_version)).where(
                FallbackPolicy.device_id == plant.device_id
            )
        )
        or 0
    ) + 1
    now = utcnow()
    normal = {"small": 10, "medium": 20, "large": 30}[plant.pot_size]
    windows = profile_windows(profile.profile)
    effective = dict(profile.profile)
    for memory in db.scalars(
        select(Memory)
        .where(
            Memory.plant_id == plant.id,
            Memory.rule_confirmed.is_(True),
            Memory.rule_enabled.is_(True),
        )
        .order_by(Memory.created_at)
    ):
        rule = MemoryRule.model_validate(memory.structured_rule)
        if rule.preferred_windows:
            windows = rule.preferred_windows
        effective["soil_target_min_pct"] = min(
            effective["soil_target_min_pct"],
            profile.profile["soil_target_min_pct"] + rule.threshold_shift_pct,
        )
        if rule.watering_style == "small_portions":
            normal = min(normal, 5)
    dose = min(normal, 10) * (1 if plant.has_drainage else 0.5)
    compiled = compile_policy(
        profile=effective,
        profile_version=profile.version,
        policy_version=version,
        now=now,
        timezone_name=plant.timezone,
        windows=windows,
        pulse_ml=dose,
        max_24h_ml=settings.pump_max_24h_ml,
    )
    policy = FallbackPolicy(
        device_id=plant.device_id,
        plant_id=plant.id,
        policy_version=version,
        profile_version=profile.version,
        policy=compiled["policy"],
        policy_hash=compiled["policy_hash"],
        valid_from=now,
        valid_until=now + timedelta(days=7),
    )
    db.add(policy)
    db.flush()
    return policy


def evaluate_plant(db, settings, plant, *, create=True):
    now = utcnow()
    device = db.get(Device, plant.device_id)
    try:
        status, profile, calibration = safety_context(
            db, settings, device, plant, now, source="cloud_auto"
        )
    except DomainError as exc:
        return {
            "decision": "hold",
            "reason": exc.code,
            "memory_effects": [],
            "explain_zh": exc.message,
        }
    memories = list(
        db.scalars(
            select(Memory)
            .where(
                Memory.plant_id == plant.id,
                Memory.rule_confirmed.is_(True),
                Memory.rule_enabled.is_(True),
            )
            .order_by(Memory.created_at)
        )
    )
    used = max(quota_used(db, device.id, now), status.used_24h_ml)
    last = db.scalar(
        select(func.max(WateringSession.occurred_at)).where(
            WateringSession.device_id == device.id, WateringSession.quota_ml > 0
        )
    )
    weather = current_weather(profile.profile.get("weather"), now, device.source_type)
    rain = bool(weather and weather.rain_next_12h_mm >= 3)
    values = DecisionInput(
        now=now,
        timezone=plant.timezone,
        soil_pct=status.soil_moisture,
        target_min=profile.profile["soil_target_min_pct"],
        target_max=profile.profile["soil_target_max_pct"],
        windows=profile_windows(profile.profile),
        pot_size=plant.pot_size,
        pot_material=plant.pot_material,
        has_drainage=plant.has_drainage,
        placement_type=plant.placement_type,
        water_level_ok=status.water_level_ok,
        time_trusted=device.time_trusted,
        calibration_valid=True,
        profile_confirmed=True,
        operating_mode=device.operating_mode,
        activity=status.activity,
        auto_mode=plant.auto_mode,
        interval_ok=not last
        or (now - last).total_seconds() >= settings.pump_min_interval_hours * 3600,
        quota_remaining_ml=settings.pump_max_24h_ml - used,
        active_command=bool(
            db.scalar(
                select(Command.id).where(
                    Command.device_id == device.id,
                    Command.action == "dispense",
                    Command.status.in_(["pending", "claimed", "executing"]),
                )
            )
        ),
        temperature_c=status.temperature_c,
        air_humidity=status.air_humidity,
        air_fresh=status.sensor_health.get("air_age_sec", 100000) <= 300,
        rain_expected=rain,
    )
    config = DecisionConfig(
        urgent_gap_pct=settings.urgent_override_gap_pct,
        session_max_ml=settings.max_single_session_ml,
        max_pulses=settings.max_pulses_limit,
    )
    baseline = decide(values, config)
    decision = decide(replace(values, memory_rules=[m.structured_rule for m in memories]), config)
    effects = []
    if decision != baseline:
        for memory in memories:
            without = decide(
                replace(
                    values, memory_rules=[m.structured_rule for m in memories if m.id != memory.id]
                ),
                config,
            )
            if without == decision:
                continue
            effect = {
                "memory_id": memory.id,
                "original_experience": memory.original_experience,
                "before": asdict(without),
                "after": asdict(decision),
            }
            effects.append(effect)
            key = f"memory:{memory.id}:{status.reported_at.isoformat()}"
            if not db.scalar(
                select(Event.id).where(Event.device_id == device.id, Event.event_id == key)
            ):
                db.add(
                    Event(
                        device_id=device.id,
                        plant_id=plant.id,
                        event_id=key,
                        event_type="memory_rule_applied",
                        event_data=effect,
                        human_readable=f"家庭经验参与养护：{memory.original_experience}",
                        source_type=device.source_type,
                        occurred_at=now,
                    )
                )
                if device.source_type == "real":
                    memory.applied_count += 1
                    memory.last_applied_at = now
    output = asdict(decision) | {"memory_effects": effects, "source_type": device.source_type}
    if create and decision.decision == "water":
        try:
            cmd = create_command(
                db,
                settings,
                device_id=device.id,
                plant_id=plant.id,
                user_id=plant.user_id,
                capability="dispenser",
                action="dispense",
                parameters={
                    "quantity": decision.session_max_ml,
                    "unit": "ml",
                    "pulse_ml": decision.pulse_ml,
                    "stop_soil_pct": decision.effective_min_pct,
                },
                source="cloud_auto",
                run_mode=settings.run_mode,
                idempotency_key=f"auto:{plant.id}:{status.reported_at.isoformat()}",
            )
            output["command_id"] = cmd.id
        except DomainError as exc:
            output.update(decision="hold", reason=exc.code)
    key = f"decision:{plant.id}:{status.reported_at.isoformat()}"
    if not db.scalar(select(Event.id).where(Event.device_id == device.id, Event.event_id == key)):
        db.add(
            Event(
                device_id=device.id,
                plant_id=plant.id,
                event_id=key,
                event_type="decision",
                event_data=output,
                human_readable=output["explain_zh"],
                source_type=device.source_type,
                occurred_at=now,
            )
        )
    return output
