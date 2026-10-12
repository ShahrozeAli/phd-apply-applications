from app.database import Base, SessionLocal, engine
from app.services.discovery import run_discovery
from app.services.profile_service import get_or_create_profile


def main() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        get_or_create_profile(db)
        result = run_discovery(db)
        print(result)
    finally:
        db.close()


if __name__ == "__main__":
    main()
