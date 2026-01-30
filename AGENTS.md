# Руководство по репозиторию

## Структура проекта и организация модулей
- `main.py` — точка входа; парсит аргументы CLI и запускает полноэкранное PyQt5‑приложение.
- Основная логика в `app.py`, `audio_processor.py`, `overlay_manager.py`.
- Виджеты UI находятся в `components/` (`visualization.py`, `clock.py`, `overlay.py`).
- Конфигурация запуска — в `config.yaml`; изображения оверлея копируются в `assets/` (создаётся при необходимости).
- Зависимости перечислены в `requirements.txt`.

## Сборка, тесты и команды для разработки
- `python main.py` — запуск визуализатора с настройками по умолчанию.
- `python main.py --overlay images/logo.png` — запуск с новым оверлеем (файл копируется в `assets/`).
- `pip install -r requirements.txt` — установка зависимостей.

## Стиль кода и соглашения об именовании
- Python: отступ 4 пробела; `snake_case` для функций и переменных.
- Модули небольшие и разделены по ответственности (например, `overlay_manager.py` отвечает за работу с файлами).
- Форматтер/линтер не настроены — придерживайтесь существующего стиля и порядка.

## Правила тестирования
- Автоматических тестов пока нет.
- Если добавляете тесты, складывайте их в `tests/` и называйте файлы `test_*.py`.
- Ручные проверки описывайте в PR (например: «запустил `python main.py` на X11»).

## Правила коммитов и Pull Request
- Сообщения коммитов — короткие, в виде фразы без префиксов (например: «Add librosa integration»).
- Держите коммиты сфокусированными на одном изменении; при необходимости добавляйте второе предложение.
- В PR указывайте: краткое описание изменений, изменения конфигурации (если есть), скриншоты/GIF для визуальных правок.

## Конфигурация и запуск
- Приложение настраивается через `config.yaml` (FFT, градиенты, часы, путь к оверлею).
- UI ориентирован на Linux/X11; изменения окна проверяйте на X11.

## Landing the Plane (Session Completion)

**When ending a work session**, you MUST complete ALL steps below. Work is NOT complete until `git push` succeeds.

**MANDATORY WORKFLOW:**

1. **File issues for remaining work** - Create issues for anything that needs follow-up
2. **Run quality gates** (if code changed) - Tests, linters, builds
3. **Update issue status** - Close finished work, update in-progress items
4. **PUSH TO REMOTE** - This is MANDATORY:
   ```bash
   git pull --rebase
   bd sync
   git push
   git status  # MUST show "up to date with origin"
   ```
5. **Clean up** - Clear stashes, prune remote branches
6. **Verify** - All changes committed AND pushed
7. **Hand off** - Provide context for next session

**CRITICAL RULES:**
- Work is NOT complete until `git push` succeeds
- NEVER stop before pushing - that leaves work stranded locally
- NEVER say "ready to push when you are" - YOU must push
- If push fails, resolve and retry until it succeeds
