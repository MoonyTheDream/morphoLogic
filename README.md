# morphoLogic

## morphoLogicEngine

### Setup on a new machine

Setting up a local anvironment for developing and testing.

#### 1. Bring up the local database and Kafka

```bash
cd morphoLogicEngine/deployment/docker
docker compose up -d postgres kafka
```

#### 2. Install the Python project (check the minimal Python version in pyproject.toml)

```bash
cd ../..    # back to morphoLogicEngine/
python -m venv .venv
source .venv/bin/activate
pip install --upgrade hatch
hatch build
pip install -e .
```

#### 3. Configure .env to point at the local DB

```bash
cd src/morphologic_server
cp .env.template .env       # if not already there
# edit .env so DB_ADDRESS reads:
# morphoLogicServer:morphoLogicTEST@postgres:5432/morphoLogicDB
# and fill in KAFKA_SERVER as appropriate.
```

#### 4. Apply schema migrations

`alembic upgrade head`

#### 5a. Fresh world from the seed script

`morphologic seed`

#### 5b. OR restore a dump from another machine (see pg_dump/pg_restore below)

```bash
pg_restore \
  -h localhost -p 5432 \
  -U <DB_USER> \
  -d <DB_NAME> \
  --clean --if-exists --no-owner --no-privileges \
  morphologic-YYYYMMDD.dump
```

### What the docker volume holds

The named volume `morphologic_pgdata` keeps the cluster data across
`docker compose down`. To wipe everything and start fresh:

```bash
docker compose down -v
```

Use it when migrations have diverged badly or you want a guaranteed-clean slate.


### CMD

The package name is `morphologic-server`, but the name of the program is `morphoLogic`.

- `morphologic start` — starts the server
  - `-l` or `--log` — enable logging
- `morphologic shell` — drop into async-aware interactive shell without running the server
- `morphologic seed` — populate the database with test objects and areas

### CLI

The CLI has some basic functions. When the morphoLogic Engine is run by `morphologic start` the CLI will start altogether.

- `stop` — a command to stop the server
- `detach` — detaches (turns off) the CLI, the server keeps running
- `debug` — runs **debugpy** at port `5678`
- `shell` — drop into async-aware interactive shell. Logging is paused
  - `quit()` to turn off the shell (logging will resume if was enabled)

## morphoLogicClient

Built on Godot
Using moonythedream/godot-kafka-extension for Kafka connection.
