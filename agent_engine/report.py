import hashlib
import json
import os
import subprocess
from collections import Counter
from decimal import Decimal
from pathlib import Path

from agent_engine.schemas import RequestCounts, RunFlags, RunReport

COST_LIMIT_USD = Decimal("10")
DAILY_TIME_LIMIT_MIN = 45


def code_version() -> str:
    try:
        result = subprocess.run(["git", "rev-parse", "--short=8", "HEAD"], capture_output=True, text=True,
                                timeout=5, cwd=Path(__file__).parent)
    except (OSError, subprocess.SubprocessError):
        return "0.1.0-dev"
    version = result.stdout.strip()
    return version if result.returncode == 0 and len(version) >= 7 else "0.1.0-dev"


def config_hash(settings) -> str:
    safe = settings.model_dump(mode="json", exclude={"llm_api_key"})
    return hashlib.sha256(json.dumps(safe, sort_keys=True).encode()).hexdigest()


def build_report(job) -> RunReport:
    """job is the finished Orchestrator; every number comes from the ledger, the companies or the store."""
    ledger = job.ledger.snapshot()
    outcomes = Counter(company.status.value for company in job.companies.values())
    return RunReport(
        job_id=job.job_id,
        mode=job.job_mode,
        started_at=job.started_at,
        ended_at=job.ended_at,
        duration_seconds=int((job.ended_at - job.started_at).total_seconds()),
        company_count=len(job.companies),
        outcomes=dict(outcomes),
        requests=RequestCounts(total=ledger["total_outbound_requests"], by_kind=ledger["requests_by_kind"]),
        llm_calls=ledger["llm_calls"],
        input_tokens=ledger["input_tokens"],
        output_tokens=ledger["output_tokens"],
        tokens_estimated=False,
        estimated_cost_usd=Decimal(ledger["estimated_cost_usd"]),
        cost_limit_usd=COST_LIMIT_USD,
        time_limit_min=DAILY_TIME_LIMIT_MIN if job.job_mode == "daily_test" else None,
        stop_reason=job.stop_reason,
        flags=RunFlags(
            soft_cap_reached=ledger["soft_cap_reached"],
            brake_tripped=ledger["brake_tripped"],
            kill_switch_tripped=ledger["kill_switch_tripped"],
            plan_a_outage_detected=job.registry.plan_c,
        ),
        plan_b_used_count=ledger["requests_by_kind"].get("plan_b", 0),
        rejections_by_reason=job.store.rejection_counts(job.job_id),
        checkpoint={"path": "checkpoints/latest.json", "sequence": job.sequence},
        config_hash=config_hash(job.settings),
        code_version=code_version(),
    )


def write_report(output_dir: Path, report: RunReport) -> Path:
    data = report.model_dump(mode="json")
    data["estimated_cost_usd"] = f"{report.estimated_cost_usd:.4f}"
    path = Path(output_dir) / "run_report.json"
    temp = path.with_name(path.name + ".tmp")
    with open(temp, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp, path)
    return path
