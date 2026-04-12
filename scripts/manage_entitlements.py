import argparse
import asyncio
from datetime import datetime, timezone

from app.application.access import AccessEvaluationService
from app.application.access.schemas import EntitlementGrantCreate
from app.core.config import get_settings
from app.infrastructure.access import SqlAlchemyAccessRepository
from app.infrastructure.bootstrap import close_infrastructure, init_infrastructure


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="CycleSync entitlement grant/revoke/list utility")
    sub = parser.add_subparsers(dest="command", required=True)

    grant = sub.add_parser("grant")
    grant.add_argument("--user-id", required=True)
    grant.add_argument("--entitlement", required=True)
    grant.add_argument("--source", default="manual")
    grant.add_argument("--expires-at", default=None, help="ISO UTC datetime, e.g. 2026-04-30T00:00:00+00:00")
    grant.add_argument("--source-ref", default=None)
    grant.add_argument("--notes", default=None)

    revoke = sub.add_parser("revoke")
    revoke.add_argument("--user-id", required=True)
    revoke.add_argument("--entitlement", required=True)
    revoke.add_argument("--source", default="manual")
    revoke.add_argument("--reason", default=None)
    revoke.add_argument("--source-ref", default=None)

    list_cmd = sub.add_parser("list")
    list_cmd.add_argument("--user-id", required=True)
    list_cmd.add_argument("--active-only", action="store_true")
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
    service = AccessEvaluationService(repository=repo)

    try:
        if args.command == "grant":
            expires_at = datetime.fromisoformat(args.expires_at) if args.expires_at else None
            grant = await service.grant(
                EntitlementGrantCreate(
                    user_id=args.user_id,
                    entitlement_code=args.entitlement,
                    granted_by_source=args.source,
                    expires_at=expires_at,
                    source_ref=args.source_ref,
                    notes=args.notes,
                ),
                now_utc=datetime.now(timezone.utc),
            )
            print(f"granted: id={grant.grant_id} code={grant.entitlement_code} user={grant.user_id}")
            return

        if args.command == "revoke":
            count = await service.revoke(
                user_id=args.user_id,
                entitlement_code=args.entitlement,
                revoked_by_source=args.source,
                reason=args.reason,
                source_ref=args.source_ref,
            )
            print(f"revoked: {count}")
            return

        rows = await service.list_user_grants(user_id=args.user_id, only_active=args.active_only)
        if not rows:
            print("no grants")
            return
        for row in rows:
            print(
                f"{row.grant_id} | {row.entitlement_code} | {row.grant_status} | "
                f"source={row.granted_by_source} | expires_at={row.expires_at}"
            )
    finally:
        await close_infrastructure(infra)


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
