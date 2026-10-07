# Kararsızım

Kullanıcıların kararsız kaldıkları konularda anket açtığı, herkesin oy verebildiği bir prototip. Ana plan: [docs/project.md](docs/project.md) (faz listesi, veri modeli, API, tasarım). Çalışmaya başlamadan önce oku.

## Çalışma kuralları
- Her seferinde **yalnızca istenen fazı** yap; kullanıcı "Faz N'i başlat" demeden sonraki faza geçme. Faz sonunda özetle, dur, onay bekle.
- Prototip: basit tut. DRF, JS framework'ü, npm/build adımı ve plandaki "kapsam dışı" özellikleri ekleme. Yeni paket ekleme (`requirements.txt` minimal kalsın).
- Kullanıcıya dönük metinler **Türkçe**, kod ve değişken adları **İngilizce**.
- Gizli bilgileri (parola, anahtar, `DATABASE_URL`) koda veya sohbete yazma; yalnızca `.env`. `.env` commit edilmez.
- Belirsiz durumda varsayım yapmak yerine kısa soru sor.
- **Commit ve push'u kullanıcı yapar.** `git commit`, `git commit --amend`, `git push` çalıştırma. Faz sonunda yalnızca ne değiştiğini ve önerilen bir commit mesajını (faz adıyla) söyle.

## Komutlar
```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt   # kök requirements.txt -> backend/requirements.txt
cd backend
../.venv/bin/python manage.py migrate
../.venv/bin/python manage.py runserver
../.venv/bin/python manage.py test
```
**Testleri her zaman SQLite ile çalıştır** (`backend/.env`'deki `DATABASE_URL` Supabase'i gösterir; `manage.py test` onu kullanırsa Supabase'te `test_postgres` veritabanı açar, yavaştır ve geride kalır):
```bash
cd backend && DATABASE_URL=sqlite:///:memory: ../.venv/bin/python manage.py test
```
`DATABASE_URL` yoksa SQLite (`backend/db.sqlite3`, gitignore'da) kullanılır. Supabase için `backend/.env.example`'ı `backend/.env` olarak kopyalayıp doldur (pooler, port 6543). `DEBUG=True` değilse `SECRET_KEY` zorunlu (testler hariç).

## Yapı
- `backend/`: Django. `config/` ayarlar ve kök URL'ler, `accounts/` özel `User` (benzersiz e-posta) ve `/api/auth/*`, `polls/` modeller, `/api/polls/*` ([views_api.py](backend/polls/views_api.py)) ve sayfa view'ları ([views.py](backend/polls/views.py)).
- `frontend/`: düz HTML/CSS/JS. `templates/` Django şablonları, `static/{css,js}`. Sayfa kodu `static/js/app.js` içinde `data-page` özniteliğine göre başlar; fetch/CSRF yardımcıları `api.js`'te. Django bunları `FRONTEND_DIR` ile okur (aynı origin: oturum/CSRF kolay).
- Kökte: `vercel.json`, `requirements.txt` (backend'inkini işaret eder), `.python-version`, `README.md` (kurulum ve dağıtım), `docs/project.md` (plan).

## Kasıtlı kararlar
- Auth'u Django yapar (session, veritabanında); Supabase yalnızca Postgres'tir. Supabase Auth/JS SDK yok.
- Anonim oy: istemci `localStorage`'a UUID `voter_key` yazar. IP/parmak izi yok. Anonim `my_vote` için GET isteklerine `?voter_key=` eklenir.
- Kullanıcı oyunu değiştiremez. Oy sayıları `Vote` tablosundan `Count` ile hesaplanır, sayaç alanı yok.
- Seçenek sayısı (2–5) model değil view düzeyinde doğrulanır.
- `annotate(Count)` ile gruplanan sorgularda `Meta.ordering` yok sayılır; sıralama için `.order_by(...)` açıkça yazılmalı (seçenek sırası böyle bozulmuştu, testle sabitli).
- Liste ve detay sorguları N+1 içermemeli (`prefetch_related` + `annotate(Count)`); testle sabitlenmiştir.
- Supabase pooler için `CONN_MAX_AGE=0` ve `DISABLE_SERVER_SIDE_CURSORS`.
- Statik dosyalar WhiteNoise ile; varsayılan `StaticFilesStorage`; Vercel `collectstatic`'i kendisi çalıştırıp CDN'den sunar.

- Supabase'de tüm `public` tablolarında RLS **açık, politikasız** (Data API/anon anahtarı üzerinden erişimi kapatır; Django `postgres` rolüyle bağlandığı için etkilenmez). Yeni bir migrasyon tablo eklerse o tablo için de `ALTER TABLE public.<tablo> ENABLE ROW LEVEL SECURITY;` çalıştır (Supabase `apply_migration` ile) ve `list_tables` ile doğrula.

## Durum
Faz 0–4 hazırlandı. Supabase bağlantısı doğrulandı (migrasyonlar uygulandı, RLS açık). Vercel projesi `undecided` oluşturuldu (kişisel hesap, framework Django; `DEBUG`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS` girildi) ama henüz deploy edilmedi: kullanıcının `SECRET_KEY` ve `DATABASE_URL`'i Vercel panelinden girmesi bekleniyor (gizli değerleri ben girmem). Proje varsayılan olarak Vercel Authentication açık; herkese açık site için Deployment Protection kapatılmalı. Supabase bölgesi ap-south-1 olduğu için işlev bölgesi `bom1` önerilir. GitHub remote tanımlı (`Memo-Can/undecided`), push kullanıcıda. Faz 5 isteğe bağlı, istenmedikçe yapılmaz.
