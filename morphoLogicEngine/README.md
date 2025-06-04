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

# Building morphoLogicEngine CLI
In main morphoLogicEngine folder:

`pip install --upgrade hatch
hatch build
pip install -e .`


# PostgreSQL with PostGIS
## Docker

``docker run --name morphoLogic_postgres -e POSTGRES_PASSWORD=trollpassword -p 5432:5432 -d postgis/postgis
