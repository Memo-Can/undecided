---
name: security-audit
description: Kararsızım (undecided) projesinde güvenlik açıklarını tarar, önem sırasıyla raporlar ve onay verilen bulguları düzeltir. Kullanıcı "güvenlik taraması", "security audit", "güvenlik açığı var mı", "güvenlik hatalarını bul/düzelt" ya da yayına çıkmadan önce güvenlik kontrolü istediğinde kullan. Genel kod incelemesi için değil, yalnızca güvenlik içindir.
---

# Kararsızım güvenlik taraması

Projeye özel güvenlik denetimi. İki aşamalıdır: **önce bul ve raporla, sonra yalnızca onaylananı düzelt.**

## Değişmez kurallar
- **Commit ve push yapma.** Düzeltmeden sonra yalnızca değişen dosyaları ve önerilen commit mesajını (faz adıyla) söyle.
- **Gizli değerleri okuma, yazma ya da sohbete basma:** `backend/.env`, Vercel/Supabase parolaları, `SECRET_KEY`, `DATABASE_URL`. Bir değişkenin var olup olmadığını ve biçimini kontrol edebilirsin (şema, host, port), değerini gösterme.
- **Canlı veriye dokunma.** Üretim veritabanında (Supabase) satır silme/değiştirme, veritabanı silme yok; yalnızca okuma ve onaylanmış `ENABLE ROW LEVEL SECURITY` tipi sertleştirme.
- **Testleri SQLite ile çalıştır:** `cd backend && DATABASE_URL=sqlite:///:memory: ../.venv/bin/python manage.py test`. Supabase'e karşı çalıştırma (`test_postgres` bırakır).
- **Canlı siteyi saldırı amaçlı yoğun taramadan koru:** `https://undecided-memo-team1.vercel.app` üzerinde yalnızca birkaç normal GET/POST dene; brute-force, yük ya da hız sınırı testi yapma. Hız sınırı eksikliğini kodu okuyarak tespit et.
- Yeni paket ekleme (`requirements.txt` minimal kalsın). Gerekirse araçları geçici çalıştır (`uvx`), projeye ekleme.
- Kullanıcıya dönük metin Türkçe, kod İngilizce.

## Aşama 1 — Tara (yalnızca oku)

Aşağıdaki başlıkları sırayla gez. Her bulgu için **dosya:satır**, kanıt ve gerçekçi sömürü senaryosu yaz; kanıtı olmayan şeyi bulgu sayma.

### A. Gizli bilgi sızıntısı
- `git ls-files | grep -iE '\.env|secret|key|\.pem'` → `.env` takip ediliyor mu? (`.env.example` dışında hiçbir `.env` olmamalı.)
- Git geçmişinde sızıntı: `git log -p --all -S 'postgresql://' -- . ':!*.example'` ve `-S 'SECRET_KEY='` ile parola/anahtar sabitlenmiş mi bak.
- Kodda sabit gömülü sır: `grep -rnE "(password|secret|token|api_key)\s*=\s*['\"][^'\"]+" backend frontend --include=*.py --include=*.js --include=*.html` (test parolaları `guclu-parola-1` gibi bilinen test verileri hariç).
- `settings.py`: `SECRET_KEY` üretimde zorunlu mu, dev varsayılanı yalnızca `DEBUG`/test'te mi çalışıyor?
- `.gitignore`: `.env`, `.venv`, `db.sqlite3`, `staticfiles/`, `.vercel/`.

