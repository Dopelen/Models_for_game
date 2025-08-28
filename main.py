import uuid
import csv
from datetime import datetime
from enum import Enum as PyEnum
from typing import Optional

from sqlalchemy import (
    Enum as SqlEnum,
    Column,
    UUID,
    Integer,
    String,
    DateTime,
    ForeignKey,
    CheckConstraint,
    Index,
    select,
    exists
)
from sqlalchemy.orm import declarative_base, relationship, Session

Base = declarative_base()

class BoostType(PyEnum):
    """Типы бонусов с описанием."""
    DOUBLE_POINTS = ("double_points", "x2 к очкам")
    SPEED = ("speed", "ускорение")
    SHIELD = ("shield", "щит от потерь")

    def __init__(self, value, description):
        self._value_ = value
        self.description = description

class Player(Base):
    __tablename__ = "players"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    first_login = Column(DateTime)
    last_login = Column(DateTime)
    points = Column(Integer, default=0, nullable=False)

    boosts = relationship("PlayerBoost", back_populates="player", cascade="all, delete-orphan")
    levels = relationship("PlayerLevel", back_populates="player", cascade="all, delete-orphan")
    prizes = relationship("PlayerPrize", back_populates="player", cascade="all, delete-orphan")

    def login(self):
        """Начисление очков за ежедневный вход."""
        now = datetime.utcnow()
        if not self.first_login:
            self.first_login = now

        if not self.last_login or self.last_login.date() < now.date():
            self.points += 10

        self.last_login = now

    def add_boost(self, session: Session, boost_id: uuid.UUID, amount: int = 1):
        """
        Начисление бонуса игроку.
        """
        pb = session.get(PlayerBoost, (self.id, boost_id))
        if pb:
            pb.amount += amount
        else:
            session.add(PlayerBoost(
                player_id=self.id,
                boost_id=boost_id,
                amount=amount,
                created_at=datetime.utcnow()
            ))

    def give_prizes_for_level(self, session: Session, level_id: uuid.UUID):
        """
        Выдаёт игроку все призы за уровень, если уровень пройден.
        """
        pl = session.get(PlayerLevel, (self.id, level_id))
        if not pl or not pl.completed:
            return  # уровень не пройден → призы не выдаём

        prizes = session.scalars(
            select(Prize).join(LevelPrize).where(LevelPrize.level_id == level_id)
        ).all()

        for prize in prizes:
            already = session.scalar(
                exists().where(
                    PlayerPrize.player_id == self.id,
                    PlayerPrize.prize_id == prize.id
                ).select()
            )
            if not already:
                session.add(PlayerPrize(
                    player_id=self.id,
                    prize_id=prize.id,
                    received_at=datetime.utcnow()
                ))

class Boost(Base):
    __tablename__ = "boosts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    type = Column(SqlEnum(BoostType), nullable=False, unique=True)
    description = Column(String, nullable=False)

    player_boosts = relationship("PlayerBoost", back_populates="boost", cascade="all, delete-orphan")

    @classmethod
    def create(cls, boost_type: BoostType):
        """Создание нового бонуса с автоматическим описанием."""
        return cls(type=boost_type, description=boost_type.description)

class PlayerBoost(Base):
    __tablename__ = "player_boosts"

    player_id = Column(UUID(as_uuid=True), ForeignKey("players.id", ondelete="CASCADE"), primary_key=True)
    boost_id = Column(UUID(as_uuid=True), ForeignKey("boosts.id", ondelete="CASCADE"), primary_key=True)
    amount = Column(Integer, default=1, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    player = relationship("Player", back_populates="boosts")
    boost = relationship("Boost", back_populates="player_boosts")

    __table_args__ = (
        CheckConstraint("amount >= 0", name="check_playerboost_amount_nonnegative"),
        Index("ix_playerboost_player", "player_id"),
        Index("ix_playerboost_boost", "boost_id"),
    )

class Level(Base):
    __tablename__ = "levels"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(100), nullable=False)
    order = Column(Integer, default=0, nullable=False)

    player_levels = relationship("PlayerLevel", back_populates="level", cascade="all, delete-orphan")
    prizes = relationship("LevelPrize", back_populates="level", cascade="all, delete-orphan")

class Prize(Base):
    __tablename__ = "prizes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(100), nullable=False)

    level_prizes = relationship("LevelPrize", back_populates="prize", cascade="all, delete-orphan")

class PlayerLevel(Base):
    __tablename__ = "player_levels"

    player_id = Column(UUID(as_uuid=True), ForeignKey("players.id", ondelete="CASCADE"), primary_key=True)
    level_id = Column(UUID(as_uuid=True), ForeignKey("levels.id", ondelete="CASCADE"), primary_key=True)
    completed = Column(DateTime, nullable=True)
    score = Column(Integer, default=0, nullable=False)

    player = relationship("Player", back_populates="levels")
    level = relationship("Level", back_populates="player_levels")

    __table_args__ = (
        CheckConstraint("score >= 0", name="check_playerlevel_score_nonnegative"),
        Index("ix_playerlevel_player", "player_id"),
        Index("ix_playerlevel_level", "level_id"),
        Index("ix_playerlevel_completed", "completed"),
    )

class LevelPrize(Base):
    __tablename__ = "level_prizes"

    level_id = Column(UUID(as_uuid=True), ForeignKey("levels.id", ondelete="CASCADE"), primary_key=True)
    prize_id = Column(UUID(as_uuid=True), ForeignKey("prizes.id", ondelete="CASCADE"), primary_key=True)

    level = relationship("Level", back_populates="prizes")
    prize = relationship("Prize", back_populates="level_prizes")

    __table_args__ = (
        Index("ix_levelprize_level", "level_id"),
        Index("ix_levelprize_prize", "prize_id"),
    )

class PlayerPrize(Base):
    __tablename__ = "player_prizes"

    player_id = Column(UUID(as_uuid=True), ForeignKey("players.id", ondelete="CASCADE"), primary_key=True)
    prize_id = Column(UUID(as_uuid=True), ForeignKey("prizes.id", ondelete="CASCADE"), primary_key=True)
    received_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    player = relationship("Player", back_populates="prizes")
    prize = relationship("Prize")

    __table_args__ = (
        Index("ix_playerprize_player", "player_id"),
        Index("ix_playerprize_prize", "prize_id"),
    )

    # ------------------ Функция экспорта ------------------
def export_player_levels_to_csv(session: Session, file_path: str):
    """
    Экспортирует данные: player_id, название уровня, пройден ли уровень, приз за уровень.
    Для каждого уровня игрока берётся только приз, связанный с этим уровнем.
    """
    with open(file_path, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["player_id", "level_title", "completed", "prize_title"])

        query = session.query(PlayerLevel).join(PlayerLevel.level).outerjoin(Level.prizes).outerjoin(LevelPrize.prize)
        for pl in query.yield_per(1000):
            level_title = pl.level.title
            completed = bool(pl.completed)
            # Берём только первый приз уровня, если он есть
            prize_title: Optional[str] = pl.level.prizes[0].prize.title if pl.level.prizes else ""
            writer.writerow([pl.player_id, level_title, completed, prize_title])