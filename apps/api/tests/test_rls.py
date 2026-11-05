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
drop schema if exists storage cascade;
create schema public;
create schema auth;
create schema storage;
create table storage.buckets (
  id text primary key,
  name text not null,
  public boolean,
  file_size_limit bigint,
  allowed_mime_types text[]
);
do $$ begin
  if not exists (select from pg_roles where rolname = 'anon') then create role anon; end if;
  if not exists (select from pg_roles where rolname = 'authenticated') then create role authenticated; end if;
  if not exists (select from pg_roles where rolname = 'service_role') then create role service_role; end if;
end $$;
grant usage on schema public, auth to anon, authenticated;
create table auth.users (id uuid primary key, email text);
create function auth.uid() returns uuid language sql stable as $$
  select (nullif(current_setting('request.jwt.claims', true), '')::json ->> 'sub')::uuid
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
    deleted = conn.execute("delete from public.target_roles")
    assert updated.rowcount == 0
    assert deleted.rowcount == 0


def test_user_can_create_own_rows(conn: psycopg.Connection) -> None:
    act_as(conn, BOB)
    conn.execute("insert into public.target_roles (title, region) values ('Dev', 'US')")
    assert count(conn, "target_roles") == 1


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
        "insert into public.analyses (user_id, score) values (auth.uid(), 100)",
        "select * from public.skill_judgements",
        "select * from public.term_translations",
        "insert into public.term_translations (term, language, translation) values ('a', 'ru', 'b')",
        "update public.skill_judgements set result = '{}'",
        "update public.subscriptions set plan = 'pro'",
        "update public.documents set parsed_text = 'x'",
        "insert into public.skills (name) values ('Fake')",
        "insert into public.documents (type, file_name) values ('resume', 'x.pdf')",
        "delete from public.documents",
    ],
)
def test_user_cannot_write_server_owned_data(conn: psycopg.Connection, statement: str) -> None:
    act_as(conn, ALICE)
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        conn.execute(statement.encode())


def add_extraction(conn: psycopg.Connection, user_id: str) -> str:
    conn.execute("reset role")
    row = conn.execute(
        "insert into public.documents (user_id, type, file_name) "
        "values (%s, 'resume', 'cv.pdf') returning id",
        (user_id,),
    ).fetchone()
    assert row
    document_id = str(row[0])
    conn.execute(
        "insert into public.extracted_profiles (document_id, user_id, data, prompt_version, model) "
        "values (%s, %s, '{}', 'v1', 'm')",
        (document_id, user_id),
    )
    return document_id


def test_extracted_profiles_are_private(conn: psycopg.Connection) -> None:
    add_extraction(conn, ALICE)
    act_as(conn, BOB)
    assert count(conn, "extracted_profiles") == 0
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        conn.execute("update public.extracted_profiles set model = 'x'")
    act_as(conn, ALICE)
    assert count(conn, "extracted_profiles") == 1


def test_clients_cannot_call_the_skill_matcher_directly(conn: psycopg.Connection) -> None:
    vector = "[" + ",".join(["0"] * 384) + "]"
    act_as(conn, ALICE)
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        conn.execute("select * from public.match_skill(%s::extensions.vector)", (vector,))


def test_skill_matcher_returns_nearest_skill(conn: psycopg.Connection) -> None:
    near = "[1," + ",".join(["0"] * 383) + "]"
    far = "[0,1," + ",".join(["0"] * 382) + "]"
    conn.execute("reset role")
    conn.execute(
        "insert into public.skills (name, embedding) values "
        "('near', %s::extensions.vector), ('far', %s::extensions.vector)",
        (near, far),
    )
    row = conn.execute(
        "select name, similarity from public.match_skill(%s::extensions.vector)", (near,)
    ).fetchone()
    assert row is not None
    assert row[0] == "near"
    assert row[1] == pytest.approx(1.0)


