# morphoLogic

## morphoLogicEngine

### File structure

morphoLogicEngine/
├── config/             # Configuration files (settings.json, .env, etc.)
├── deployment/         # Docker, CI/CD, Kubernetes, etc.
│   ├── docker/
├── logs/               # Stores server logs
├── morphologic_server/      # Game server package
│   ├── services/            # Kafka Consumers then handing over tasks to workers
│   ├── db/             # Database models and connections
│   ├── game_logic/     # Game mechanics, inventory, etc.
│   ├── network/        # Kafka Producers and Consumers handlers
│   ├── utils/          # Utilities (logger, helpers)
│   ├── __init__.py     # Package entry point
│   ├── main.py         # Starts the server
├── tests/              # Unit & integration tests
├── requirements.txt    # Dependencies
├── .gitignore          # Ignore unnecessary files
└── README.md           # This documentation

### Setup on a new machine

Six steps from a fresh clone to a running shell. Detailed sections for
each piece live further down in this README — this is the linear
end-to-end path.

```bash
# 1. Make sure Docker is installed and running.
docker --version

# 2. Bring up the local database (creates the volume, runs PostGIS init).
cd morphoLogicEngine/deployment/docker
docker compose up -d postgres
docker compose ps    # wait until status shows "healthy"

# 3. Install the Python project (see "Building morphoLogicEngine CLI" below).
cd ../..             # back to morphoLogicEngine/
python -m venv .venv
source .venv/bin/activate
pip install --upgrade hatch
hatch build
pip install -e .

# 4. Configure .env to point at the local DB.
cd src/morphologic_server
cp .env.template .env       # if not already there
# edit .env so DB_ADDRESS reads:
#   morphoLogicServer:morphoLogicTEST@localhost:5436/morphoLogicDB
# and fill in KAFKA_SERVER as appropriate.

# 5. Apply schema migrations.
alembic upgrade head

# 6a. Fresh world from the seed script:
morphologic seed

# 6b. OR restore a dump from another machine (see pg_dump/pg_restore below):
pg_restore \
  -h localhost -p 5436 \
  -U morphoLogicServer \
  -d morphoLogicDB \
  --clean --if-exists --no-owner --no-privileges \
  morphologic-YYYYMMDD.dump

# 7. Verify.
morphologic shell
```

