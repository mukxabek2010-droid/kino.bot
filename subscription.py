services:
  - type: web
    name: kinobot
    env: python
    buildCommand: pip install -r requirements.txt
    startCommand: python bot.py
    envVars:
      - key: BOT_TOKEN
        sync: false
      - key: ADMIN_IDS
        sync: false
      - key: CHANNEL_1
        sync: false
      - key: CHANNEL_2
        sync: false
      - key: PREMIUM_PRICE
        value: "10000"
      - key: PAYMENT_CARD
        sync: false
      - key: PAYMENT_NAME
        sync: false
