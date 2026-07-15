from app.db import SessionLocal, engine, Base
from app.models import Equipment, Booking


def run():
    Base.metadata.create_all(engine)  # создаём таблицы

    db = SessionLocal()
    try:
        db.query(Booking).delete()
        db.query(Equipment).delete()
        db.commit()

        db.add_all([
            Equipment(
                name="КамАЗ 43118 с КМУ-150 «Галичанин»",
                type="Бортовой автокран с буром",
                hourly_rate=4000,
                deposit=40000,
                specs={
                    "Грузоподъёмность": "7 т",
                    "Грузовой момент": "15 тм",
                    "Вылет стрелы": "19 м",
                    "Бур": True,
                    "Люлька": True,
                    "Шасси": "КамАЗ-43118",
                },
            ),
            Equipment(
                name="Погрузчик ZAUBERG EF4C",
                type="Фронтальный погрузчик",
                hourly_rate=3000,
                deposit=30000,
                specs={
                    "Грузоподъёмность": "2500 кг",
                    "Передний ковш": "челюстной 4-в-1",
                    "Задний ковш": "0.3 м³",
                    "Стрела": "телескопическая",
                    "Мощность": "95 л.с.",
                },
            ),
        ])
        db.commit()
        print("✅ Сид выполнен: 2 единицы техники добавлены")
    finally:
        db.close()


if __name__ == "__main__":
    run()