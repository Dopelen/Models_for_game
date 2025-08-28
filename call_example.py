from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from main import (
    Base, Player, Boost, BoostType,
    Level, Prize, LevelPrize, PlayerLevel, PlayerPrize,
    export_player_levels_to_csv
)

# --- Настройка in-memory базы ---
engine = create_engine("sqlite:///:memory:", echo=False)
SessionLocal = sessionmaker(bind=engine)
Base.metadata.create_all(bind=engine)

NUM_PLAYERS = 1000
NUM_LEVELS = 100  # 1000*100 = 100 000 записей PlayerLevel

with SessionLocal() as session:
    # --- Создаём базовые бусты ---
    double_points = Boost.create(BoostType.DOUBLE_POINTS)
    speed = Boost.create(BoostType.SPEED)
    shield = Boost.create(BoostType.SHIELD)
    session.add_all([double_points, speed, shield])
    session.commit()

    # --- Создаём уровни и призы ---
    levels = [Level(title=f"Level {i+1}", order=i+1) for i in range(NUM_LEVELS)]
    prizes = [Prize(title=f"Prize {i+1}") for i in range(NUM_LEVELS)]
    session.add_all(levels + prizes)
    session.commit()

    # --- Привязываем призы к уровням ---
    level_prizes = [LevelPrize(level_id=level.id, prize_id=prize.id)
                    for level, prize in zip(levels, prizes)]
    session.add_all(level_prizes)
    session.commit()

    # --- Создаём игроков ---
    players = [Player() for _ in range(NUM_PLAYERS)]
    session.add_all(players)
    session.commit()

    # --- Начисляем бусты каждому игроку ---
    for player in players:
        player.login()
        player.add_boost(session, boost_id=double_points.id, amount=2)
        player.add_boost(session, boost_id=speed.id, amount=1)
        player.add_boost(session, boost_id=shield.id, amount=3)
    session.commit()

    # --- Генерация прохождения уровней и выдача призов ---
    player_levels = []
    player_prizes = []
    for player in players:
        for level in levels:
            # Случайно считаем, что уровень пройден или нет
            completed = datetime.utcnow() if (hash(player.id) + hash(level.id)) % 2 == 0 else None
            pl = PlayerLevel(player_id=player.id, level_id=level.id, completed=completed, score=100)
            player_levels.append(pl)

            # Если уровень пройден — выдаём приз
            if completed:
                lp = session.query(LevelPrize).filter_by(level_id=level.id).first()
                if lp:
                    player_prizes.append(PlayerPrize(player_id=player.id, prize_id=lp.prize_id))

    session.add_all(player_levels)
    session.add_all(player_prizes)
    session.commit()

    # --- Вывод результатов для одного игрока (пример) ---
    example_player = players[0]
    print(f"Player points: {example_player.points}")
    print("Начисленные бусты:")
    for pb in example_player.boosts:
        print(f"- Буст: {pb.boost.type.value}, amount: {pb.amount}")

    print("\nПройденные уровни:")
    for pl in example_player.levels[:10]:  # первые 10 уровней для наглядности
        print(f"- {pl.level.title}, score: {pl.score}, completed: {pl.completed}")

    print("\nПолученные призы:")
    for pp in example_player.prizes:
        print(f"- {pp.prize.title}, received_at: {pp.received_at}")

    # --- Экспорт всех данных в CSV ---
    export_player_levels_to_csv(session, "player_levels_export.csv")
    print("\nЭкспорт в CSV выполнен: player_levels_export.csv")