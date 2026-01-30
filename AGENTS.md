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

<!-- bv-agent-instructions-v1 -->

---

## Beads Workflow Integration

This project uses [beads_viewer](https://github.com/Dicklesworthstone/beads_viewer) for issue tracking. Issues are stored in `.beads/` and tracked in git.

### Essential Commands

```bash
# View issues (launches TUI - avoid in automated sessions)
bv

# CLI commands for agents (use these instead)
bd ready              # Show issues ready to work (no blockers)
bd list --status=open # All open issues
bd show <id>          # Full issue details with dependencies
bd create --title="..." --type=task --priority=2
bd update <id> --status=in_progress
bd close <id> --reason="Completed"
bd close <id1> <id2>  # Close multiple issues at once
bd sync               # Commit and push changes
```

### Workflow Pattern

1. **Start**: Run `bd ready` to find actionable work
2. **Claim**: Use `bd update <id> --status=in_progress`
3. **Work**: Implement the task
4. **Complete**: Use `bd close <id>`
5. **Sync**: Always run `bd sync` at session end

### Key Concepts

- **Dependencies**: Issues can block other issues. `bd ready` shows only unblocked work.
- **Priority**: P0=critical, P1=high, P2=medium, P3=low, P4=backlog (use numbers, not words)
- **Types**: task, bug, feature, epic, question, docs
- **Blocking**: `bd dep add <issue> <depends-on>` to add dependencies

### Session Protocol

**Before ending any session, run this checklist:**

```bash
git status              # Check what changed
git add <files>         # Stage code changes
bd sync                 # Commit beads changes
git commit -m "..."     # Commit code
bd sync                 # Commit any new beads changes
git push                # Push to remote
```

### Best Practices

- Check `bd ready` at session start to find available work
- Update status as you work (in_progress → closed)
- Create new issues with `bd create` when you discover tasks
- Use descriptive titles and set appropriate priority/type
- Always `bd sync` before ending session

<!-- end-bv-agent-instructions -->
