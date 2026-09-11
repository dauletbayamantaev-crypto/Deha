# Tug'ilgan kunlar eslatuvchi Telegram bot

Jamoa guruhingizdagi a'zolarning tug'ilgan kunlarini saqlaydi va har kuni
ertalab o'sha kuni tug'ilgan kuni bo'lgan a'zolarni guruhga avtomatik
tabriklaydi.

## Buyruqlar

Barcha buyruqlar (`/start`, `/help` dan tashqari) faqat guruh ichida ishlaydi.

| Buyruq | Tavsif |
|---|---|
| `/setbirthday KK-OO` yoki `/setbirthday KK-OO-YYYY` | Tug'ilgan kuningizni saqlaydi. Masalan: `/setbirthday 15-03` yoki `/setbirthday 15-03-1998` |
| `/mybirthday` | Saqlangan tug'ilgan kuningizni ko'rsatadi |
| `/removebirthday` | Tug'ilgan kuningizni o'chiradi |
| `/birthdays` | Guruhdagi barcha tug'ilgan kunlar ro'yxatini (yaqinlashib kelayotgan tartibda) ko'rsatadi |
| `/help` | Yordam xabari |

Har kuni belgilangan vaqtda (standart: 09:00, `Asia/Tashkent`) bot barcha
guruhlarni tekshirib, o'sha kuni tug'ilgan kuni bo'lganlarni bittalab yoki
guruh bo'lib tabriklaydi.

## O'rnatish

1. [@BotFather](https://t.me/BotFather) orqali yangi bot yarating va tokenni oling.
2. Repozitoriyani klonlab, virtual muhit tayyorlang:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

3. `.env.example` faylidan nusxa oling va tokeningizni kiriting:

   ```bash
   cp .env.example .env
   # .env faylini oching va BOT_TOKEN qiymatini o'zgartiring
   ```

4. Botni jamoa guruhingizga qo'shing va admin qilishingiz shart emas —
   faqat xabar yuborish huquqi yetarli. Guruhda "Group Privacy" o'chirilgan
   bo'lishi kerak (BotFather → Bot Settings → Group Privacy → Turn off),
   aks holda bot buyruqlarni ko'ra olmaydi.

5. Botni ishga tushiring:

   ```bash
   python main.py
   ```

## VPS'da doimiy ishlatish (systemd)

`/etc/systemd/system/birthday-bot.service` faylini yarating:

```ini
[Unit]
Description=Telegram Birthday Reminder Bot
After=network.target

[Service]
Type=simple
WorkingDirectory=/path/to/Deha
ExecStart=/path/to/Deha/.venv/bin/python main.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

So'ng:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now birthday-bot
sudo systemctl status birthday-bot
```

## Konfiguratsiya (.env)

| O'zgaruvchi | Tavsif | Standart |
|---|---|---|
| `BOT_TOKEN` | BotFather'dan olingan token (majburiy) | — |
| `TIMEZONE` | Eslatma vaqti mintaqasi | `Asia/Tashkent` |
| `REMINDER_HOUR` | Eslatma yuboriladigan soat (0-23) | `9` |
| `REMINDER_MINUTE` | Eslatma yuboriladigan daqiqa | `0` |
| `DB_PATH` | SQLite ma'lumotlar bazasi fayli | `birthdays.db` |

## Ma'lumotlar bazasi

Barcha tug'ilgan kunlar `birthdays.db` (SQLite) faylida saqlanadi, har bir
yozuv guruh (`chat_id`) va foydalanuvchiga (`user_id`) bog'langan — bitta
foydalanuvchi turli guruhlarda alohida sana saqlashi mumkin.
