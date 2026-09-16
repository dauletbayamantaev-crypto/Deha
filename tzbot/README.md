# TZ boti

SMM menejer botga TZ beradi — bot uni to'liqligini tekshiradi, kerakli topikka
yuboradi va mas'ul dizaynerga shaxsiy bildirishnoma jo'natadi.

Bot **shaxsiy chatda ham, guruhda ham** bir xil ishlaydi.

## Bot guruhga shunday yuboradi

```
ID_160926
TZ (Texnik topshiriq) @smm_aziz tomonidan berildi.
Mijoz: Xazna
Tasnif: Xazna uchun karusel post
Mavzu: Xalqaro o'tkazmalar xazna ilovasidan amalga oshirish qo'llanmasi
Deadline: 20.09.2026 18:00
Dizayner: @dilnoza

1. Page
Lorem ipsum

2. Page
Lorem ipsum

Izoh: logotip oq bo'lsin

#xazna #karusel

Tayyor bo'lgach: /tayyor ID_160926
```

`ID_160926` — kun bo'yicha raqam (16.09.26). O'sha kuni ikkinchi TZ berilsa
`ID_160926-2` bo'ladi. Hashtaglar mijoz nomi va ish turidan avtomatik yig'iladi.

---

# O'rnatish — qadamma-qadam

Tug'ilgan kunlar botini o'rnatgan bo'lsangiz, bu ham xuddi shunday. Farqi —
**alohida token** va **alohida papka**.

## 1-qadam. Yangi bot yarating

