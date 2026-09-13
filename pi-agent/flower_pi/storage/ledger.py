from datetime import datetime, timezone
import json
import math
from pathlib import Path
import sqlite3


def timestamp(now):
    if not isinstance(now, datetime) or now.tzinfo is None:
        raise ValueError("TIME_UNTRUSTED")
    return now.timestamp()


class Ledger:
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(str(path), timeout=30)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute("PRAGMA synchronous=FULL")
        self.connection.executescript("""
            CREATE TABLE IF NOT EXISTS water_ledger (
                id INTEGER PRIMARY KEY AUTOINCREMENT, command_id TEXT UNIQUE NOT NULL,
                source TEXT NOT NULL, state TEXT NOT NULL, reserved_ml REAL NOT NULL,
                actual_ml REAL, quota_ml REAL NOT NULL, server_issued_at_utc REAL,
                trusted_wall_time_utc REAL, recovered_at_utc REAL, boot_id TEXT NOT NULL,
                monotonic_started REAL, monotonic_finished REAL, created_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS local_values (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS outbox (
                id TEXT PRIMARY KEY, route TEXT NOT NULL, payload TEXT NOT NULL,
                created_at REAL NOT NULL
            );
        """)

    def close(self):
        self.connection.close()

    def get(self, command_id):
        row = self.connection.execute(
            "SELECT * FROM water_ledger WHERE command_id=?", (command_id,)
        ).fetchone()
        return dict(row) if row else None

    def _used(self, now):
        cutoff = timestamp(now) - 86400
        rows = self.connection.execute(
            """SELECT quota_ml FROM water_ledger
            WHERE COALESCE(trusted_wall_time_utc, server_issued_at_utc, recovered_at_utc) IS NULL
               OR COALESCE(trusted_wall_time_utc, server_issued_at_utc, recovered_at_utc) > ?""",
            (cutoff,),
        )
        local = sum(row[0] for row in rows)
        cloud = self.value("cloud_quota", {})
        cloud_used = cloud.get("used", 0) if cloud.get("observed", 0) > cutoff else 0
        return max(local, cloud_used)

    def used(self, now):
        return self._used(now)

    def last_watered(self):
        row = self.connection.execute("""SELECT MAX(COALESCE(trusted_wall_time_utc,
            server_issued_at_utc, recovered_at_utc)) FROM water_ledger""").fetchone()
        return datetime.fromtimestamp(row[0], timezone.utc) if row[0] is not None else None

    def reserve(
        self, command_id, source, amount, now, boot_id, monotonic, *, limit_ml, interval_hours
    ):
        wall = timestamp(now)
        if not math.isfinite(amount) or not 0 < amount <= 60:
            raise ValueError("INVALID_AMOUNT")
        try:
            self.connection.execute("BEGIN IMMEDIATE")
            if self.get(command_id):
                raise ValueError("DUPLICATE_COMMAND")
            last = self.last_watered()
            if last and (now - last).total_seconds() < interval_hours * 3600:
                raise ValueError("MIN_INTERVAL")
            if self._used(now) + amount > limit_ml:
                raise ValueError("QUOTA_EXCEEDED")
            self.connection.execute(
                """INSERT INTO water_ledger
                (command_id,source,state,reserved_ml,quota_ml,trusted_wall_time_utc,
                 boot_id,monotonic_started,created_at) VALUES (?,?,'reserved',?,?,?,?,?,?)""",
                (command_id, source, amount, amount, wall, boot_id, monotonic, wall),
            )
            self.connection.commit()
        except Exception:
            self.connection.rollback()
            raise

    def progress(self, command_id, actual_ml):
        with self.connection:
            self.connection.execute(
                "UPDATE water_ledger SET actual_ml=? WHERE command_id=? AND state='reserved'",
                (actual_ml, command_id),
            )

    def provisional(self, command_id):
        with self.connection:
            self.connection.execute(
                """UPDATE water_ledger SET state='provisional', quota_ml=reserved_ml
                WHERE command_id=? AND state='reserved'""",
                (command_id,),
            )

    def recover(self, now):
        wall = timestamp(now) if now is not None else None
        with self.connection:
            self.connection.execute(
                "UPDATE water_ledger SET state='provisional', quota_ml=reserved_ml WHERE state='reserved'"
            )
            if wall is not None:
                self.connection.execute(
                    """UPDATE water_ledger SET recovered_at_utc=?
                    WHERE state='provisional' AND trusted_wall_time_utc IS NULL
                    AND server_issued_at_utc IS NULL AND recovered_at_utc IS NULL""",
                    (wall,),
                )

    def finish(self, command_id, *, actual_ml, now, monotonic, verified):
        row = self.get(command_id)
        if not verified or not row or row["state"] != "reserved":
            raise ValueError("UNVERIFIED_SETTLEMENT")
        timestamp(now)
        if not math.isfinite(actual_ml) or not 0 <= actual_ml <= row["reserved_ml"]:
            raise ValueError("INVALID_SETTLEMENT")
        with self.connection:
            self.connection.execute(
                """UPDATE water_ledger SET state='final',actual_ml=?,quota_ml=?,
                monotonic_finished=? WHERE command_id=?""",
                (actual_ml, actual_ml, monotonic, command_id),
            )

    def reconcile_used(self, cloud_used, now):
        if not math.isfinite(cloud_used) or cloud_used < 0:
            raise ValueError("INVALID_CLOUD_QUOTA")
        local = self.used(now)
        previous = self.value("cloud_quota", {})
        wall = timestamp(now)
        if previous.get("observed", 0) <= wall - 86400 or cloud_used >= previous.get("used", 0):
            self.set_value("cloud_quota", {"used": cloud_used, "observed": wall})
        return max(local, cloud_used), local != cloud_used

    def receipts(self):
        rows = self.connection.execute(
            "SELECT key,value FROM local_values WHERE key LIKE 'receipt:%' ORDER BY key LIMIT 100"
        )
        return [
            {"command_id": row["key"][8:], "result": json.loads(row["value"])}
            for row in rows
            if self.get(row["key"][8:])["source"] != "local_fallback"
        ]

    def reconcile_receipt(self, receipt, now):
        command_id = receipt["command_id"]
        row = self.get(command_id)
        local = self.value("receipt:" + command_id)
        result = receipt["result"]
        if not local or not row:
            raise ValueError("MISSING_LOCAL_RECEIPT")

        def normalized(value):
            return (
                value.get("status"),
                value.get("actual_ml"),
                datetime.fromisoformat(value["finished_at"]),
                [
                    (p["pulse"], p["estimated_ml"], datetime.fromisoformat(p["finished_at"]))
                    for p in value["pulses"]
                ],
            )

        if normalized(local) != normalized(result):
            raise ValueError("RECEIPT_MISMATCH")
        end = datetime.fromisoformat(result["finished_at"])
        amount = result["actual_ml"]
        if (
            result["status"] != "succeeded"
            or not math.isfinite(amount)
            or not 0 <= amount <= row["reserved_ml"]
            or end.tzinfo is None
            or not row["trusted_wall_time_utc"] <= timestamp(end) <= timestamp(now)
            or abs(sum(p["estimated_ml"] for p in result["pulses"]) - amount) > 0.001
        ):
            raise ValueError("UNVERIFIED_SETTLEMENT")
        with self.connection:
            self.connection.execute(
                "UPDATE water_ledger SET state='reconciled',actual_ml=?,quota_ml=? WHERE command_id=?",
                (amount, amount, command_id),
            )
            self.connection.execute(
                "DELETE FROM local_values WHERE key=?", ("receipt:" + command_id,)
            )
        return True

    def value(self, key, default=None):
        row = self.connection.execute(
            "SELECT value FROM local_values WHERE key=?", (key,)
        ).fetchone()
        return json.loads(row[0]) if row else default

    def set_value(self, key, value):
        with self.connection:
            self.connection.execute(
                "INSERT OR REPLACE INTO local_values VALUES (?,?)", (key, json.dumps(value))
            )

    def enqueue(self, key, route, payload, now):
        with self.connection:
            self.connection.execute(
                "INSERT OR IGNORE INTO outbox VALUES (?,?,?,?)",
                (key, route, json.dumps(payload), timestamp(now)),
            )

    def pending(self):
        return [
            dict(row)
            for row in self.connection.execute("SELECT * FROM outbox ORDER BY created_at LIMIT 100")
        ]

    def acknowledge(self, key):
        with self.connection:
            self.connection.execute("DELETE FROM outbox WHERE id=?", (key,))