### B. Django yapılandırması
- `cd backend && SECRET_KEY=x DEBUG=False ../.venv/bin/python manage.py check --deploy` çıktısını yorumla. Bilinen ve **bilinçli** uyarılar: `SECURE_HSTS_SECONDS` (geri alınması zor; Vercel zaten HTTPS'e yönlendiriyor) ve `SECURE_SSL_REDIRECT`. Bunlar dışındakiler yeni bulgudur.
- `DEBUG` varsayılanı `False` mı? `ALLOWED_HOSTS` joker (`*`) içeriyor mu? (`.vercel.app` bilinçli.)
- `CSRF_TRUSTED_ORIGINS` yalnızca `https://` ve gereken alan adlarını içeriyor mu? (`https://*.vercel.app` bilinçli ama herhangi bir Vercel projesine güveniyor; özel alan adı eklenince daralt.)
- Üretimde çerezler: `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `SECURE_PROXY_SSL_HEADER`. `SESSION_COOKIE_HTTPONLY` kapatılmamış olmalı; `CSRF_COOKIE_HTTPONLY` bilinçli olarak kapalı (JS çerezi okuyor).
- Middleware: `SecurityMiddleware`, `CsrfViewMiddleware`, `XFrameOptionsMiddleware`, `AuthenticationMiddleware` yerinde mi?
- `/admin/` herkese açık. Parola politikası (`AUTH_PASSWORD_VALIDATORS`) etkin mi? Admin yolunu gizleme ya da ek koruma gerekir mi, değerlendir.

### C. Kimlik doğrulama ve oturum (`backend/accounts/views.py`)
- Parola doğrulayıcıları çalışıyor mu, parola hiçbir yerde loglanıyor/dönüyor mu?
- Kullanıcı numaralandırma: kayıt `Bu e-posta adresi zaten kayıtlı` / `Bu kullanıcı adı alınmış` ile hesabın varlığını sızdırıyor (UX gereği kabul edilmiş olabilir, riskini yaz). Giriş hata mesajı ise genel kalmalı (`E-posta veya parola hatalı.`).
- `login`/`register` GET ile tetiklenemiyor (`require_POST`), `logout` oturum kontrolü yapıyor mu?
- E-posta eşleşmesi büyük/küçük harfe duyarsız (`iexact`) ve `authenticate` her zaman çağrılıyor mu (zamanlama farkı)?
- **Hız sınırı yok** (Faz 5'te planlı): giriş, kayıt, anket oluşturma ve oy uç noktalarında brute-force/spam riski. Bulgu olarak yaz; çözüm paket gerektirir, kullanıcı onayı iste (Faz 5 kapsamı).

### D. Yetkilendirme ve iş mantığı (`backend/polls/views_api.py`)
- Anket oluşturma gerçekten giriş şartı arıyor mu (`401`)?
- Oy: tek oy kısıtları hem uygulama hem veritabanı düzeyinde (`UniqueConstraint`) var mı; yarış durumu `IntegrityError` ile yakalanıyor mu?
- Seçenek başka ankete ait olamıyor (`option_id` + `poll_id` birlikte sorgulanıyor).
- Girdi sınırları: soru ≤200, seçenek ≤100, 2–5 seçenek, `voter_key` ≤64 karakter; JSON gövde tipleri doğrulanıyor (liste/sözlük/bool tuzakları).
- `voter_key` istemci kontrollü (bilinçli tasarım): aynı kişi `voter_key` değiştirerek tekrar oy verebilir. Bunu kabul edilmiş tasarım riski olarak not et, "bulgu" olarak şişirme.
- IDOR: başka kullanıcıya ait veriyi okuyan/değiştiren uç nokta var mı? (Şu an `my_vote` yalnızca çağıranın verisi.)
- ORM dışı SQL: `grep -rn "raw(\|extra(\|cursor()\|execute(" backend --include=*.py` (migrasyonlar hariç) → SQL enjeksiyonu.

### E. İstemci tarafı (`frontend/`)
- XSS: kullanıcı kaynaklı metin (soru, seçenek, kullanıcı adı) DOM'a `textContent`/`createTextNode` ile mi basılıyor? `innerHTML`, `insertAdjacentHTML`, `outerHTML`, `document.write`, `eval` arat: `grep -rnE "innerHTML|insertAdjacentHTML|outerHTML|document\.write|eval\(" frontend`.
- Şablonlarda `|safe`, `{% autoescape off %}`, `mark_safe` kullanımı: `grep -rnE "\|safe|autoescape|mark_safe" frontend backend`.
- Açık yönlendirme: `app.js` içindeki `safeNext()` yalnızca `/` ile başlayan ve `//` ile başlamayan yolları kabul etmeli (`/\evil.com` gibi tarayıcıda host'a dönüşen biçimleri de düşün).
- Üçüncü taraf kaynaklar: yalnızca Google Fonts. SRI/CSP yok → CSP eklemeyi öneri olarak yaz (düşük öncelik).
- `localStorage` yalnızca rastgele `voter_key` tutuyor, başka hassas veri yok.

### F. Veritabanı ve altyapı
- **Supabase RLS:** MCP `list_tables` ile `public` şemasında her tablonun `rls_enabled: true` olduğunu doğrula (yeni migrasyon tablo eklediyse kapalı kalabilir — en sık kaçan şey). Kapalı tablo = anon anahtarıyla herkese açık (kritik).
- Supabase `get_advisors` (security) çıktısını oku.
- Bağlantı `postgresql://` + pooler (6543) ve `sslmode` üretimde makul mü? Parola URL'de, yalnızca ortam değişkeninde olmalı.
- Artık veritabanları: `select datname from pg_database where datname like 'test%'` (ör. `test_postgres`) — silmeyi kullanıcıya bırak.
- Vercel: Vercel Authentication/Deployment Protection durumu bilinçli mi, ortam değişkenleri `Sensitive` mi (panelden kullanıcı kontrol eder; erişimin yoksa kullanıcıya sor).

### G. Bağımlılıklar
- `uvx pip-audit -r requirements.txt` (kök dosya `backend/requirements.txt`'yi işaret eder) ya da `../.venv/bin/pip list --outdated`. Django 5.2.x güvenlik yamalarını izle; bilinen CVE'li sürüm varsa en küçük güvenli güncellemeyi öner.

## Aşama 2 — Raporla

Bulguları şu biçimde, önem sırasıyla (Kritik → Yüksek → Orta → Düşük → Bilgi) sun:

| # | Önem | Başlık | Konum | Kanıt / sömürü | Önerilen düzeltme |
|---|---|---|---|---|---|

Ardından üç ayrı liste ver: **Düzelttim**, **Onayını bekleyen**, **Bilinçli/kabul edilmiş risk** (ör. HSTS yok, anonim `voter_key`, kayıtta numaralandırma). Bilinçli riskleri her taramada yeniden "bulgu" diye şişirme; yalnızca durum değiştiyse belirt.

## Aşama 3 — Düzelt (yalnızca onaydan sonra)

1. Kullanıcıdan hangi bulguların düzeltileceğini öğren. Onaylanmayana dokunma.
2. Her düzeltmeyi **küçük ve yerel** tut; mimariyi değiştirme, yeni paket ekleme, plandaki "kapsam dışı" özellikleri getirme.
3. Her düzeltme için **regresyon testi** ekle (SQLite ile çalıştır). Güvenlik düzeltmesi testsiz kalmasın.
4. Tüm testleri çalıştır, tarayıcıda ya da `Client` ile ilgili akışı doğrula.
5. Değişen dosyaları ve önerilen commit mesajını (örn. `Faz 4: güvenlik – <kısa açıklama>`) özetle; commit/push'u kullanıcı yapar.
6. Düzeltme yeni bir tablo/migrasyon getirdiyse Supabase'te RLS'i açmayı kullanıcıya hatırlat.
7. `CLAUDE.md` "Kasıtlı kararlar" bölümüne yeni kalıcı bir güvenlik kararı eklenmeliyse öner.

## Sık düzeltme kalıpları (bu projede)
- **XSS:** `innerHTML` yerine `textContent`; şablonda `|safe` kaldır.
- **Eksik giriş şartı:** view başında `request.user.is_authenticated` kontrolü + `401`.
- **Girdi doğrulama:** tip kontrolü (`isinstance`), uzunluk sınırı, bool/`None` tuzakları; hata `400` + `{"errors": {...}}`, Türkçe mesaj.
- **Açık yönlendirme:** yalnızca tek `/` ile başlayan yollar; `\` ve `//` reddedilir.
- **RLS:** `ALTER TABLE public.<tablo> ENABLE ROW LEVEL SECURITY;` (Supabase `apply_migration`), sonra `list_tables` ile doğrula.
- **Hız sınırı:** Faz 5 kapsamı; paket gerektiriyorsa önce kullanıcıdan onay al.