1. Telegramda [@BotFather](https://t.me/BotFather) ni oching.
2. `/newbot` yozing.
3. Bot nomini yozing, masalan: `Deha TZ`.
4. Bot username'ini yozing, `bot` bilan tugashi shart: `deha_tz_bot`.
5. BotFather uzun token beradi — `123456:AAF...` ko'rinishida. **Nusxa oling.**
6. Shu yerda `/mybots` → botni tanlang → `Bot Settings` → `Group Privacy` →
   **Turn off**. Bu shart, aks holda bot guruhda buyruqlarni ko'rmaydi.

## 2-qadam. Loyihani yuklab oling

Terminal (Mac) yoki PowerShell (Windows) da:

```bash
git clone https://github.com/dauletbayamantaev-crypto/Deha.git
cd Deha/tzbot
```

## 3-qadam. Ishga tushiring — bitta buyruq

**Mac / Linux:**

```bash
bash ishga_tushir.sh
```

**Windows:** `Deha\tzbot` papkasini oching va `ishga_tushir.bat` faylini ikki marta bosing.

Birinchi safar skript hammasini o'zi qiladi: muhit tayyorlaydi, kutubxonalarni
o'rnatadi (1-2 daqiqa) va tokenni so'raydi. BotFather bergan tokenni qo'ying va
Enter bosing.

> Token yozganingizda ekranda hech narsa ko'rinmaydi — bu xavfsizlik uchun,
> normal holat. Yozib Enter bosavering.

Terminalda `TZ bot ishga tushdi` chiqsa — tayyor.
**Bu oyna ochiq tursin**, yopsangiz bot o'chadi. To'xtatish: `Ctrl+C`.

Keyingi safar shunchaki yana o'sha faylni ishga tushirasiz — token so'ralmaydi.

<details>
<summary>Qo'lda o'rnatish (skriptsiz)</summary>

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # Windows: copy .env.example .env
# .env faylini oching va BOT_TOKEN qiymatini yozing
python main.py
```
</details>

## 4-qadam. Tokenni hech kimga bermang

Token — botning kaliti. U `.env` faylida turadi va git'ga **hech qachon
tushmaydi** (`.gitignore` da yozilgan). Agar tokeni biror joyga (chat, skrinshot,
xabar) yuborib qo'ysangiz — BotFather'da `/revoke` qiling va yangi token oling.

## 5-qadam. Botni guruhga qo'shing

Guruh → Add members → bot username'ini yozing → qo'shing.
So'ng guruhda bir marta `/start` yozing — bot guruhni eslab qoladi.

## 6-qadam. Topiklarni ro'yxatga oling

Bot Telegram'dan topiklar ro'yxatini o'zi ola olmaydi — bir marta ko'rsatish kerak.

Har bir topikka kiring va ichida yozing:

```
/topik Xazna
```

Boshqa topikda `/topik Artel`, yana boshqasida `/topik Umumiy dizayn` va hokazo.
Ro'yxatni ko'rish uchun topikdan tashqarida `/topik` yozing.

## 7-qadam. Dizaynerlar botga /start bossin ⚠️

**Eng muhim qadam.** Telegram qoidasiga ko'ra bot faqat o'ziga bir marta yozgan
odamga shaxsiy xabar yubora oladi.

Har bir dizayner botni shaxsiy chatda ochib, `/start` bosishi kerak.
Aks holda TZ guruhga tushadi, lekin shaxsiy bildirishnoma bormaydi — bot
bu haqda SMM menejerga ogohlantirish beradi.

---

# Ishlatish

## TZ berish

Shaxsiy chatda yoki guruhda `/tz` yozing. Bot ketma-ket so'raydi:

| Savol | Javob |
|---|---|
| Qaysi guruh / topik? | Tugmadan tanlanadi (topik ichida yozsangiz — so'ramaydi) |
| Mijoz kim? | `Xazna` |
| Tasnif? | Tugmalar: Karusel post / Feed post / Story / Reels / Banner / Boshqa |
| Mavzu? | `Xalqaro o'tkazmalar qo'llanmasi` |
| Deadline? | Tugma (Bugun 18:00 / Ertaga 12:00 / Ertaga 18:00) yoki `20.09.2026 18:00` |
| Dizayner kim? | `@dilnoza` — bir nechta bo'lsa `@dilnoza @ali` |
| TZ matni? | Hammasi **bitta xabarda**: `1. Page` … `2. Page` … |
| Izoh? | Yozasiz yoki "⏭ Izohsiz" tugmasini bosasiz |

Bekor qilish — `/cancel`.

## Tezroq usul — bitta xabarda

`/shablon` yozing, bot shablon beradi. Nusxalab to'ldiring va yuboring:

```
/tz
Mijoz: Xazna
Tasnif: Xazna uchun karusel post
Mavzu: Xalqaro o'tkazmalar qo'llanmasi
Deadline: 20.09.2026 18:00
Dizayner: @dilnoza
Matn:
1. Page
Lorem ipsum

2. Page
Lorem ipsum
Izoh: logotip oq bo'lsin
```

Maydon nomlari moslashuvchan: `Brend`, `Muddat`, `Mas'ul`, `TZ` kabi sinonimlar
ham tushuniladi. Biror maydon to'ldirilmasa yoki `yo'q`, `tezroq`, `keyin` deb
yozilsa — bot TZ ni qabul qilmaydi va nima yetishmayotganini aytadi.

## Buyruqlar

| Buyruq | Kim uchun | Tavsif |
|---|---|---|
| `/tz` | SMM | Yangi TZ |
| `/shablon` | SMM | Shablonni olish |
| `/tayyor ID_160926` | Dizayner | TZ ni yopish |
| `/bekor ID_160926` | Muallif yoki dizayner | TZ ni bekor qilish |
| `/navbat` | Hamma | Ochiq TZ lar (shaxsiyda — faqat o'ziniki) |
| `/hisobot` | Hamma | So'nggi 7 kun statistikasi |
| `/topik Nomi` | Hamma | Topikni ro'yxatga olish |
| `/help` | Hamma | Yordam |

## Bot o'zi nima qiladi

- Deadline'ga 2 soat qolganda — guruhga va dizaynerga eslatma.
- Deadline o'tib ketsa — yana eslatma.
- Har kuni 09:30 da — o'sha kungi ochiq TZ lar ro'yxati.
- Har dushanba 09:30 da — hafta hisoboti: kim nechta TZ berdi, nechtasi
  4 soatdan kam muddat bilan berilgan, qaysi dizayner nechtasini bajardi.

---

# Sozlamalar (.env)

| O'zgaruvchi | Tavsif | Standart |
|---|---|---|
| `BOT_TOKEN` | BotFather tokeni (majburiy) | — |
| `TIMEZONE` | Vaqt mintaqasi | `Asia/Tashkent` |
| `DB_PATH` | Ma'lumotlar fayli | `tasks.db` |
| `DIGEST_HOUR` / `DIGEST_MINUTE` | Kunlik xulosa vaqti | `9` / `30` |
| `REMINDER_LEAD_HOURS` | Deadline'ga necha soat qolganda eslatilsin | `2` |
| `RUSH_HOURS` | Hisobotda "shoshilinch" deb sanaladigan muddat | `4` |

# Nimani qayerdan o'zgartirasiz

Dasturchi bo'lmasangiz ham bu joylarni o'zgartirish oson — fayl ochib,
kerakli qatorni almashtirasiz va botni qayta ishga tushirasiz.

| Nimani | Qaysi fayl | Nimani qidirasiz |
|---|---|---|
| Ish turlari va hashtaglar | `app/tzform.py` | `KINDS = (` |
| Guruhga chiqadigan xabar ko'rinishi | `app/render.py` | `def render_task` |
| Bot so'raydigan savollar matni | `app/tzform.py` | `FIELDS = (` |
| Deadline tugmalari (Bugun 18:00 ...) | `app/handlers.py` | `_deadline_keyboard` |
| "yo'q", "tezroq" kabi rad etiladigan javoblar | `app/tzform.py` | `_EMPTY_VALUES` |
| Eslatma va hisobot vaqtlari | `.env` | `DIGEST_HOUR` |

O'zgartirgandan keyin:

```bash
python tests/smoke.py   # hammasi joyidami — tekshiradi
python main.py          # qayta ishga tushiradi
```

# Doimiy ishlashi uchun

Bot siz uni ishga tushirgan kompyuterda ishlaydi. Ya'ni:

- **Sinov uchun** — o'z kompyuteringizda ishga tushiring, terminal oynasi ochiq tursin.
- **Jamoa uchun doimiy** — bot 24/7 ishlashi kerak. Ikki yo'l bor:
  1. Agentlikda doim yoqiq turadigan kompyuter (uyqu rejimi o'chirilgan bo'lsin).
  2. Arzon VPS (oyiga ~5$). Bunda pastdagi systemd sozlamasi bilan bot
     server qayta yuklansa ham o'zi ishga tushadi.

## VPS (systemd)

`/etc/systemd/system/tz-bot.service` faylini yarating:

```ini
[Unit]
Description=Telegram TZ Bot
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
sudo systemctl status tz-bot
```

# Sinash

Telegramsiz, soxta xabarlar bilan butun bot tekshiriladi:

```bash
cd tzbot
python tests/smoke.py
```

62 ta tekshiruv: topik tanlash, bildirishnoma, to'liqsiz TZ ni rad etish,
deadline hisobi, eslatmalar, hisobot.
