from __future__ import annotations

from constants.routes import ROUTES


def route_config(slug: str | None) -> dict | None:
    if not slug:
        return None
    return ROUTES.get(slug)


def route_title_for_slug(slug: str | None, fallback: str = "") -> str:
    config = route_config(slug)
    if config:
        return config["title"]
    return (fallback or slug or "").strip()


def route_short_title_for_slug(slug: str | None, fallback: str = "") -> str:
    config = route_config(slug)
    if config:
        return config["short_title"]
    return (fallback or slug or "").strip()


def route_title_for_model(route) -> str:
    return route_title_for_slug(getattr(route, "slug", None), getattr(route, "name", ""))


def target_slugs_for_route(slug: str | None) -> list[str]:
    config = route_config(slug)
    if not config:
        return [slug] if slug else []
    return list(config.get("target_route_slugs") or [config["slug"]])


def primary_db_slug_for_route(slug: str | None) -> str | None:
    config = route_config(slug)
    if not config:
        return slug
    return config.get("db_slug") or config["slug"]


def route_payload(slug: str) -> dict | None:
    config = route_config(slug)
    if not config:
        return None
    return {
        "route_slug": config["slug"],
        "route_title": config["title"],
        "target_route_slugs": target_slugs_for_route(config["slug"]),
    }
