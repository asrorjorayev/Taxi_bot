REGION_TO_TASHKENT_SLUGS = [
    "bagdod_toshkent",
    "rishton_toshkent",
    "buvayda_toshkent",
    "uchkoprik_toshkent",
]

TASHKENT_TO_REGION_SLUGS = [
    "toshkent_bagdod",
    "toshkent_rishton",
    "toshkent_buvayda",
    "toshkent_uchkoprik",
]

DRIVER_MANUAL_TARGET_SLUGS = REGION_TO_TASHKENT_SLUGS + TASHKENT_TO_REGION_SLUGS

REGION_TO_TASHKENT_ROUTE_SLUG = "region_to_tashkent"
TASHKENT_TO_REGION_ROUTE_SLUG = "tashkent_to_region"

ROUTES = {
    "bagdod_toshkent": {
        "slug": "bagdod_toshkent",
        "title": "Bag'dod ➡️ Toshkent",
        "short_title": "Bag'dod",
        "from_city": "Bag'dod",
        "to_city": "Toshkent",
    },
    "rishton_toshkent": {
        "slug": "rishton_toshkent",
        "title": "Rishton ➡️ Toshkent",
        "short_title": "Rishton",
        "from_city": "Rishton",
        "to_city": "Toshkent",
    },
    "buvayda_toshkent": {
        "slug": "buvayda_toshkent",
        "title": "Buvayda ➡️ Toshkent",
        "short_title": "Buvayda",
        "from_city": "Buvayda",
        "to_city": "Toshkent",
    },
    "uchkoprik_toshkent": {
        "slug": "uchkoprik_toshkent",
        "title": "Uchko‘prik ➡️ Toshkent",
        "short_title": "Uchko‘prik",
        "from_city": "Uchko‘prik",
        "to_city": "Toshkent",
    },
    "qoqon_toshkent": {
        "slug": "qoqon_toshkent",
        "title": "Qo'qon ➡️ Toshkent",
        "short_title": "Qo'qon",
        "from_city": "Qo'qon",
        "to_city": "Toshkent",
    },
    "fargona_toshkent": {
        "slug": "fargona_toshkent",
        "title": "Farg'ona ➡️ Toshkent",
        "short_title": "Farg'ona",
        "from_city": "Farg'ona",
        "to_city": "Toshkent",
    },
    "toshkent_bagdod": {
        "slug": "toshkent_bagdod",
        "title": "Toshkent ➡️ Bag'dod",
        "short_title": "Bag'dod",
        "from_city": "Toshkent",
        "to_city": "Bag'dod",
    },
    "toshkent_rishton": {
        "slug": "toshkent_rishton",
        "title": "Toshkent ➡️ Rishton",
        "short_title": "Rishton",
        "from_city": "Toshkent",
        "to_city": "Rishton",
    },
    "toshkent_buvayda": {
        "slug": "toshkent_buvayda",
        "title": "Toshkent ➡️ Buvayda",
        "short_title": "Buvayda",
        "from_city": "Toshkent",
        "to_city": "Buvayda",
    },
    "toshkent_uchkoprik": {
        "slug": "toshkent_uchkoprik",
        "title": "Toshkent ➡️ Uchko‘prik",
        "short_title": "Uchko‘prik",
        "from_city": "Toshkent",
        "to_city": "Uchko‘prik",
    },
    "toshkent_qoqon": {
        "slug": "toshkent_qoqon",
        "title": "Toshkent ➡️ Qo'qon",
        "short_title": "Qo'qon",
        "from_city": "Toshkent",
        "to_city": "Qo'qon",
    },
    "toshkent_fargona": {
        "slug": "toshkent_fargona",
        "title": "Toshkent ➡️ Farg'ona",
        "short_title": "Farg'ona",
        "from_city": "Toshkent",
        "to_city": "Farg'ona",
    },
    REGION_TO_TASHKENT_ROUTE_SLUG: {
        "slug": REGION_TO_TASHKENT_ROUTE_SLUG,
        "title": "Bag'dod, Rishton, Buvayda, Uchko‘prik ➡️ Toshkent",
        "short_title": "Viloyat ➡️ Toshkent",
        "target_route_slugs": REGION_TO_TASHKENT_SLUGS,
        "db_slug": "bagdod_toshkent",
    },
    TASHKENT_TO_REGION_ROUTE_SLUG: {
        "slug": TASHKENT_TO_REGION_ROUTE_SLUG,
        "title": "Toshkent ➡️ Bag'dod, Rishton, Buvayda, Uchko‘prik",
        "short_title": "Toshkent ➡️ Viloyat",
        "target_route_slugs": TASHKENT_TO_REGION_SLUGS,
        "db_slug": "toshkent_bagdod",
    },
}

DRIVER_AUTO_ROUTE_SLUGS = [
    REGION_TO_TASHKENT_ROUTE_SLUG,
    TASHKENT_TO_REGION_ROUTE_SLUG,
]

DATABASE_ROUTE_SLUGS = [
    slug
    for slug, route in ROUTES.items()
    if "from_city" in route and "to_city" in route
]

DEFAULT_DATABASE_ROUTES = [
    (
        route["title"],
        route["slug"],
        route["from_city"],
        route["to_city"],
    )
    for route in (ROUTES[slug] for slug in DATABASE_ROUTE_SLUGS)
]
