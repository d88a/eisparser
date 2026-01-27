#!/usr/bin/env python3
"""
EIS Parser — Парсер закупок недвижимости.

CLI для запуска каждого этапа пайплайна.
"""
import argparse
import json
from utils.logger import setup_logger, get_logger
from pipeline import Pipeline


def cmd_stats(pipeline: Pipeline, args):
    """Показать статистику."""
    stats = pipeline.get_statistics()
    print(f"\n📊 Статистика:")
    print(f"  Закупок: {stats['zakupki']}")
    print(f"  ИИ-результатов: {stats['ai_results']}")
    print(f"  Объявлений: {stats['listings']}")


def cmd_stage1(pipeline: Pipeline, args):
    """Stage 1: Загрузка закупок (ОКПД2 68.10.11)."""
    result = pipeline.run_stage1(limit=args.limit)
    print(f"\n{result}")
    if result.errors:
        print(f"  Ошибки: {result.errors}")


def cmd_stage2(pipeline: Pipeline, args):
    """Stage 2: ИИ-обработка."""
    result = pipeline.run_stage2(limit=args.limit)
    print(f"\n{result}")
    if result.errors:
        print(f"  Ошибки: {result.errors}")


def cmd_stage3(pipeline: Pipeline, args):
    """Stage 3: Генерация ссылок 2ГИС."""
    result = pipeline.run_stage3(limit=args.limit)
    print(f"\n{result}")
    print(f"  Данные: {json.dumps(result.data, ensure_ascii=False, indent=2)}")
    if result.errors:
        print(f"  Ошибки ({len(result.errors)}): {result.errors[:3]}...")


def cmd_stage4(pipeline: Pipeline, args):
    """Stage 4: Сбор объявлений."""
    result = pipeline.run_stage4(
        top_n=args.top_n,
        limit=args.limit,
        get_details=args.details
    )
    print(f"\n{result}")
    print(f"  Данные: {json.dumps(result.data, ensure_ascii=False, indent=2)}")
    if result.errors:
        print(f"  Ошибки ({len(result.errors)}): {result.errors[:3]}...")


def cmd_server(pipeline: Pipeline, args):
    """Запуск веб-сервера UI."""
    import uvicorn
    print(f"Запуск UI на http://{args.host}:{args.port}")
    uvicorn.run(
        "api.app:app",
        host=args.host,
        port=args.port,
        reload=True
    )


def main():
    """Главная функция."""
    parser = argparse.ArgumentParser(
        description="EIS Parser — Парсер закупок недвижимости",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры:
  python main.py stats
  python main.py stage1 --limit 10
  python main.py stage2 --limit 5
  python main.py stage3 --limit 5
  python main.py stage4 --top-n 5 --limit 2 --details
        """
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Подробный вывод (DEBUG уровень)'
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Доступные команды')
    
    # stats
    stats_parser = subparsers.add_parser('stats', help='Показать статистику')
    
    # stage1
    stage1_parser = subparsers.add_parser('stage1', help='Stage 1: Загрузка закупок (ОКПД2 68.10.11)')
    stage1_parser.add_argument('--limit', type=int, default=10, help='Макс. количество')
    
    # stage2
    stage2_parser = subparsers.add_parser('stage2', help='Stage 2: ИИ-обработка')
    stage2_parser.add_argument('--limit', type=int, default=None, help='Макс. количество')
    
    # stage3
    stage3_parser = subparsers.add_parser('stage3', help='Stage 3: Генерация ссылок 2ГИС')
    stage3_parser.add_argument('--limit', type=int, default=None, help='Макс. количество')
    
    # stage4
    stage4_parser = subparsers.add_parser('stage4', help='Stage 4: Сбор объявлений')
    stage4_parser.add_argument('--top-n', type=int, default=20, help='Объявлений на закупку')
    stage4_parser.add_argument('--limit', type=int, default=None, help='Макс. закупок')
    stage4_parser.add_argument('--details', action='store_true', help='Получать детали (год постройки)')
    
    # server
    server_parser = subparsers.add_parser('server', help='Запуск UI (Веб-интерфейс)')
    server_parser.add_argument('--host', type=str, default='127.0.0.1', help='Хост')
    server_parser.add_argument('--port', type=int, default=8000, help='Порт')
    
    args = parser.parse_args()
    
    # Настраиваем логирование
    import logging
    level = logging.DEBUG if args.verbose else logging.INFO
    setup_logger(level=level)
    logger = get_logger("main")
    
    print("=" * 50)
    print("EIS Parser v2.0 (OOP-version)")
    print("=" * 50)
    
    # Инициализируем Pipeline (кроме команды server)
    pipeline = None
    if args.command != 'server':
        pipeline = Pipeline()
        pipeline.init_database()
    
    # Выполняем команду
    commands = {
        'stats': cmd_stats,
        'stage1': cmd_stage1,
        'stage2': cmd_stage2,
        'stage3': cmd_stage3,
        'stage3': cmd_stage3,
        'stage4': cmd_stage4,
        'server': cmd_server,
    }
    
    if args.command in commands:
        commands[args.command](pipeline, args)
    else:
        parser.print_help()
    
    print()
    return 0


if __name__ == "__main__":
    exit(main())
