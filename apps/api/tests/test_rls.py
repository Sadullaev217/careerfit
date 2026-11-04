"""Runs the real migration on Postgres. Needs TEST_DATABASE_URL; it drops and recreates schemas."""

import json
import os
from collections.abc import Iterator
from pathlib import Path

import psycopg
import pytest

DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="TEST_DATABASE_URL not set")

ROOT = Path(__file__).resolve().parents[3] / "supabase"
ALICE = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
BOB = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"

SUPABASE_SHIM = """
drop schema if exists public cascade;
drop schema if exists auth cascade;
create schema public;
create schema auth;
do $$ begin
  if not exists (select from pg_roles where rolname = 'anon') then create role anon; end if;
  if not exists (select from pg_roles where rolname = 'authenticated') then create role authenticated; end if;
end $$;
grant usage on schema public, auth to anon, authenticated;
create table auth.users (id uuid primary key, email text);
create function auth.uid() returns uuid language sql stable as $$
  select nullif(current_setting('request.jwt.claims', true), '')::json ->> 'sub'
$$;
"""


@pytest.fixture
def conn() -> Iterator[psycopg.Connection]:
    assert DATABASE_URL
    with psycopg.connect(DATABASE_URL, autocommit=True) as connection:
        connection.execute(SUPABASE_SHIM.encode())
        for migration in sorted((ROOT / "migrations").glob("*.sql")):
            connection.execute(migration.read_bytes())
        connection.execute((ROOT / "seed.sql").read_bytes())
        connection.execute(
            "insert into auth.users (id, email) values (%s, 'a@example.com'), (%s, 'b@example.com')",
            (ALICE, BOB),
        )
        connection.execute(
            "insert into public.documents (user_id, type, file_name) values (%s, 'resume', 'a.pdf')",
            (ALICE,),
        )
        connection.execute(
            "insert into public.target_roles (user_id, title, region) values (%s, 'Dev', 'US')",
            (ALICE,),
        )
        connection.execute(
            "insert into public.analyses (user_id, score) values (%s, 50)",
            (ALICE,),
        )
        yield connection


def act_as(conn: psycopg.Connection, user_id: str | None) -> None:
    conn.execute("reset role")
    claims = json.dumps({"sub": user_id}) if user_id else ""
    conn.execute("select set_config('request.jwt.claims', %s, false)", (claims,))
    conn.execute("set role " + ("authenticated" if user_id else "anon"))


def count(conn: psycopg.Connection, table: str) -> int:
    row = conn.execute(f"select count(*) from public.{table}").fetchone()
    assert row
    return int(row[0])


USER_TABLES = ["documents", "target_roles", "analyses", "profiles", "subscriptions"]


@pytest.mark.parametrize("table", USER_TABLES)
def test_user_cannot_read_other_users_rows(conn: psycopg.Connection, table: str) -> None:
    act_as(conn, BOB)
    if table in ("profiles", "subscriptions"):
        assert count(conn, table) == 1  # only Bob's own row
    else:
        assert count(conn, table) == 0
    act_as(conn, ALICE)
    assert count(conn, table) == 1


def test_every_public_table_has_rls(conn: psycopg.Connection) -> None:
    rows = conn.execute(
        "select relname from pg_class c join pg_namespace n on n.oid = c.relnamespace "
        "where n.nspname = 'public' and c.relkind = 'r' and not c.relrowsecurity"
    ).fetchall()
    assert rows == []


def test_anon_cannot_read_user_data(conn: psycopg.Connection) -> None:
    act_as(conn, None)
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        count(conn, "documents")


def test_user_cannot_update_or_delete_other_users_rows(conn: psycopg.Connection) -> None:
    act_as(conn, BOB)
    updated = conn.execute("update public.target_roles set title = 'Hacked'")
    deleted = conn.execute("delete from public.documents")
    assert updated.rowcount == 0
    assert deleted.rowcount == 0


def test_user_can_create_own_rows(conn: psycopg.Connection) -> None:
    act_as(conn, BOB)
    conn.execute("insert into public.target_roles (title, region) values ('Dev', 'US')")
    conn.execute("insert into public.documents (type, file_name) values ('resume', 'b.pdf')")
    assert count(conn, "target_roles") == 1
    assert count(conn, "documents") == 1


def test_user_cannot_insert_rows_for_another_user(conn: psycopg.Connection) -> None:
    act_as(conn, BOB)
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        conn.execute(
            "insert into public.target_roles (user_id, title, region) values (%s, 'X', 'US')",
            (ALICE,),
        )


@pytest.mark.parametrize(
    "statement",
    [
        "update public.analyses set score = 100",
        "update public.subscriptions set plan = 'pro'",
        "update public.documents set parsed_text = 'x'",
        "insert into public.skills (name) values ('Fake')",
    ],
)
def test_user_cannot_write_server_owned_data(conn: psycopg.Connection, statement: str) -> None:
    act_as(conn, ALICE)
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        conn.execute(statement.encode())


def test_signup_creates_profile_and_free_subscription(conn: psycopg.Connection) -> None:
    row = conn.execute(
        "select plan from public.subscriptions s join public.profiles p on p.id = s.user_id "
        "where s.user_id = %s",
        (BOB,),
    ).fetchone()
    assert row == ("free",)


def test_deleting_user_removes_all_their_data(conn: psycopg.Connection) -> None:
    conn.execute("delete from auth.users where id = %s", (ALICE,))
    conn.execute("reset role")
    for table in USER_TABLES:
        row = conn.execute(
            f"select count(*) from public.{table} where "
            + ("id" if table == "profiles" else "user_id")
            + " = %s",
            (ALICE,),
        ).fetchone()
        assert row == (0,), table
