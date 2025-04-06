# Alembic needs
for `pip install psycopg2` the `sudo apt install libpq-dev` is needed  before.
    Note: only when  not async version of alembic template (I don't know how to run that one still)
        The update is I probably don't need async alembic anyway, as it will be run only in CLI. I might need async SQLAlchemy though.
# Create alembic init
- `alembic init alembic` - last one is a folder where it should initiate. The alembic.ini file will be level higher
- `alembic init --template async alembc` is a way to create it with async template
# Revisions
- `alembic revision -m "name of revision`
- `alembic revision --autogenerate -m "name of revision` - autogenerates if in .ini is the proper DeclarativeBase class.
# Upgrades/downgrades
- `alembic upgrade/downgrade <first 3 revision symbols>/+1/-2/head`
    
