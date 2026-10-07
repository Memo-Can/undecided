# Kararsızım

Kararsız kalınan konularda anket açıp oy verilen küçük bir prototip. Ayrıntılı plan: [docs/project.md](docs/project.md).

```
backend/    Django (API + sayfa view'ları): config/, accounts/, polls/, manage.py, requirements.txt
frontend/   templates/ (Django şablonları) ve static/ (CSS + düz JS)
vercel.json Vercel işlev ayarı (kök dizinde)
```

Backend, frontend dosyalarını `backend/config/settings.py` içindeki `FRONTEND_DIR` üzerinden okur; aynı kaynaktan servis edildiği için oturum ve CSRF çerezleri ek ayar istemez.

## Yerelde çalıştırma

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp backend/.env.example backend/.env   # SECRET_KEY ve DATABASE_URL'i doldur
cd backend
../.venv/bin/python manage.py migrate
../.venv/bin/python manage.py runserver
../.venv/bin/python manage.py test
```

`DATABASE_URL` boşsa SQLite (`backend/db.sqlite3`) kullanılır. `DEBUG=True` değilse `SECRET_KEY` zorunludur.

## Supabase

1. Supabase'de proje aç: **Project Settings → Database → Connection string → Transaction pooler** (port **6543**).
2. Bu adresi `backend/.env` içine `DATABASE_URL` olarak yaz (parolayı koda veya sohbete yazma).
3. Şemayı bir kez uygula: `cd backend && ../.venv/bin/python manage.py migrate`

## Vercel'e dağıtım

Vercel, `backend/manage.py` dosyasını bulup Django'yu otomatik algılar, `collectstatic`'i kendisi çalıştırır ve statik dosyaları CDN'den sunar. Projeyi **kök dizinden** (Root Directory boş) içe aktar.

1. Projeyi Vercel'e bağla (Git deposu ya da `vercel` CLI).
2. **Settings → Environment Variables** altına (Production) şunları ekle:

   | Değişken | Değer |
   |---|---|
   | `SECRET_KEY` | uzun rastgele bir değer (`python -c "import secrets; print(secrets.token_urlsafe(50))"`) |
   | `DEBUG` | `False` |
   | `ALLOWED_HOSTS` | `.vercel.app` (özel alan adın varsa onu da ekle) |
   | `CSRF_TRUSTED_ORIGINS` | `https://*.vercel.app` (özel alan adı için `https://alanadi.com`) |
   | `DATABASE_URL` | Supabase pooler adresi (port 6543) |

3. Deploy et. `SECRET_KEY` build sırasında da gerekir; değişkenleri deploy'dan önce ekle.
4. Şemayı Supabase'e uyguladığından emin ol (yukarıdaki `migrate`).
5. Canlı URL'de kayıt ol, anket aç ve oy ver.

Üretimde (`DEBUG=False`) çerezler `Secure` işaretlenir ve `X-Forwarded-Proto` başlığına güvenilir.
