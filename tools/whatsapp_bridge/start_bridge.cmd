@echo off
chcp 65001 >nul
title GY WhatsApp Bridge
cd /d "/Users/imyigitcengiz/Downloads/GitHub/kobi-ops/tools/whatsapp_bridge"
echo [%date% %time%] Köprü baslatiliyor...
echo Node: "/Users/imyigitcengiz/.nvm/versions/node/v24.15.0/bin/node"
"/Users/imyigitcengiz/.nvm/versions/node/v24.15.0/bin/node" server.js
if errorlevel 1 (
  echo.
  echo HATA: Köprü kapandi. Yukaridaki kirmizi mesaji okuyun.
  echo node_modules yoksa: npm install
  pause
)
