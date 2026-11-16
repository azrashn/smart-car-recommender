# Katkı kuralları / Contributing

Bu dosya ekip içi çalışma kurallarını anlatır. Hoca commit geçmişini, tarihlerini ve logları incelediği için bu kurallar notu doğrudan etkiler.

## 1. Başlamadan önce (bir kez)

```bash
git config --global user.name  "Ad Soyad"
git config --global user.email "github-hesabindaki@eposta.com"   # GitHub'daki e-postayla aynı olmalı
```

E-posta GitHub hesabınızla eşleşmezse commitleriniz profilinize ve **Insights > Contributors** grafiğine düşmez.

## 2. Branch stratejisi (GitHub Flow)

- `main` her zaman çalışır durumdadır. **Doğrudan `main`'e push yapılmaz** (branch protection açık).
- Her issue için `main`'den yeni bir branch açılır:

| Tür | Branch adı örneği |
| --- | --- |
| Yeni özellik | `feat/T22-weighted-scoring` |
| Hata düzeltme | `fix/T05-price-filter` |
| Doküman | `docs/T27-algorithm` |
| Test | `test/T26-engine-tests` |
| Veri | `data/T18-add-5-vehicles` |
| Altyapı/CI | `chore/T54-ci` |

- Branch'ler kısa ömürlüdür: **en fazla 3 gün** açık kalır. Uzayan işi küçük PR'lara bölün.
- Uzun süren branch'inizi güncel tutmak için: `git fetch origin && git rebase origin/main`

```bash
git checkout main && git pull
git checkout -b feat/T22-weighted-scoring
# ... çalış, küçük commitler at ...
git push -u origin feat/T22-weighted-scoring
# GitHub'da PR aç → "Closes #<issue no>"
```

## 3. Pull request kuralları

- Her PR bir issue'ya bağlıdır (`Closes #12`).
- En az **1 onay** gerekir; modülün yedek gözden geçireni onaylar (plan dokümanındaki tablo).
- **CI yeşil olmadan merge edilmez.**
- **Merge yöntemi: "Create a merge commit" veya "Rebase and merge". "Squash and merge" kapalı.** Squash, bireysel commitleri tek commite indirir ve geliştirme geçmişini siler.
- PR'lar küçük tutulur; hedef 400 satırdan az değişiklik.
- `app/schemas/` altındaki ortak şemaları değiştiren PR'larda ilgili modül sahipleri etiketlenir.

## 4. Commit mesajı kuralları (Conventional Commits)

Format:

```
<tür>(<kapsam>): <kısa açıklama, emir kipinde, İngilizce, en fazla 72 karakter>

<isteğe bağlı gövde: NEDEN yapıldı, ne değişti>

Refs #<issue no>
```

**Türler:** `feat`, `fix`, `docs`, `test`, `refactor`, `style`, `chore`, `data`, `ci`

**Kapsamlar (modüller):** `catalog`, `db`, `data`, `prefs`, `i18n`, `engine`, `ai`, `cost`, `compare`, `ui`, `scenario`, `ci`, `readme`

**İyi örnekler:**

```
feat(engine): add hard budget and transmission filters
fix(cost): handle electric vehicles without L/100km value
test(engine): cover weight sensitivity for fuel economy
docs(ai): document prompt and Pydantic validation flow
data(catalog): add 5 SUV variants with spec sources
feat(scenario): debounce slider input to 250 ms
```

**Kötü örnekler:** `update`, `fix`, `asdf`, `son hali`, `final2`, `many changes`

## 5. Düzenli commit alışkanlığı

- Her çalışma oturumunda **en az bir anlamlı commit** atılır. Bir commit tek mantıksal değişikliktir.
- Haftada en az 4 farklı günde commit hedeflenir. Son gece toplu commit **yapılmaz**.
- Çalışmayan kod da commit edilebilir, ama `main`'e değil, kendi branch'inize.
- Commit tarihleri değiştirilmez (`--date`, `rebase` ile tarih oynamak yok). `push --force` yalnızca kendi branch'inizde ve gerekirse `--force-with-lease` ile.
- Birlikte kod yazıldıysa (pair programming) commit sonuna eklenir:

```
Co-authored-by: Ad Soyad <eposta@ornek.com>
```

## 6. Issue ve pano

- Her görev bir issue'dur; başlık `[Txx]` ile başlar.
- Etiketler: `module:M1`–`M6`, `type:code|docs|test|data`, `priority:P0|P1|P2`.
- Milestone'lar haftalara karşılık gelir: Hafta 1–4.
- Projects panosu kolonları: **Todo → In progress → In review → Done**.
- İşe başlayınca issue'yu "In progress"e çekin ve kısa bir yorum yazın.

## 7. Kod stili

- Python: `ruff format` + `ruff check`; fonksiyon ve değişken adları İngilizce.
- Arayüz metinleri koda yazılmaz, `app/static/i18n/tr.json` ve `en.json`'a eklenir.
- API anahtarları yalnızca `.env`'de tutulur; `.env` asla commit edilmez.

## 8. Sürüm

- Her haftanın sonunda tag atılır: `v0.1.0` (H1), `v0.2.0` (H2), `v0.3.0` (H3), `v1.0.0` (teslim).
- `v1.0.0` için GitHub Release notu yazılır.