def test_deleting_a_resume_removes_its_skills_and_analysis(conn: psycopg.Connection) -> None:
    document_id = add_extraction(conn, ALICE)
    skill = conn.execute("insert into public.skills (name) values ('Temp') returning id").fetchone()
    assert skill
    conn.execute(
        "insert into public.profile_skills (user_id, skill_id, source_document_id) "
        "values (%s, %s, %s)",
        (ALICE, skill[0], document_id),
    )
    conn.execute(
        "insert into public.analyses (user_id, document_id, score) values (%s, %s, 50)",
        (ALICE, document_id),
    )
    conn.execute(
        "insert into public.skill_judgements (document_id, input_key, result) values (%s, 'k', '{}')",
        (document_id,),
    )
    conn.execute("delete from public.documents where id = %s", (document_id,))
    assert conn.execute(
        "select count(*) from public.profile_skills where user_id = %s", (ALICE,)
    ).fetchone() == (0,)
    assert conn.execute(
        "select count(*) from public.extracted_profiles where document_id = %s", (document_id,)
    ).fetchone() == (0,)
    assert conn.execute(
        "select count(*) from public.analyses where document_id = %s", (document_id,)
    ).fetchone() == (0,)
    assert conn.execute(
        "select count(*) from public.skill_judgements where document_id = %s", (document_id,)
    ).fetchone() == (0,)


def add_posting(
    conn: psycopg.Connection,
    source_id: str,
    salary: float | None,
    region: str = "Ontario",
    duplicate_key: str | None = None,
    education: str | None = None,
) -> None:
    conn.execute(
        "insert into public.job_postings (source, source_id, title, region, occupation_code, "
        "salary_min, salary_max, posted_at, duplicate_key, education_level) "
        "values ('test', %s, 'cook', %s, '63200', %s, %s, '2026-10-15', %s, %s)",
        (source_id, region, salary, salary, duplicate_key or source_id, education),
    )


def stats(conn: psycopg.Connection, region: str | None = None) -> dict:
    row = conn.execute("select public.market_stats('63200', %s)", (region,)).fetchone()
    assert row
    return dict(row[0])


def test_market_stats_gives_percentiles_and_sample_size(conn: psycopg.Connection) -> None:
    conn.execute("reset role")
    for index, salary in enumerate((40000, 50000, 60000, 70000, 80000)):
        add_posting(conn, f"j{index}", salary)
    add_posting(conn, "no-pay", None)

    result = stats(conn, "Ontario")
    assert result["sample_size"] == 6
    assert result["salary_sample_size"] == 5
    assert result["salary_median"] == 60000
    assert result["salary_p25"] == 50000
    assert result["salary_p75"] == 70000
    assert result["latest_posting"] == "2026-10-15"


def test_market_stats_counts_repeated_ads_once(conn: psycopg.Connection) -> None:
    conn.execute("reset role")
    add_posting(conn, "real", 40000, duplicate_key="real")
    add_posting(conn, "spam-on", 111360, "Ontario", "spam")
    add_posting(conn, "spam-ab", 111360, "Alberta", "spam")
    add_posting(conn, "spam-bc", 111360, "British Columbia", "spam")

    national = stats(conn)
    assert national["sample_size"] == 2
    assert stats(conn, "Alberta")["sample_size"] == 1


def test_market_stats_filters_by_region(conn: psycopg.Connection) -> None:
    conn.execute("reset role")
    add_posting(conn, "on", 40000, "Ontario")
    add_posting(conn, "ab", 90000, "Alberta")
    assert stats(conn, "Alberta")["salary_median"] == 90000


def test_market_stats_counts_education_levels(conn: psycopg.Connection) -> None:
    conn.execute("reset role")
    add_posting(conn, "a", 40000, education="Bachelor's degree")
    add_posting(conn, "b", 50000, education="Bachelor's degree")
    add_posting(conn, "c", 60000, education="College/CEGEP")
    add_posting(conn, "d", 70000)
    assert stats(conn)["education"] == {"Bachelor's degree": 2, "College/CEGEP": 1}


def test_market_stats_with_no_postings_is_empty(conn: psycopg.Connection) -> None:
    conn.execute("reset role")
    result = stats(conn)
    assert result["sample_size"] == 0
    assert result["salary_median"] is None
    assert result["salary_top_share"] is None
    assert result["education"] == {}


