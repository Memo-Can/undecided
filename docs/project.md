# Kararsızım — Proje Planı (Claude Code için)

> Bu dosya Claude Code'a verilecek ana plandır. Proje bir **prototip**tir: basit tut, gereksiz soyutlama, ekstra özellik ve kütüphane ekleme. Her fazı **ayrı ayrı** yapacağız; bir faz bitmeden sonrakine geçme, faz sonunda dur ve onay iste.

## 1. Proje Özeti

**Ad:** Kararsızım

**Amaç:** Kullanıcıların kararsız kaldıkları konularda anket açabildiği, diğer kullanıcıların da oy verdiği bir platform. Örnek: "Bugün sinemaya mı tiyatroya mı gitsem?" → seçenekler: Sinema, Tiyatro.

**Temel kurallar**
- Bir anketin **en az 2, en çok 5** seçeneği olur.
- Takip (follow) sistemi, profil takibi, bildirim, yorum, beğeni **yoktur**.
- Her kullanıcı (giriş yapmamış olsa bile) platformdaki **tüm anketleri görebilir ve oy verebilir**.
- **Anket oluşturmak için üyelik zorunludur.**
- Kayıt alanları: **e-posta, parola, kullanıcı adı**. Kullanıcı adı benzersizdir ve anketlerde herkese **görünür**.

## 2. Teknoloji Yığını

| Katman | Seçim |
|---|---|
| Backend | Python 3.12 + Django (5.x) |
| Veritabanı | Supabase (yalnızca yönetilen **PostgreSQL** olarak kullanılır) |
| Deployment | Vercel (Python serverless, WSGI) |
| Frontend | Framework yok. Düz HTML + CSS + JavaScript, **aynı repo içinde** |

**Mimari kararlar (prototip için sabit):**
1. **Auth'u Django yapar** (Supabase Auth / Supabase JS SDK kullanılmaz). Özel `User` modeli + Django session. Supabase sadece Postgres'tir; bağlantı `DATABASE_URL` ile yapılır (`dj-database-url`).
2. Django hem **JSON API** sunar hem de sayfa şablonlarını (HTML) servis eder. Sayfalar Django template ile basit iskelet olarak gelir, veri `fetch` ile JS tarafından API'den çekilir.
3. Oturumlar **veritabanında** tutulur (`SESSION_ENGINE = django.contrib.sessions.backends.db`); Vercel'de dosya sistemi kalıcı değildir.
4. Statik dosyalar **WhiteNoise** ile servis edilir.
5. Supabase bağlantısında **connection pooler (transaction mode, port 6543)** kullan: `CONN_MAX_AGE = 0`, `DISABLE_SERVER_SIDE_CURSORS = True`. Serverless için gereklidir.
6. Supabase'in RLS'i devre dışı/önemsiz: veritabanına yalnızca Django bağlanır, istemci doğrudan bağlanmaz.
7. Ek kütüphane minimumda kalsın: `django`, `psycopg[binary]`, `dj-database-url`, `whitenoise`, `python-dotenv`.

## 3. Veri Modeli

```
User (AbstractUser'dan türet)
  - id
  - username   (benzersiz, 3-20 karakter, harf/rakam/_ )
  - email      (benzersiz, zorunlu)
  - password
  - date_joined

Poll
  - id
  - question     (CharField, max 200)
  - author       (FK -> User, on_delete=CASCADE)
  - created_at

Option
  - id
  - poll         (FK -> Poll, related_name="options", on_delete=CASCADE)
  - text         (CharField, max 100)
  - position     (int, görüntüleme sırası)

Vote
  - id
  - option       (FK -> Option, related_name="votes", on_delete=CASCADE)
  - poll         (FK -> Poll)   # kısıtlama için denormalize
  - user         (FK -> User, null=True, blank=True)
  - voter_key    (CharField, null=True, blank=True)  # anonim oy için rastgele UUID
  - created_at
```

**Kısıtlar**
- Seçenek sayısı 2–5: serializer/view düzeyinde doğrula (modelde değil).
- Oy tekilliği: `UniqueConstraint(fields=[poll, user], condition=user not null)` ve `UniqueConstraint(fields=[poll, voter_key], condition=voter_key not null)`.
- Bir `Vote` ya `user` ya `voter_key` taşır, ikisi birden boş olamaz.
- Oy sayıları `Vote` tablosundan `Count` ile hesaplanır (ayrı sayaç alanı tutma).

**Anonim oy mantığı (kasıtlı olarak basit):** İstemci ilk ziyarette `localStorage`'a rastgele bir UUID (`voter_key`) yazar ve oy isteğiyle gönderir. Bu sadece "aynı tarayıcıdan tekrar oy vermeyi" zorlaştırır; IP, parmak izi veya başka takip mekanizması **kullanılmaz**. Giriş yapmış kullanıcının oyu `user` ile bağlanır. Kullanıcı oyunu değiştiremez (prototip kararı).

## 4. API Uç Noktaları

Hepsi JSON; Django session + CSRF kullanır (JS, `csrftoken` çerezini `X-CSRFToken` başlığı olarak gönderir).

