import argparse
import asyncio
from datetime import datetime, timezone

from app.application.access import AccessEvaluationService, AccessKeyCreate, AccessKeyEntitlementTemplate, AccessKeyService
from app.core.config import get_settings
from app.infrastructure.access import SqlAlchemyAccessRepository
from app.infrastructure.bootstrap import close_infrastructure, init_infrastructure


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="CycleSync access keys utility")
    sub = parser.add_subparsers(dest="command", required=True)

    create_cmd = sub.add_parser("create")
    create_cmd.add_argument("--key-code", required=True)
    create_cmd.add_argument("--entitlement", action="append", required=True, help="Repeatable entitlement code")
    create_cmd.add_argument("--max-redemptions", type=int, default=1)
    create_cmd.add_argument("--expires-at", default=None, help="ISO UTC datetime")
    create_cmd.add_argument("--duration-days", type=int, default=None, help="Optional fixed duration for all entitlements")
    create_cmd.add_argument("--source", default="manual")
    create_cmd.add_argument("--notes", default=None)

    disable_cmd = sub.add_parser("disable")
    disable_cmd.add_argument("--key-code", required=True)

    inspect_cmd = sub.add_parser("inspect")
    inspect_cmd.add_argument("--key-code", required=True)

    list_redemptions_cmd = sub.add_parser("list-redemptions")
    list_redemptions_cmd.add_argument("--key-code", required=True)

    return parser


async def _run(args: argparse.Namespace) -> None:
    settings = get_settings()
    infra = await init_infrastructure(
        postgres_dsn=settings.postgres_dsn,
        redis_dsn=settings.redis_dsn,
        meilisearch_url=settings.meilisearch_url,
        meilisearch_api_key=settings.meilisearch_api_key,
        meilisearch_index=settings.meilisearch_index,
    )
    repo = SqlAlchemyAccessRepository(infra.db_session_factory)
    access_service = AccessEvaluationService(repository=repo)
    key_service = AccessKeyService(repository=repo, evaluator=access_service)

    try:
        if args.command == "create":
            expires_at = datetime.fromisoformat(args.expires_at) if args.expires_at else None
            templates = tuple(
                AccessKeyEntitlementTemplate(
                    entitlement_code=code,
                    grant_duration_days=args.duration_days,
                    grant_status_template="active",
                )
                for code in args.entitlement
            )
            key = await key_service.create_key(
                AccessKeyCreate(
                    key_code=args.key_code,
                    max_redemptions=args.max_redemptions,
                    expires_at=expires_at,
                    created_by_source=args.source,
                    notes=args.notes,
                    entitlements=templates,
                ),
                now_utc=datetime.now(timezone.utc),
            )
            print(f"created key={key.key_code} id={key.key_id} entitlements={','.join(e.entitlement_code for e in key.entitlements)}")
            return

        if args.command == "disable":
            key = await key_service.disable_key(key_code=args.key_code)
            print(f"disabled key={key.key_code} status={key.status}")
            return

        if args.command == "inspect":
            key = await key_service.inspect_key(key_code=args.key_code)
            if key is None:
                print("not found")
                return
            print(
                f"key={key.key_code} status={key.status} redeemed={key.redeemed_count}/{key.max_redemptions} "
                f"expires_at={key.expires_at} entitlements={[e.entitlement_code for e in key.entitlements]}"
            )
            return

        rows = await key_service.list_redemptions(key_code=args.key_code)
        if not rows:
            print("no redemptions")
            return
        for row in rows:
            print(
                f"{row.redemption_id} user={row.user_id} status={row.result_status} "
                f"reason={row.result_reason_code} grants={[str(g) for g in row.created_grant_ids]}"
            )
    finally:
        await close_infrastructure(infra)


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