def test_market_stats_reports_how_many_ads_share_one_pay_figure(conn: psycopg.Connection) -> None:
    conn.execute("reset role")
    for index in range(3):
        add_posting(conn, f"same{index}", 75213)
    add_posting(conn, "other", 60000)
    add_posting(conn, "no-pay", None)
    assert stats(conn)["salary_top_share"] == pytest.approx(0.75)


def test_match_occupation_finds_the_nearest_title(conn: psycopg.Connection) -> None:
    near = "[1," + ",".join(["0"] * 383) + "]"
    far = "[0,1," + ",".join(["0"] * 382) + "]"
    conn.execute("reset role")
    conn.execute("insert into public.occupations (code, name) values ('63200', 'Cooks')")
    conn.execute(
        "insert into public.occupation_titles (title, occupation_code, embedding) values "
        "('cook', '63200', %s::extensions.vector), ('baker', '63200', %s::extensions.vector)",
        (near, far),
    )
    row = conn.execute(
        "select title, occupation_name, similarity from public.match_occupation(%s::extensions.vector)",
        (near,),
    ).fetchone()
    assert row is not None
    assert row[:2] == ("cook", "Cooks")
    assert row[2] == pytest.approx(1.0)


def test_match_occupations_lists_each_occupation_once_nearest_first(
    conn: psycopg.Connection,
) -> None:
    near = "[1," + ",".join(["0"] * 383) + "]"
    close = "[1,1," + ",".join(["0"] * 382) + "]"
    far = "[0,1," + ",".join(["0"] * 382) + "]"
    conn.execute("reset role")
    conn.execute(
        "insert into public.occupations (code, name) values "
        "('63200', 'Cooks'), ('62200', 'Chefs'), ('72106', 'Welders')"
    )
    conn.execute(
        "insert into public.occupation_titles (title, occupation_code, embedding) values "
        "('cook', '63200', %s::extensions.vector), ('line cook', '63200', %s::extensions.vector), "
        "('chef', '62200', %s::extensions.vector), ('welder', '72106', %s::extensions.vector)",
        (near, near, close, far),
    )
    rows = conn.execute(
        "select occupation_code, occupation_name, similarity "
        "from public.match_occupations(%s::extensions.vector, 2)",
        (near,),
    ).fetchall()
    assert [row[:2] for row in rows] == [("63200", "Cooks"), ("62200", "Chefs")]
    assert rows[0][2] == pytest.approx(1.0)


@pytest.mark.parametrize(
    "statement",
    [
        "select public.market_stats('63200', null)",
        "select * from public.match_occupation(('[' || repeat('0,', 383) || '0]')::extensions.vector)",
        "select * from public.match_occupations(('[' || repeat('0,', 383) || '0]')::extensions.vector, 5)",
    ],
)
def test_clients_cannot_call_market_functions_directly(
    conn: psycopg.Connection, statement: str
) -> None:
    act_as(conn, ALICE)
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        conn.execute(statement.encode())


@pytest.mark.parametrize(
    "statement",
    [
        "insert into public.occupations (code, name) values ('x', 'Fake')",
        "insert into public.job_postings (source, source_id, title, region) values ('a','b','c','d')",
        "delete from public.occupation_skills",
    ],
)
def test_clients_cannot_change_market_data(conn: psycopg.Connection, statement: str) -> None:
    act_as(conn, ALICE)
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        conn.execute(statement.encode())


def test_signed_in_users_can_read_market_data_but_anonymous_cannot(
    conn: psycopg.Connection,
) -> None:
    conn.execute("reset role")
    conn.execute("insert into public.occupations (code, name) values ('63200', 'Cooks')")
    act_as(conn, ALICE)
    assert count(conn, "occupations") == 1
    act_as(conn, None)
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        count(conn, "occupations")


def test_documents_bucket_is_private(conn: psycopg.Connection) -> None:
    row = conn.execute("select public from storage.buckets where id = 'documents'").fetchone()
    assert row == (False,)


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