| Metot | Yol | Açıklama | Yetki |
|---|---|---|---|
| POST | `/api/auth/register/` | `email`, `username`, `password` ile kayıt, ardından otomatik giriş | herkes |
| POST | `/api/auth/login/` | `email` + `password` ile giriş | herkes |
| POST | `/api/auth/logout/` | çıkış | giriş yapmış |
| GET | `/api/auth/me/` | mevcut kullanıcı veya `null` | herkes |
| GET | `/api/polls/?page=1` | anket listesi, en yeni önce, sayfa başı 10 | herkes |
| POST | `/api/polls/` | `{question, options: [..2-5..]}` ile anket oluştur | **giriş yapmış** |
| GET | `/api/polls/<id>/` | tek anket | herkes |
| POST | `/api/polls/<id>/vote/` | `{option_id, voter_key?}` ile oy ver | herkes |

**Anket yanıt biçimi**
```json
{
  "id": 12,
  "question": "Bugün sinemaya mı tiyatroya mı gitsem?",
  "author": "ayse_k",
  "created_at": "2026-10-06T14:20:00Z",
  "total_votes": 7,
  "options": [
    {"id": 31, "text": "Sinema", "votes": 4},
    {"id": 32, "text": "Tiyatro", "votes": 3}
  ],
  "my_vote": 31
}
```
`my_vote`: giriş yapmış kullanıcı için kendi oyu; anonim için istekle gelen `voter_key` eşleşirse; yoksa `null`.

**Hata kuralları:** doğrulama hatası → `400` + `{"errors": {...}}`; yetkisiz → `401`; tekrar oy → `409`. Hata mesajları **Türkçe** olsun.

**Kayıt doğrulaması:** e-posta geçerli ve benzersiz; kullanıcı adı benzersiz (büyük/küçük harfe duyarsız), 3–20 karakter, `[A-Za-z0-9_]`; parola en az 8 karakter (Django parola doğrulayıcıları yeterli).

## 5. Sayfalar (Frontend)

Dil: **Türkçe**. Tek sayfa uygulaması yapma; basit çok sayfalı yapı:

| Yol | Sayfa | İçerik |
|---|---|---|
| `/` | Ana sayfa | Anket akışı (kartlar), "Daha fazla yükle" butonu, sağ üstte Giriş/Kayıt veya kullanıcı adı + Çıkış |
| `/anket/<id>/` | Anket detay | Tek anket, oy verme, sonuçlar (paylaşılabilir link) |
| `/yeni/` | Anket oluştur | Soru + 2–5 seçenek (dinamik ekle/çıkar). Giriş yoksa `/giris/`e yönlendir |
| `/giris/` | Giriş | e-posta + parola |
| `/kayit/` | Kayıt | e-posta + kullanıcı adı + parola |

**Davranışlar**
- Oy verilmeden önce sonuçlar gizli, oy verildikten sonra yüzde çubukları animasyonla görünür. Oy verdiği şık işaretli olur. (Daha önce oy vermiş biri sayfayı açınca doğrudan sonuçları görür.)
- Anket kartında: soru, "@kullanici_adi", göreli zaman ("2 saat önce"), toplam oy.
- Giriş yapmamış kullanıcı `/yeni/`ye gitmek isterse giriş sayfasına yönlendirilir, giriş sonrası geri döner.
- Form hataları alanın altında kırmızı metinle gösterilir.
- Boş durum: hiç anket yoksa "İlk anketi sen aç!" mesajı + buton.

**Dosya yapısı (statik):** `static/css/style.css`, `static/js/api.js` (fetch + CSRF yardımcıları), `static/js/app.js` (sayfaya özel kod; sayfa `data-page` özniteliğine göre başlar). Her sayfa için ayrı büyük JS dosyası gerekmez.

## 6. Tasarım Yönergesi

Hedef kitle: gençler. Hava: neşeli, enerjik, oyunbaz — ama okunaklı.

- **Arka plan açık** (kırık beyaz, ör. `#FFFBF5`); kartlar beyaz, yumuşak gölgeli, büyük köşe yuvarlaklığı (16–20px).
- **Canlı renk paleti** (CSS değişkeni olarak tanımla):
  - `--pembe: #FF4D8D`
  - `--mor: #7C4DFF`
  - `--sari: #FFC83D`
  - `--turkuaz: #1ED6C4`
  - `--koyu: #1E1B2E` (metin)
- Seçenek çubukları ve butonlar bu renkleri döngüsel kullanır (her şık farklı renk).
- Kalın, yuvarlak başlık fontu (Google Fonts: **Poppins** veya **Baloo 2**); gövde için **Inter**.
- Butonlar dolgulu, hover'da hafif yukarı kayma/büyüme. Çubuk dolum animasyonu CSS transition ile.
- Mobil öncelikli (tek sütun), masaüstünde ortalanmış ~720px sütun.
- Karanlık mod **yok** (prototip kapsamı dışı). Erişilebilirlik: yeterli kontrast, odak halkaları, `label`'lar.
- Logo: metin tabanlı "kararsızım" + soru işareti vurgusu; görsel varlık gerekmez.

