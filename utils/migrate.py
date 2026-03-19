import sys
from alembic.config import Config
from alembic import command

def run_migrations():
    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")

if __name__ == "__main__":
    # This is just a helper, ideally you run 'alembic revision --autogenerate' manually
    pass