After this initial setup, daily use is just `docker compose up -d postgres`
(if the DB container isn't already running) and `morphologic shell` or
`morphologic start`.

### Building morphoLogicEngine CLI

In main morphoLogicEngine folder:

```bash
pip install --upgrade hatch
hatch build
pip install -e .`
```

### PostgreSQL with PostGIS

A `docker-compose.yml` at `morphoLogicEngine/deployment/docker/` defines a
local PostGIS service with the same credentials and port (5436) as the Pi,
so the only difference between local and remote is the host portion of
`DB_ADDRESS`.

#### Quick start (local dev DB)

From `morphoLogicEngine/deployment/docker/`:

```bash
docker compose up -d postgres        # start only the DB in the background
docker compose ps                    # confirm it's healthy
docker compose logs -f postgres      # tail logs (Ctrl-C to detach)
docker compose stop postgres         # stop without removing data
docker compose down                  # stop + remove containers (data persists in named volume)
docker compose down -v               # nuke everything including the data volume
```

After the container is up, point your `.env` at it:

```ini
# src/morphologic_server/.env
DB_ADDRESS = "morphoLogicServer:morphoLogicTEST@localhost:5436/morphoLogicDB"
```

Then prepare schema and seed data:

```bash
cd morphoLogicEngine/src/morphologic_server
alembic upgrade head        # create tables
morphologic seed            # populate test world
```

#### Switching between local and Pi

Keep both lines in `.env` and comment whichever you don't need:

```ini
DB_ADDRESS = "morphoLogicServer:morphoLogicTEST@localhost:5436/morphoLogicDB"
# DB_ADDRESS = "morphoLogicServer:morphoLogicTEST@95.160.189.212:5436/morphoLogicDB"
```

Port and credentials are identical — only the host changes.

#### Full stack in containers

`docker compose up -d` starts postgres + kafka + the server itself. The
server inside the network reaches postgres at `postgres:5432` (container
DNS), not `localhost:5436`. The compose file injects the correct
`DB_ADDRESS` for that case via service-level `environment:` — your `.env`
is not consulted when the server runs in the container.

#### What the volume holds

The named volume `morphologic_pgdata` keeps the cluster data across
`docker compose down`. To wipe everything and start fresh:

```bash
docker compose down -v
```

`-v` removes named volumes. Use it when migrations have diverged badly or
you want a guaranteed-clean slate.

### Sharing data between machines (pg_dump / pg_restore)

When you need the *exact* same database content on another machine —
debugging a specific bug, sharing a save with someone, snapshotting before
a risky migration — use `pg_dump` to export and `pg_restore` to import.
This is a one-shot operation, not continuous replication.

#### Dump from a running source

The custom format (`-Fc`) is compressed, restorable in parallel, and lets
you pick which tables to restore selectively if needed.

```bash
# Dump from local dev DB
pg_dump \
  -h localhost -p 5436 \
  -U morphoLogicServer \
  -d morphoLogicDB \
  -Fc \
  -f morphologic-$(date +%Y%m%d).dump

# Dump from the Pi
pg_dump \
  -h 95.160.189.212 -p 5436 \
  -U morphoLogicServer \
  -d morphoLogicDB \
  -Fc \
  -f morphologic-pi-$(date +%Y%m%d).dump
```

You'll be prompted for the password. To avoid the prompt, set
`PGPASSWORD=morphoLogicTEST` in the environment for that command, or use a
[`~/.pgpass` file](https://www.postgresql.org/docs/current/libpq-pgpass.html).

#### Restore into a target

`pg_restore` writes into an existing database. Make sure the target DB
exists and is empty (or use `--clean` to drop existing objects first).

```bash
# Restore into local dev DB (assumes container is up)
pg_restore \
  -h localhost -p 5436 \
  -U morphoLogicServer \
  -d morphoLogicDB \
  --clean --if-exists \
  --no-owner --no-privileges \
  morphologic-20260510.dump
```

Flag rationale:

- `--clean --if-exists` — drop existing tables/indexes before restoring.
  Use this on an existing DB you want to overwrite.
- `--no-owner --no-privileges` — strip ownership/grant statements so the
  restore doesn't fail if user names differ between source and target.

#### Wipe-and-recreate alternative

For a totally clean slate without juggling `--clean` flags, drop and
recreate the DB before restoring. The compose container exposes `psql`:

```bash
docker compose exec postgres \
  psql -U morphoLogicServer -d postgres \
       -c "DROP DATABASE IF EXISTS \"morphoLogicDB\";" \
       -c "CREATE DATABASE \"morphoLogicDB\" OWNER \"morphoLogicServer\";"

pg_restore \
  -h localhost -p 5436 \
  -U morphoLogicServer \
  -d morphoLogicDB \
  --no-owner --no-privileges \
  morphologic-20260510.dump
```

#### Tip: dump only what changed

If your seed scripts produce reproducible base data, you only need to
share the *delta* — the rows you've added or changed during play. Dump
just the relevant tables:

```bash
pg_dump -h localhost -p 5436 -U morphoLogicServer -d morphoLogicDB \
  -Fc \
  -t game_objects -t characters -t character_souls \
  -f morphologic-state-only.dump
```

Restore on the destination after running migrations + seed. Smaller
dumps, faster sync, and you avoid clobbering schema differences if one
machine is mid-migration.

#### Kafka

Currectly testing on [bitnami/kafka Docker Image](https://hub.docker.com/r/bitnami/kafka)

### CMD

The package name is `morphologic-server`, but the name of the program is `morphoLogic`.

- `morphologic start` — starts the server
  - `-l` or `--log` — enable logging
- `morphologic shell` — drop into async-aware interactive shell without running the server
- `morphologic seed` — populatea the database with test objects and areas

### CLI

The CLI has some basic functions. When the morphoLogic Server is run by `morphologic start` the CLI will start altogether.

- `stop` — a command to stop the server
- `detach` — detaches (turns off) the CLI, the server keeps running
- `debug` — runs **debugpy** at port `5678`
- `shell` — drop into async-aware interactive shell. Logging is paused
  - `quit()` to turn off the shell (logging will resume if was enabled)

## morphoLogicClient

Built on Godot
Using moonythedream/godot-kafka-extension for Kafka connection.
