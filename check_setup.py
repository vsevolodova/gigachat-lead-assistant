# -*- coding: utf-8 -*-
"""
Проверка готовности ассистента заявок.

Запуск:  python check_setup.py

Скрипт проверяет по порядку:
  1. Установлен ли Python подходящей версии.
  2. Установлены ли нужные библиотеки.
  3. Заполнен ли файл .env (особенно ключ GIGA_AUTH_KEY).
  4. Настроены ли сертификаты.
  5. (Если ключ заполнен) связывается ли GigaChat API — простым запросом,
     который не расходует токены.

Всё с пометкой [ОШИБКА] нужно исправить; [ВНИМ.] — желательно.
"""

import os
import sys
from importlib.metadata import PackageNotFoundError, version

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

ok_count = 0
warn_count = 0
fail_count = 0


def ok(message):
    global ok_count
    ok_count += 1
    print("  [  OK  ]  " + message)


def warn(message):
    global warn_count
    warn_count += 1
    print("  [ВНИМ.]  " + message)


def fail(message):
    global fail_count
    fail_count += 1
    print("  [ОШИБКА]  " + message)


def load_env_manual(path):
    """Читаем .env так же, как приложение (без библиотек)."""
    envs = {}
    if not os.path.exists(path):
        return envs
    with open(path, "r", encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key:
                envs[key] = value
    return envs


def main():
    print()
    print("Проверка готовности ассистента заявок")
    print("=" * 50)

    # 1. Версия Python
    print("\n1) Python")
    if sys.version_info < (3, 8):
        fail(f"Версия Python {sys.version.split()[0]} — слишком старая. Нужна 3.8 или новее.")
    else:
        ok(f"Python установлен, версия {sys.version.split()[0]}.")

    # 2. Библиотеки
    print("\n2) Библиотеки")
    missing = []
    for package, our_name in (("flask", "Flask (веб-сервер)"), ("gigachat", "gigachat (GigaChat API)"), ("python-dotenv", "python-dotenv (чтение .env)")):
        try:
            ver = version(package)
        except PackageNotFoundError:
            # у flask есть внутренние альтернативные имена — проверим импортом
            try:
                __import__("flask" if package == "flask" else "gigachat")
                ver = "установлена (версию определить не удалось)"
            except ImportError:
                fail(f"{our_name} не установлена. Выполните: pip install -r requirements.txt")
                missing.append(package)
                continue
        ok(f"{our_name}: версия {ver}")

    if missing:
        print("        Установить недостающее можно командой:")
        print("        pip install -r requirements.txt")

    # 3. Файл .env
    print("\n3) Файл настроек .env")
    env_path = os.path.join(BASE_DIR, ".env")
    env = load_env_manual(env_path)
    if not env:
        fail("Файл .env не найден или пуст. Скопируйте .env.example в .env и заполните.")
    else:
        ok("Файл .env найден.")

    key = env.get("GIGA_AUTH_KEY", "")
    key = key if key else os.environ.get("GIGA_AUTH_KEY", "")
    if not key:
        fail("Ключ GIGA_AUTH_KEY не заполнен. Впишите ключ авторизации после знака = в файле .env.")
    else:
        ok("Ключ GIGA_AUTH_KEY заполнен (содержимое не печатается — это секрет).")
        if key != key.strip() or " " in key or '"' in key or "'" in key:
            warn("Похоже, вокруг ключа есть пробелы или кавычки. Ключ должен стоять сразу после = и без кавычек.")

    model = env.get("GIGA_MODEL", "").strip() or "GigaChat"
    ok(f"Модель: {model}")

    # 4. Сертификаты
    print("\n4) Сертификаты (соединение с GigaChat)")
    ca_file = env.get("GIGA_CA_FILE", "").strip()
    verify_raw = env.get("GIGA_VERIFY_SSL", "1").strip().lower()
    check_ssl = verify_raw not in ("0", "false", "no", "нет")

    if not check_ssl:
        warn("Проверка SSL-сертификатов ОТКЛЮЧЕНА (GIGA_VERIFY_SSL=0).")
        print("        Это годится только для локального теста. Для постоянной работы")
        print("        скачайте сертификат с gosuslugi.ru/crt и укажите его в GIGA_CA_FILE.")
    elif ca_file:
        if os.path.exists(ca_file):
            ok(f"Сертификат подключён: {ca_file}")
        else:
            warn(f"Файл сертификата не найден по пути: {ca_file}. Проверьте путь в GIGA_CA_FILE.")
    else:
        ok("Проверка SSL включена, свой файл сертификата не задан.")
        print("        Если приложение сообщит «проблема сертификатов» — скачайте")
        print("        «Russian Trusted Root CA» с gosuslugi.ru/crt и пропишите")
        print("        путь к нему в GIGA_CA_FILE. Есть и быстрый временный вариант:")
        print("        GIGA_VERIFY_SSL=0 (только для локальной проверки).")

    # 5. Связь с GigaChat API (если ключ есть)
    if key and not missing:
        print("\n5) Связь с GigaChat API")
        try:
            from gigachat import GigaChat

            options = {"credentials": key, "model": model, "timeout": 30.0}
            scope = env.get("GIGA_SCOPE", "").strip()
            if scope:
                options["scope"] = scope
            if ca_file:
                options["ca_bundle_file"] = ca_file
            options["verify_ssl_certs"] = check_ssl

            print("        Отправляем простой запрос (токены не расходуются на него)…")
            with GigaChat(**options) as client:
                models = client.get_models()
                names = []
                try:
                    for m in getattr(models, "data", []):
                        name = getattr(m, "id_", None) or getattr(m, "id", None)
                        if not name and isinstance(m, dict):
                            name = m.get("id") or m.get("id_")
                        if name:
                            names.append(str(name))
                    names = names[:8]
                except Exception:
                    names = []
            ok("GigaChat отвечает, ключ принят.")
            if names:
                print(f"        Доступные модели (первые): {', '.join(names)}")
                if model not in names:
                    warn(f"Модель «{model}» нет в списке доступных. Проверьте GIGA_MODEL в .env.")
        except Exception as exc:
            fail("Не удалось соединиться или ключ не принят.")
            msg = str(exc)
            brief = msg if len(msg) <= 300 else msg[:300] + "…"
            print(f"        Причина: {brief}")
            print("        Что делать с частыми причинами — смотрите README (раздел «Если что-то не работает»).")

    # Итог
    print("\n" + "=" * 50)
    if fail_count == 0:
        print("Готово к запуску!" if warn_count == 0 else "Почти готово: замечания [ВНИМ.] выше можно исправить позже, запускать уже можно.")
        print("Запуск приложения:")
        print(f"    cd \"{BASE_DIR}\"")
        print("    python app.py")
        print("Затем откройте в браузере http://127.0.0.1:" + str(env.get("GIGA_PORT", "5000") or "5000"))
    else:
        print(f"Найдено проблем: {fail_count}. Исправьте их и запустите проверку ещё раз:")
        print(f"    cd \"{BASE_DIR}\"")
        print("    python check_setup.py")
    print()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(1)
