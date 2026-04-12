import argparse
import asyncio
from datetime import datetime, timezone

from app.application.commerce import CheckoutService, CouponCreate, FreePaymentProvider, PaymentProviderRegistry
from app.core.config import get_settings
from app.infrastructure.bootstrap import close_infrastructure, init_infrastructure
from app.infrastructure.commerce import SqlAlchemyCommerceRepository


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="CycleSync coupons utility")
    sub = parser.add_subparsers(dest="command", required=True)

    create_cmd = sub.add_parser("create")
    create_cmd.add_argument("--code", required=True)
    create_cmd.add_argument("--discount-type", required=True, choices=["percent", "fixed"])
    create_cmd.add_argument("--discount-value", required=True, type=int)
    create_cmd.add_argument("--currency", default=None)
    create_cmd.add_argument("--valid-from", default=None, help="ISO UTC datetime")
    create_cmd.add_argument("--valid-to", default=None, help="ISO UTC datetime")
    create_cmd.add_argument("--max-redemptions-total", type=int, default=None)
    create_cmd.add_argument("--max-redemptions-per-user", type=int, default=None)
    create_cmd.add_argument("--notes", default=None)

    disable_cmd = sub.add_parser("disable")
    disable_cmd.add_argument("--code", required=True)

    inspect_cmd = sub.add_parser("inspect")
    inspect_cmd.add_argument("--code", required=True)

    list_redemptions_cmd = sub.add_parser("list-redemptions")
    list_redemptions_cmd.add_argument("--code", required=True)

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

    try:
        repo = SqlAlchemyCommerceRepository(infra.db_session_factory)
        service = CheckoutService(
            repository=repo,
            provider_registry=PaymentProviderRegistry({"free": FreePaymentProvider()}, tuple(p.strip() for p in settings.commerce_declared_providers.split(",") if p.strip())),
            commerce_mode=settings.commerce_mode,
        )

        if args.command == "create":
            coupon = await service.create_coupon(
                CouponCreate(
                    code=args.code,
                    discount_type=args.discount_type,
                    discount_value=args.discount_value,
                    currency=args.currency,
                    valid_from=datetime.fromisoformat(args.valid_from) if args.valid_from else None,
                    valid_to=datetime.fromisoformat(args.valid_to) if args.valid_to else None,
                    max_redemptions_total=args.max_redemptions_total,
                    max_redemptions_per_user=args.max_redemptions_per_user,
                    notes=args.notes,
                ),
                now_utc=datetime.now(timezone.utc),
            )
            print(f"created coupon={coupon.code} id={coupon.coupon_id} status={coupon.status}")
            return

        if args.command == "disable":
            coupon = await service.disable_coupon(coupon_code=args.code, now_utc=datetime.now(timezone.utc))
            print(f"disabled coupon={coupon.code} status={coupon.status}")
            return

        if args.command == "inspect":
            coupon = await service.inspect_coupon(coupon_code=args.code)
            if coupon is None:
                print("not found")
                return
            print(
                f"coupon={coupon.code} status={coupon.status} redeemed={coupon.redeemed_count}/{coupon.max_redemptions_total} "
                f"discount={coupon.discount_type}:{coupon.discount_value} currency={coupon.currency}"
            )
            return

        rows = await service.list_coupon_redemptions(coupon_code=args.code)
        if not rows:
            print("no redemptions")
            return
        for row in rows:
            print(
                f"{row.redemption_id} checkout={row.checkout_id} user={row.user_id} status={row.result_status} "
                f"reason={row.result_reason_code} discount={row.discount_amount} total_after={row.final_total_after_discount}"
            )
    finally:
        await close_infrastructure(infra)


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
