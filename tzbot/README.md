# TZ va navbat boti

SMM ↔ dizayn jarayonidagi uchta muammoni hal qiladi:

| Muammo | Bot yechimi |
|---|---|
| TZ to'liq bo'lmaydi | Bot brend, ish turi, format, matn, materiallar va deadline'siz TZ ni **qabul qilmaydi** — nima yetishmayotganini aytib qaytaradi |
| Deadline berilmaydi | Deadline majburiy maydon. Har bir ish turi uchun minimal muddat bor; undan qisqa muddat berilsa bot **sabab** so'raydi |
| Navbatga rioya qilinmaydi | Navbat avtomatik — deadline bo'yicha. Hamma uchun `/navbat` da ochiq. Dizayner bir vaqtda faqat `WIP_LIMIT` ta ishni boshlaydi |

Bot tug'ilgan kunlar botidan **alohida** ishlaydi: o'z tokeni, o'z bazasi,
o'z jarayoni. Ikkalasini bitta guruhga qo'shsa ham bo'ladi.

## Buyruqlar

Barcha buyruqlar (`/start`, `/help`, `/qoida`, `/shablon` dan tashqari) faqat guruhda ishlaydi.

| Buyruq | Kim uchun | Tavsif |
|---|---|---|
| `/tz` | SMM | Yangi TZ. Bo'sh yuborilsa — savol-javob tartibi; shablon bilan yuborilsa — bir xabarda |
| `/shablon` | SMM | Nusxa olib to'ldiriladigan shablon |
| `/mentz` | SMM | O'zining ochiq TZ lari |
| `/navbat` | Hamma | Hozirgi navbat, deadline bo'yicha tartiblangan |
| `/boshladim 12` | Dizayner | 12-TZ ni ishga olish |
| `/tayyor 12` | Dizayner | 12-TZ ni yopish (kechikkan-kechikmagani hisoblanadi) |
| `/bekor 12` | Muallif yoki dizayner | TZ ni bekor qilish |
| `/hisobot` | Hamma | So'nggi 7 kun statistikasi |
| `/qoida` | Hamma | Jamoa uchun ish qoidalari |

## TZ qanday beriladi

**1-usul — bir xabarda.** `/shablon` dan nusxa oling, to'ldiring va yuboring:

```
/tz
Brend: Nestle
Ish turi: karusel
Format: 1080x1350
Matn: Sarlavha: Kuzgi chegirma -30%
CTA: Buyurtma bering
Materiallar: https://drive.google.com/...
Referens: https://pin.it/...
Deadline: 18-09 15:00
Izoh: logotip oq bo'lsin
```

Maydon nomlari moslashuvchan: `Mijoz`, `Muddat`, `O'lcham`, `Material` kabi
sinonimlar ham tushuniladi. `Matn` bir nechta qatordan iborat bo'lishi mumkin —
keyingi tanilgan maydongacha hammasi matn hisoblanadi.

**2-usul — savol-javob.** Shunchaki `/tz` yozing, bot bosqichma-bosqich so'raydi.
Ish turi va format tugmalar orqali tanlanadi. `/cancel` — bekor qilish.

Ikkala usulda ham `yo'q`, `keyin`, `tezroq`, `odatdagidek` kabi javoblar
to'ldirilgan hisoblanmaydi va TZ qaytariladi.

## Minimal muddatlar va prioritet

Prioritetni TZ beruvchi emas, **muddat** belgilaydi:

| Ish turi | Minimal muddat |
|---|---|
| Post / story maketi | 3 soat |
| Karusel (2+ slayd) | 6 soat |
| Reels / video montaj | 24 soat |
| Banner / print maketi | 24 soat |
| Logo / brending | 72 soat |
| Boshqa | 4 soat |

- Muddat minimaldan qisqa → **🔥 Shoshilinch**, bot sabab so'raydi va sabab
  TZ kartasida hamda haftalik hisobotda ko'rinadi.
- 24 soatdan kam → 🟡 Oddiy.
- 24 soatdan ko'p → 🟢 Rejali.

Shu tarzda "hammasi shoshilinch" holati yo'qoladi: shoshilinch deb belgilashning
narxi — ochiq yoziladigan sabab.

## Avtomatik eslatmalar

- Har 30 daqiqada: deadline'ga `REMINDER_LEAD_HOURS` soat qolgan, lekin hali
  boshlanmagan ishlar; deadline'i o'tib ketgan ishlar.
- Har kuni `DIGEST_HOUR:DIGEST_MINUTE` da: o'sha kungi navbat.
- Har dushanba shu vaqtda: o'tgan hafta hisoboti — kim nechta TZ berdi,
  nechtasi shoshilinch edi, o'rtacha qancha muddat berilgan.

## O'rnatish

1. [@BotFather](https://t.me/BotFather) da **yangi** bot yarating va tokenni oling.
2. Virtual muhit tayyorlang:

   ```bash
   cd tzbot
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

3. Sozlamalarni kiriting:

   ```bash
   cp .env.example .env
   # .env ni oching, BOT_TOKEN va DESIGNER_USERNAMES ni to'ldiring
   ```

4. Botni ish guruhiga qo'shing. BotFather → Bot Settings → Group Privacy →
   **Turn off** (aks holda bot guruhdagi buyruqlarni ko'rmaydi).
5. Ishga tushiring:

   ```bash
   python main.py
   ```

## Konfiguratsiya (.env)

| O'zgaruvchi | Tavsif | Standart |
|---|---|---|
| `BOT_TOKEN` | BotFather tokeni (majburiy) | — |
| `TIMEZONE` | Deadline va eslatmalar vaqt mintaqasi | `Asia/Tashkent` |
| `DB_PATH` | SQLite bazasi | `tasks.db` |
| `TEAM_NAME` | Jamoa nomi | `Jamoa` |
| `WIP_LIMIT` | Dizayner bir vaqtda nechta ish boshlay oladi | `2` |
| `DESIGNER_USERNAMES` | Dizaynerlar username'i, vergul bilan. Bo'sh — cheklov yo'q | bo'sh |
| `DIGEST_HOUR` / `DIGEST_MINUTE` | Kunlik xulosa vaqti | `9` / `30` |
| `REMINDER_LEAD_HOURS` | Deadline'ga necha soat qolganda eslatilsin | `2` |

## VPS'da doimiy ishlatish (systemd)

`/etc/systemd/system/tz-bot.service`:

```ini
[Unit]
Description=Telegram TZ & Queue Bot
After=network.target

[Service]
Type=simple
WorkingDirectory=/path/to/Deha/tzbot
ExecStart=/path/to/Deha/tzbot/.venv/bin/python main.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now tz-bot
```

## Sinash

Telegram'siz, soxta Update obyektlari bilan:

```bash
cd tzbot
python tests/smoke.py
```

Hamma buyruq, tekshiruv va navbat mantig'i sinaladi.
