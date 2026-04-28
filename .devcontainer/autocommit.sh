#!/bin/bash
# VideoFlower — Otomatik commit & push
# Değişiklik algılandığında 60 saniye bekler, sonra commit atar

BRANCH=$(git branch --show-current 2>/dev/null || echo "main")
WATCH_DIR=$(git rev-parse --show-toplevel 2>/dev/null || echo ".")
DEBOUNCE=60  # saniye — kaydet, 60sn bekle, commit at

echo "🌸 AutoCommit aktif | branch: $BRANCH | bekleme: ${DEBOUNCE}s"

generate_commit_msg() {
  # Değişen dosyalar
  CHANGED=$(git diff --cached --name-only 2>/dev/null)
  STATS=$(git diff --cached --stat 2>/dev/null | tail -1)
  TIMESTAMP=$(date '+%Y-%m-%d %H:%M')

  # Dosya tipine göre prefix belirle
  if echo "$CHANGED" | grep -qE "\.(cs|razor)$"; then
    PREFIX="feat(ui)"
  elif echo "$CHANGED" | grep -qE "\.(py)$"; then
    PREFIX="feat(backend)"
  elif echo "$CHANGED" | grep -qE "\.(json|csproj|sln)$"; then
    PREFIX="chore(config)"
  elif echo "$CHANGED" | grep -qE "\.(md)$"; then
    PREFIX="docs"
  else
    PREFIX="chore"
  fi

  # İlk 3 dosya adını al
  FILES=$(echo "$CHANGED" | head -3 | xargs -I{} basename {} | tr '\n' ', ' | sed 's/,$//')

  echo "$PREFIX: $FILES — $STATS [$TIMESTAMP]"
}

# Değişiklikleri izle
inotifywait -m -r -e modify,create,delete,move \
  --exclude '(\.git|node_modules|obj|bin|__pycache__)' \
  "$WATCH_DIR" 2>/dev/null | \
while read -r dir event file; do
  # Debounce: kısa sürede çok fazla event gelirse biriktir
  sleep $DEBOUNCE

  # Gerçek değişiklik var mı?
  if git diff --quiet && git diff --cached --quiet && \
     [ -z "$(git ls-files --others --exclude-standard)" ]; then
    continue
  fi

  # Stage et
  git add -A

  # Commit mesajı üret
  MSG=$(generate_commit_msg)

  # Commit at
  git commit -m "$MSG" --quiet

  # Push et
  if git push origin "$BRANCH" --quiet 2>/dev/null; then
    echo "✅ Push: $MSG"
  else
    echo "⚠️  Push başarısız — token kontrolü gerekebilir"
  fi
done