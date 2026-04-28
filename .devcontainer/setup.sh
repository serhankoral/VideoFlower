#!/bin/bash
set -e

echo "🌸 VideoFlower ortamı kuruluyor..."

# inotify-tools: dosya değişikliklerini izlemek için
sudo apt-get update -q && sudo apt-get install -y -q inotify-tools

# Git global ayarları
git config --global user.email "${GIT_EMAIL:-videoflower@dev.local}"
git config --global user.name "${GIT_NAME:-VideoFlower Bot}"

# autocommit.sh çalıştırılabilir yap
chmod +x .devcontainer/autocommit.sh

echo "✅ Container hazır! Container Kuruldupuda auth login yaz!"