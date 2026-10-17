import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

import httpx

from agent_engine.config import load_settings
from agent_engine.errors import ConfigError, InvalidInput
from agent_engine.input_processor import parse_input
from agent_engine.logging_setup import setup_logging
from agent_engine.orchestrator import Orchestrator
from agent_engine.registry_client import REGISTRY_TIMEOUT_S, RegistryClient
from governor.budget_ledger import BudgetLedger
from governor.rate_limiter import SlidingWindowLimiter
from governor.time_kill_switch import TimeKillSwitch
from storage.store import StoreError, open_store

log = logging.getLogger("signalpost.cli")


async def run_job(settings, orgnrs, *, pass1_only=False, resume=False, transport=None,
                  store=None, enrich=None) -> Orchestrator:
    ledger = BudgetLedger(
        soft_cap=settings.soft_cap_requests,
        brake=settings.brake_requests,
        per_company_cap=settings.per_company_cap,
        limiter=SlidingWindowLimiter(settings.llm_rpm),
    )
    async with httpx.AsyncClient(transport=transport, timeout=REGISTRY_TIMEOUT_S) as http:
        hooks = {"enrich": enrich} if enrich else {}
        orchestrator = Orchestrator(settings, RegistryClient(http, ledger), ledger, TimeKillSwitch(),
                                    store=store, **hooks)
        await orchestrator.run(orgnrs, pass1_only=pass1_only, resume=resume)
    if pass1_only:
        write_pass1_results(Path(settings.output_dir), orchestrator)
    return orchestrator


def write_pass1_results(output_dir: Path, orchestrator: Orchestrator) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "registry_only_results.jsonl"
    with open(path, "w", encoding="utf-8") as handle:
        for company in orchestrator.companies.values():
            row = {"orgnr": company.orgnr, "status": company.status.value}
            dossier = company.dossier
            if dossier:
                revenue = next((r for r in dossier.financial_summary if r.metric == "revenue"), None)
                row.update({
                    "legal_name": dossier.legal_name,
                    "registry_status": dossier.registry_status,
                    "website_url": dossier.website_url,
                    "roles": len(dossier.roles),
                    "revenue_nok": str(revenue.amount_base) if revenue and revenue.amount_base is not None else None,
                    "flags": [flag.value for flag in dossier.flags],
                })
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="agent_engine.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="process a list of organisation numbers")
    run.add_argument("--input", required=True, type=Path)
    run.add_argument("--pass1-only", action="store_true", help="registry profile only, no website pass")
    run.add_argument("--resume", action="store_true", help="skip companies finished in the last checkpoint")
    args = parser.parse_args(argv)

    setup_logging()
    try:
        settings = load_settings()
        store = open_store(settings.store_mode, settings.output_dir)
        result = parse_input(args.input.read_bytes())
    except (ConfigError, InvalidInput, StoreError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(f"Accepted: {len(result.accepted)}")
    print(f"Rejected: {len(result.rejected)}")
    print(f"Duplicates merged: {result.duplicates_merged}")
    for item in result.rejected:
        print(f"  line {item.line}: {item.value!r} ({item.reason})")
    log.info("input checked", extra={"fields": {"file": str(args.input), "accepted": len(result.accepted)}})
    if not result.accepted:
        return 0

    orchestrator = asyncio.run(run_job(settings, result.accepted, pass1_only=args.pass1_only,
                                       resume=args.resume, store=store))
    summary = orchestrator.summary()
    print(f"Job {summary['job_id']}: {summary['status']} (stop reason: {summary['stop_reason']})")
    for status, count in sorted(summary["outcomes"].items()):
        print(f"  {status}: {count}")
    print(f"Requests used: {summary['requests']}")
    print(f"Output written to {settings.output_dir}/ (dossiers.jsonl, rejections.jsonl, run_report.json)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
