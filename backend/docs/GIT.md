# Ветки

```
main
 └─ develop
     ├─ Dim            личная ветка участника
     │   ├─ feature/auth
     │   └─ fix/login-cookie
     └─ Ivan
         └─ feature/orders
```

`main` -> `develop` -> личная ветка -> ветки задач (фичи, фиксы).
Слияние идёт обратно по той же цепочке, вверх по одному уровню.

## Первый раз: создать личную ветку

```bash
git checkout develop
git pull origin develop
git checkout -b Dim
git push -u origin Dim
```

## Новая задача

```bash
git checkout Dim
git pull origin develop
git checkout -b feature/auth
```

## Коммит и пуш

```bash
git add -A
git commit -m "add auth"
git push -u origin feature/auth
```

## Задача готова: влить в личную ветку

```bash
git checkout Dim
git merge feature/auth
git push origin Dim
git branch -d feature/auth
```

## Личная ветка готова: влить в develop

Подтянуть свежую develop и разобрать конфликты у себя:

```bash
git checkout Dim
git pull origin develop
git push origin Dim
```

Затем Pull Request `Dim` -> `develop`, апрув от напарника.

## Забрать чужие изменения из develop

```bash
git checkout Dim
git pull origin develop
```

## Develop в main (перед демо, один человек)

Pull Request `develop` -> `main`.

## Полезное

```bash
git branch                  # список веток, * текущая
git status                  # что изменено
git log --oneline -10       # последние коммиты
git branch -d feature/auth  # удалить влитую ветку
```
