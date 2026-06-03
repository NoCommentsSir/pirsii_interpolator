# Интерполятор

Подробная локальная отладка, mock RIFE режим и ручные smoke-тесты описаны в [`docs/local_debugging.md`](docs/local_debugging.md).

### 🚀 Запуск

Пересборка и запуск контейнеров (нужна при изменениях в Dockerfile или зависимостях):

```bash
docker compose up -d --build
```

---

### 🧹 Остановка и очистка

Остановка контейнеров с удалением volumes и сетей:

```bash
docker compose down -v
```

---

### 📜 Логи

Просмотр логов контейнера:

```bash
docker compose logs <имя_контейнера>
```

Пример:
```bash
docker compose logs backend
```

---

### ⚙️ Выполнение команд в контейнере

Запуск Python-модуля внутри backend контейнера:

```bash
docker compose exec backend python -m backend.worker.worker
```

---

### Deploy
```bash
git clone https://github.com/NoCommentsSir/pirsii_interpolator.git
cd pirsii_interpolator
cp .env.example .env
docker compose up -d --build
```
