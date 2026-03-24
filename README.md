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

### Building morphoLogicEngine CLI

In main morphoLogicEngine folder:

```bash
pip install --upgrade hatch
hatch build
pip install -e .`
```

### PostgreSQL with PostGIS

#### Docker

`docker run --name morphoLogic_postgres -e POSTGRES_PASSWORD=trollpassword -p 5432:5432 -d postgis/postgis`

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
