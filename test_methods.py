import unittest
import uuid
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from main import (
    Base, Player, Boost, BoostType, Level, Prize, LevelPrize, PlayerLevel, PlayerPrize
)


class TestPlayerFunctions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # --- Настройка in-memory базы ---
        cls.engine = create_engine("sqlite:///:memory:", echo=False)
        cls.SessionLocal = sessionmaker(bind=cls.engine)
        Base.metadata.create_all(bind=cls.engine)

        # --- Создаём сессию ---
        cls.session = cls.SessionLocal()

        # --- Создаём игрока и базовые объекты ---
        cls.player = Player()
        cls.session.add(cls.player)

        cls.double_points = Boost.create(BoostType.DOUBLE_POINTS)
        cls.session.add(cls.double_points)

        cls.level = Level(title="Test Level", order=1)
        cls.prize = Prize(title="Test Prize")
        cls.session.add_all([cls.level, cls.prize])
        cls.session.commit()

        cls.level_prize = LevelPrize(level_id=cls.level.id, prize_id=cls.prize.id)
        cls.session.add(cls.level_prize)
        cls.session.commit()

    @classmethod
    def tearDownClass(cls):
        cls.session.close()
        cls.engine.dispose()

    def test_login_increases_points(self):
        initial_points = self.player.points
        self.player.login()
        self.assertEqual(self.player.points, initial_points + 10)
        self.assertIsNotNone(self.player.first_login)
        self.assertIsNotNone(self.player.last_login)

    def test_add_boost(self):
        # Добавляем буст игроку
        self.player.add_boost(self.session, boost_id=self.double_points.id, amount=3)
        self.session.commit()
        # Проверяем, что буст начислен
        pb = self.session.query(PlayerPrize).filter_by(player_id=self.player.id).all()
        self.assertEqual(len(self.player.boosts), 1)
        self.assertEqual(self.player.boosts[0].amount, 3)

        # Добавляем ещё раз тот же буст
        self.player.add_boost(self.session, boost_id=self.double_points.id, amount=2)
        self.session.commit()
        self.assertEqual(self.player.boosts[0].amount, 5)

    def test_give_prizes_for_completed_level(self):
        # Сначала уровень не пройден → приз не выдаётся
        self.player.give_prizes_for_level(self.session, self.level.id)
        self.session.commit()
        self.assertEqual(len(self.player.prizes), 0)

        # Пройденный уровень → приз выдаётся
        pl = PlayerLevel(player_id=self.player.id, level_id=self.level.id, completed=datetime.utcnow(), score=100)
        self.session.add(pl)
        self.session.commit()

        self.player.give_prizes_for_level(self.session, self.level.id)
        self.session.commit()
        self.assertEqual(len(self.player.prizes), 1)
        self.assertEqual(self.player.prizes[0].prize_id, self.prize.id)


if __name__ == "__main__":
    unittest.main()
