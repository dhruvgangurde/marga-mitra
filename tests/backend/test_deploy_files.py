from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def test_compose_runs_db_api_and_caddy():
    compose = yaml.safe_load((ROOT / "docker-compose.prod.yml").read_text(encoding="utf-8"))
    services = compose["services"]
    assert set(services) == {"db", "api", "caddy"}
    db, api, caddy = services["db"], services["api"], services["caddy"]
    assert db["image"] == "postgis/postgis:17-3.5"
    assert db["healthcheck"]["test"] == ["CMD-SHELL", "pg_isready -U margamitra -d margamitra"]
    assert db["volumes"] == ["pgdata:/var/lib/postgresql/data"]
    assert api["environment"]["DATABASE_URL"] == "postgresql+psycopg://margamitra:${POSTGRES_PASSWORD}@db:5432/margamitra"
    assert api["depends_on"] == {"db": {"condition": "service_healthy"}}
    assert api["volumes"] == ["uploads:/app/uploads"]
    assert caddy["image"] == "caddy:2.10-alpine"
    assert caddy["ports"] == ["80:80", "443:443", "443:443/udp"]
    assert caddy["volumes"] == ["./Caddyfile:/etc/caddy/Caddyfile:ro", "caddy_data:/data", "caddy_config:/config"]
    assert {s["restart"] for s in services.values()} == {"unless-stopped"}
    assert set(compose["volumes"]) == {"pgdata", "uploads", "caddy_data", "caddy_config"}


def test_caddy_docker_files():
    assert "reverse_proxy api:8000" in (ROOT / "Caddyfile").read_text(encoding="utf-8")
    assert (ROOT / "Dockerfile").read_text(encoding="utf-8").startswith("FROM python:3.12-slim")
    assert {".env", "tests"} <= set((ROOT / ".dockerignore").read_text(encoding="utf-8").split())