## 7. Depo Yapısı

```
kararsizim/
├── manage.py
├── requirements.txt
├── vercel.json
├── .env.example
├── .gitignore
├── README.md
├── config/               # Django proje ayarları (settings, urls, wsgi)
├── accounts/             # özel User modeli + auth API
├── polls/                # Poll/Option/Vote modelleri + API + sayfa view'ları
├── templates/            # base.html + sayfa şablonları
└── static/               # css/ js/
```

## 8. Ortam Değişkenleri (`.env.example`)

```
SECRET_KEY=
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1,.vercel.app
CSRF_TRUSTED_ORIGINS=https://*.vercel.app
DATABASE_URL=postgresql://postgres.xxxx:PAROLA@aws-0-xx.pooler.supabase.com:6543/postgres
```
Gerçek `.env` asla commit edilmez.

## 9. Fazlar

Her fazın sonunda: çalıştır, kısaca neyin yapıldığını özetle, **dur ve onay bekle**.

### Faz 0 — İskelet ve bağlantı
- Django projesi (`config`), uygulamalar `accounts` ve `polls`, `requirements.txt`, `.gitignore`, `.env.example`.
- Ayarlar: `dj-database-url`, WhiteNoise, DB session, Türkçe dil/saat dilimi (`tr`, `Europe/Istanbul`).
- Özel `User` modeli (**ilk migrasyondan önce!**), e-posta benzersiz.
- Supabase bağlantısını doğrula (`migrate` çalışsın). Supabase bilgilerini kullanıcıdan iste; yoksa geçici olarak SQLite ile devam etmeyi öner.
- **Bitiş kriteri:** `python manage.py runserver` açılır, boş bir ana sayfa gelir, migrasyonlar Supabase'e uygulanır.

### Faz 1 — Modeller ve Auth API
- `Poll`, `Option`, `Vote` modelleri + kısıtlar + migrasyon.
- `/api/auth/*` uç noktaları, doğrulamalar, Türkçe hata mesajları.
- Admin paneline modelleri kaydet (hızlı kontrol için).
- **Bitiş kriteri:** curl/Python ile kayıt, giriş, çıkış, `me` çalışıyor. Birkaç temel test (`manage.py test`).

### Faz 2 — Anket API
- Liste (sayfalı), detay, oluşturma (2–5 seçenek doğrulaması, giriş şartı), oy verme (tekrar oy engeli, anonim `voter_key`).
- Sorguları verimli tut (`prefetch_related`, `annotate(Count)`); N+1 olmasın.
- **Bitiş kriteri:** tüm kurallar testlerle doğrulanır (1 seçenek reddedilir, 6 seçenek reddedilir, anonim anket açamaz, aynı kişi iki kez oy veremez).

### Faz 3 — Frontend
- `base.html`, stil dosyası (Bölüm 6), tüm sayfalar (Bölüm 5), `api.js` + `app.js`.
- Önce ana sayfa + oy verme, sonra giriş/kayıt, en son anket oluşturma.
- **Bitiş kriteri:** tüm akış tarayıcıdan uçtan uca çalışıyor; mobil genişlikte düzgün görünüyor.

### Faz 4 — Vercel'e dağıtım
- `vercel.json` (Python runtime, WSGI giriş noktası, tüm istekleri Django'ya yönlendir), `collectstatic` build adımı, ortam değişkenleri.
- Üretim ayarları: `DEBUG=False`, `SECURE_*` çerez bayrakları, `CSRF_TRUSTED_ORIGINS`.
- README'ye kurulum ve dağıtım adımları.
- **Bitiş kriteri:** canlı URL'de kayıt, anket açma ve oy verme çalışıyor.

### Faz 5 — (Prototip sonrası, isteğe bağlı — şimdi YAPMA)
Anket silme (sahibi), anket bitiş süresi, kategori/etiket, basit hız sınırlama, e-posta doğrulama, parola sıfırlama, paylaş butonu, rastgele anket.

## 10. Kapsam Dışı (yapma)
Takip/arkadaşlık, yorum, beğeni, bildirim, profil sayfası, avatar, dosya yükleme, sosyal giriş, gerçek zamanlı güncelleme (WebSocket), çoklu dil, karanlık mod, admin dışı moderasyon, JS framework'ü veya derleme adımı (npm/webpack).

## 11. Çalışma Kuralları (Claude Code için)
- Tüm kullanıcıya dönük metinler **Türkçe**, kod ve değişken adları **İngilizce**.
- Kodu küçük ve okunur tut; fonksiyon-tabanlı view'lar yeterli, DRF gibi ek paket ekleme.
- Gizli bilgileri (parola, anahtar) koda veya sohbete yazma; yalnızca `.env` kullan.
- Belirsiz bir durumda varsayım yapıp ilerlemek yerine kısa bir soru sor.
- Her faz sonunda `git commit` önerisi sun (mesajlar Türkçe veya İngilizce, kısa).
- **Şimdi yalnızca istenen fazı yap.** Kullanıcı "Faz N'i başlat" diyene kadar sonraki faza geçme.
