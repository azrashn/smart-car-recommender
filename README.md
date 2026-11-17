# AutoMatch — Smart Car Recommender

**Türkçe** | [English](README.en.md)

> Yapay zekâ destekli, açıklanabilir ve senaryo tabanlı araç öneri ve karar destek web platformu.
> SENG 461 dönem projesi.

![CI](https://github.com/azrashn/smart-car-recommender/actions/workflows/ci.yml/badge.svg)

---

## İçindekiler

1. [Amaç](#amaç)
2. [Kapsam](#kapsam)
3. [Özellikler](#özellikler)
4. [Mimari](#mimari)
5. [Teknolojiler](#teknolojiler)
6. [Kurulum](#kurulum)
7. [Kullanım](#kullanım)
8. [API](#api)
9. [Testler](#testler)
10. [Veri kaynakları](#veri-kaynakları)
11. [Proje yapısı](#proje-yapısı)
12. [Geliştirme süreci](#geliştirme-süreci)
13. [Ekip](#ekip)
14. [Lisans](#lisans)

---

## Amaç

Araç alırken bütçe, yakıt tüketimi, kullanım amacı, iç hacim ve güvenlik gibi pek çok kriteri birlikte değerlendirmek gerekiyor. AutoMatch, kullanıcının ihtiyaçlarını anketle ya da serbest metinle alıyor ve uygun araçları **puanlayıp gerekçesiyle** gösteriyor. Ayrıca kullanıcı yıllık kilometresini veya önceliklerini değiştirdiğinde **sıralamanın nasıl değiştiğini** gösteriyor.

<!-- TODO (T09): 2-3 cümlelik problem tanımı ve hedef kullanıcılar -->

## Kapsam

**Kapsamda:**

- 40 araç varyantından oluşan, kaynaklı ve tarihli araç kataloğu
- Anket ve serbest metinle (TR/EN) tercih girişi
- Kural tabanlı filtreleme ve ağırlıklı puanlama (0–100)
- Öneri açıklamaları ve çelişen tercihlerin açıklanması
- 2–3 aracı yan yana karşılaştırma ve yıllık yakıt/enerji maliyeti
- Scenario Lab: km, yakıt fiyatı ve öncelik değişince anlık yeniden sıralama

**Bilinçli olarak kapsam dışı:** kullanıcı hesapları, canlı ilan toplama, ikinci el fiyat tahmini, bakım/sigorta maliyeti, araç fotoğrafları, canlı yayına alma (deploy).

## Özellikler

<!-- TODO: Her modül sahibi kendi özelliğini 1-2 cümle + ekran görüntüsüyle ekler -->

| Özellik | Açıklama | Ekran görüntüsü |
| --- | --- | --- |
| Araç kataloğu | <!-- M1 --> | <!-- docs/img/catalog.png --> |
| İhtiyaç analizi | <!-- M2 --> | |
| Öneri motoru | Sert kısıt filtreleme (bütçe, vites, yakıt, koltuk, kasa), 0–100 ağırlıklı puanlama, güçlü/zayıf yan tespiti ve kısıt gevşetme önerileri. `app/engine/filters.py` saf Python fonksiyonları; veritabanı bağımlılığı yoktur. | |
| AI açıklamaları | <!-- M4 --> | |
| Karşılaştırma ve maliyet | <!-- M5 --> | |
| Scenario Lab | <!-- M6 --> | |

## Mimari

Tek bir FastAPI uygulaması JSON API'yi ve statik sayfaları sunar. Filtreleme, puanlama ve maliyet hesabı deterministik Python fonksiyonlarıyla yapılır. LLM yalnızca metinden tercih çıkarır ve hesaplanmış sonuçları açıklar; **AI kapalıyken de sistem tam çalışır.**

```
Tarayıcı (HTML/CSS/JS) ──HTTP──▶ FastAPI
                                   ├── catalog   (M1) ──▶ SQLite ◀── data/vehicles.csv
                                   ├── preferences (M2)
                                   ├── engine    (M3)
                                   ├── ai        (M4) ──▶ Gemini API (isteğe bağlı)
                                   ├── cost / compare (M5)
                                   └── scenarios (M6)
```

Ayrıntılar: [docs/architecture.md](docs/architecture.md)

## Teknolojiler

| Katman | Teknoloji |
| --- | --- |
| Backend | Python 3.11+, FastAPI, Uvicorn, Pydantic |
| Veritabanı | SQLite, SQLAlchemy 2 |
| Frontend | HTML, CSS, JavaScript, Chart.js |
| AI | Google Gemini API (isteğe bağlı), kural tabanlı yedek |
| Test ve kalite | pytest, pytest-cov, ruff, GitHub Actions |

## Kurulum

**Gereksinimler:** Python 3.11+ ve Git.

```bash
git clone https://github.com/azrashn/smart-car-recommender.git
cd smart-car-recommender

python -m venv .venv
# Windows:      .venv\Scripts\activate
# macOS/Linux:  source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env        # Windows: copy .env.example .env

python -m app.db.seed       # data/vehicles.csv → automatch.db
uvicorn app.main:app --reload
```

Tarayıcıda: <http://127.0.0.1:8000> — API dokümanı: <http://127.0.0.1:8000/docs>

### AI'ı açmak (isteğe bağlı)

1. [Google AI Studio](https://aistudio.google.com/)'dan bir API anahtarı alın.
2. `.env` dosyasında şunları ayarlayın:

```env
AI_PROVIDER=gemini
GEMINI_API_KEY=buraya-anahtar
```

`AI_PROVIDER=none` (varsayılan) iken kural ve şablon tabanlı yedekler kullanılır.

## Kullanım

<!-- TODO (T17): Adım adım kullanım + ekran görüntüleri. Ayrıntılı kılavuz: docs/user-guide.md -->

1. **Ana sayfa:** "Anketle başla" ya da "İhtiyacını yaz" seçeneklerinden birini seçin.
2. **Anket / metin:** Bütçenizi, kullanım tipinizi ve önceliklerinizi girin. Örnek metin: *"Şehir içinde kullanacağım, otomatik vites olsun, az yaksın, bütçem 1,5 milyon TL."*
3. **Sonuçlar:** İlk 5 araç; skor, güçlü ve zayıf yanlar ve açıklamayla listelenir.
4. **Karşılaştır:** En fazla 3 aracı seçip yan yana karşılaştırın.
5. **Scenario Lab:** Yıllık km, yakıt fiyatı ve öncelikleri değiştirip sıralamanın nasıl değiştiğini görün.

## API

| Method | Endpoint | Açıklama |
| --- | --- | --- |
| GET | `/api/vehicles` | Araç listesi ve filtreler |
| GET | `/api/vehicles/{id}` | Araç detayı |
| POST | `/api/preferences/form` | Anketten tercih |
| POST | `/api/preferences/text` | Serbest metinden tercih |
| POST | `/api/recommendations` | Öneriler veya çelişki raporu |
| GET | `/api/compare?ids=1,2,3` | Karşılaştırma |
| POST | `/api/scenarios` | Senaryo ile yeniden sıralama |

Sözleşme: [docs/api-contract.md](docs/api-contract.md)

## Testler

```bash
pip install -r requirements-dev.txt
pytest --cov=app
ruff check .
```

<!-- TODO (T56): Test özeti ve docs/test-report.md bağlantısı; ablation sonucu (T37) -->

## Veri kaynakları

Araç teknik bilgileri üreticilerin resmî sitelerinden derlendi. Her satırda kaynak bağlantısı ve kontrol tarihi bulunur. **Fiyatlar örnektir ve güncel olmayabilir.** Liste: [data/SOURCES.md](data/SOURCES.md)

Kolonlar, birimler ve izin verilen değerler: [docs/data-dictionary.md](docs/data-dictionary.md)

## Proje yapısı

```
app/        uygulama kodu (modül başına bir klasör)
data/       araç verisi (CSV) ve kaynak listesi
docs/       mimari, API, algoritma, test ve kullanım dokümanları
scripts/    yardımcı scriptler (ablation deneyi)
tests/      pytest testleri ve fixture'lar
```

## Geliştirme süreci

- Görevler: [GitHub Issues](https://github.com/azrashn/smart-car-recommender/issues) ve [Projects panosu](https://github.com/azrashn/smart-car-recommender/projects)
- Branch ve commit kuralları: [CONTRIBUTING.md](CONTRIBUTING.md)
- Sürümler: [Releases](https://github.com/azrashn/smart-car-recommender/releases)

## Ekip

| Üye | GitHub | Modül | Sorumluluk |
| --- | --- | --- | --- |
| Belis Özçelik | [@Belisozcelik](https://github.com/Belisozcelik) | M1 | Araç verisi ve katalog |
| Fatih Oğuz Kaya | [@fatihoguzkaya](https://github.com/fatihoguzkaya) | M2 | Tercih girişi ve çok dillilik |
| Karya Demirciler | [@karya-karya](https://github.com/karya-karya) | M3 | Öneri motoru |
| Orhan Çardak | [@orhancardak](https://github.com/orhancardak) | M4 | AI katmanı |
| Sude Karakoç | [@SudeKarakoc1](https://github.com/SudeKarakoc1) | M5 | Karşılaştırma, maliyet ve sonuç arayüzü |
| Esma Azra Şahin | [@azrashn](https://github.com/azrashn) | M6 | Scenario Lab, test ve CI |

## Lisans

<!-- Ekip kararı: MIT veya "yalnızca eğitim amaçlı" -->
Bu proje SENG 461 dersi kapsamında eğitim amacıyla geliştirilmiştir.
