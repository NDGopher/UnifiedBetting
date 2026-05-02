from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, JSON, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import os

Base = declarative_base()

class HighEVAlert(Base):
    __tablename__ = "high_ev_alerts"
    
    id = Column(Integer, primary_key=True)
    event_id = Column(String(50), index=True)
    sport = Column(String(50))
    away_team = Column(String(100))
    home_team = Column(String(100))
    ev_percentage = Column(Float)
    bet_type = Column(String(50))
    odds = Column(String(50))
    nvp = Column(String(50))
    alert_data = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    processed = Column(String(20), default="pending")


class AlertLogRecord(Base):
    __tablename__ = "alert_log_records"

    id = Column(Integer, primary_key=True)
    event_id = Column(String(50), index=True)
    timestamp = Column(String(50), index=True)
    teams = Column(JSON)
    steps = Column(JSON)
    result = Column(String(50))
    ev_summary = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)


# Database setup
def setup_database():
    db_path = os.path.join(os.path.dirname(__file__), 'high_ev_alerts.db')
    engine = create_engine(f'sqlite:///{db_path}')
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)

# Create session factory - lazy initialization
SessionLocal = None

def get_session():
    global SessionLocal
    if SessionLocal is None:
        SessionLocal = setup_database()
    return SessionLocal()


def save_alert_log_record(record: dict):
    """Write an alert log record to the DB. Intended for background thread use."""
    try:
        session = get_session()
        row = AlertLogRecord(
            event_id=record.get("event_id", ""),
            timestamp=record.get("timestamp", ""),
            teams=record.get("teams", {}),
            steps=record.get("steps", []),
            result=record.get("result", ""),
            ev_summary=record.get("ev_summary", []),
        )
        session.add(row)
        session.commit()
        session.close()
    except Exception as exc:
        try:
            session.rollback()
            session.close()
        except Exception:
            pass
        import logging
        logging.getLogger(__name__).error(f"[AlertLogRecord] DB write failed: {exc}")


def get_alert_log_from_db(limit: int = 200, exclude_event_ids: set = None) -> list:
    """Fetch the most recent alert log records from the DB, optionally excluding known event_ids."""
    try:
        session = get_session()
        query = session.query(AlertLogRecord).order_by(AlertLogRecord.created_at.desc()).limit(limit * 2)
        rows = query.all()
        session.close()
        results = []
        for row in rows:
            if exclude_event_ids and row.event_id in exclude_event_ids:
                continue
            results.append({
                "event_id": row.event_id,
                "timestamp": row.timestamp,
                "teams": row.teams or {},
                "steps": row.steps or [],
                "result": row.result,
                "ev_summary": row.ev_summary or [],
            })
            if len(results) >= limit:
                break
        return results
    except Exception as exc:
        import logging
        logging.getLogger(__name__).error(f"[AlertLogRecord] DB read failed: {exc}")
        return []