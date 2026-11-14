from src.config.database import Base, engine
from src import models
from migrations.schema_evolve import evolve
def migrate():
    Base.metadata.create_all(engine)
    evolve(engine)
if __name__=='__main__':migrate()
