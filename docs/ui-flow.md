# AutoMatch UI Akışı ve Wireframe'ler

> **Not:** Endpoint'ler taslaktır; `docs/api-contract.md` merge olunca doğrulanacak.

Proje: AutoMatch (smart-car-recommender). Vanilla HTML/CSS/JS + FastAPI, tek servis.
Tüm sayfalar `app/static/` altındadır. UI metinleri kodda değil, `app/static/i18n/tr.json` ve `en.json` içinde tutulur; bu dokümanda yalnızca anahtar önerisi verilir.

## 1. Sayfa akış diyagramı

```mermaid
flowchart TD
    index[index.html] --> survey[survey.html]
    survey --> results[results.html]
    results --> compare[compare.html]
    compare --> scenario[scenario.html]
    catalog[catalog.html] --> compare
```

- `catalog.html` ayrı bir giriş noktasıdır; kullanıcı anket yapmadan doğrudan katalogdan karşılaştırmaya geçebilir.
- Ortak menü sayesinde her sayfadan diğer tüm sayfalara geçilebilir; diyagramı sadeleştirmek için bu oklar çizilmemiştir.

## 2. Sayfa tablosu

| Sayfa | Amaç | Endpoint(ler) | i18n öneki | Sahip modül |
| --- | --- | --- | --- | --- |
| `index.html` | Uygulamayı tanıtır ve kullanıcıyı ankete yönlendirir. | yok | `index.*` | M5 |
| `survey.html` | Kullanıcının tercihlerini form veya serbest metin ile toplar. | `POST /api/preferences/form`, `POST /api/preferences/text` | `survey.*` | M2 |
| `results.html` | Tercihlere göre ilk 5 aracı skor ve gerekçeyle listeler. | `POST /api/recommendations` | `results.*` | M5 |
| `catalog.html` | Tüm araçları listeler ve detayını gösterir. | `GET /api/vehicles`, `GET /api/vehicles/{id}` | `catalog.*` | M1 |
| `compare.html` | 2-3 aracı yan yana tablo ve grafikle karşılaştırır. | `GET /api/compare?ids=1,2,3` | `compare.*` | M5 |
| `scenario.html` | Varsayımlar değişince sıralamanın nasıl değiştiğini gösterir. | `POST /api/scenarios` | `scenario.*` | M6 |

Ortak menü anahtarları `nav.*` önekini kullanır (bkz. bölüm 4).

## 3. Wireframe'ler

Metinler kısa yer tutucudur; gerçek metinler i18n dosyalarından gelir.

### 3.1 index.html

```text
+--------------------------------------------------+
| [Logo] Ana sayfa | Anket | Sonuçlar | Katalog |   |
|        Karşılaştır | Scenario Lab        [TR|EN]  |
+--------------------------------------------------+
|                                                  |
|            AutoMatch                             |
|      <kısa slogan: index.subtitle>               |
|                                                  |
|          [ Ankete başla ]                        |
|          [ Kataloğa göz at ]                     |
|                                                  |
+--------------------------------------------------+
| <3 kısa özellik kutusu>                          |
| [ Özellik 1 ] [ Özellik 2 ] [ Özellik 3 ]        |
+--------------------------------------------------+
```

### 3.2 survey.html

```text
+--------------------------------------------------+
| <ortak menü>                                     |
+--------------------------------------------------+
| Anket                                            |
| [ Form ] [ Serbest metin ]        <sekmeler>     |
+--------------------------------------------------+
| (Form sekmesi)                                   |
|  Bütçe:        [ min ____ ] [ max ____ ]         |
|  Gövde tipi:   [ v seçiniz ]                     |
|  Yakıt tipi:   [ v seçiniz ]                     |
|  Vites:        ( ) Manuel  ( ) Otomatik          |
|  Öncelikler:   [x] Yakıt ekonomisi [ ] İç hacim  |
|                [ ] Performans [ ] Bütçeye uygunluk|
|                [ ] Güvenlik                      |
|                                                  |
|  [ Önerileri göster ]                            |
+--------------------------------------------------+
| (Serbest metin sekmesi)                          |
|  +--------------------------------------------+  |
|  | <ne aradığınızı yazın...>                  |  |
|  +--------------------------------------------+  |
|  [ Önerileri göster ]                            |
+--------------------------------------------------+
```

### 3.3 results.html

```text
+--------------------------------------------------+
| <ortak menü>                                     |
+--------------------------------------------------+
| Sonuçlar - ilk 5 araç                            |
| <tercih özeti: bütçe, yakıt, ...>  [ Anketi düzenle ] |
+--------------------------------------------------+
| #1 +--------------------------------------------+|
|    | [kasa ikonu]  Marka Model      [ ] Karşılaştır|
|    | Fiyat: <fiyat> (örnek fiyat, <tarih> kontrol edildi) |
|    | Skor: [##########----] 82/100              ||
|    | Güçlü:  + yakıt ekonomisi  + fiyat         ||
|    | Zayıf:  - bagaj hacmi                      ||
|    | Açıklama: <neden önerildiğini anlatan metin>||
|    +--------------------------------------------+|
| #2 +--------------------------------------------+|
|    | ... aynı kart yapısı ...                   ||
|    +--------------------------------------------+|
| #3 ... #4 ... #5                                 |
+--------------------------------------------------+
| [ Seçilenleri karşılaştır ]                      |
+--------------------------------------------------+
```

### 3.4 catalog.html

```text
+--------------------------------------------------+
| <ortak menü>                                     |
+--------------------------------------------------+
| Katalog                                          |
| Filtre: [ Marka v ] [ Yakıt v ] [ Gövde v ]      |
|         [ Fiyat min-max ]            [ Ara ]     |
+--------------------------------------------------+
| +------------+ +------------+ +------------+     |
| |[kasa ikonu]| |[kasa ikonu]| |[kasa ikonu]|     |
| | Marka M.   | | Marka M.   | | Marka M.   |     |
| | <fiyat>*   | | <fiyat>*   | | <fiyat>*   |     |
| | [Detay]    | | [Detay]    | | [Detay]    |     |
| | [ ] Seç    | | [ ] Seç    | | [ ] Seç    |     |
| +------------+ +------------+ +------------+     |
| * örnek fiyat, <tarih> kontrol edildi            |
+--------------------------------------------------+
| [ Seçilenleri karşılaştır ]                      |
+--------------------------------------------------+
```

Araç detayı (`GET /api/vehicles/{id}`) için ayrı sayfa mı, modal mı olacağı TBD.

### 3.5 compare.html

```text
+--------------------------------------------------+
| <ortak menü>                                     |
+--------------------------------------------------+
| Karşılaştır (2-3 araç)          [ Araç ekle/çıkar ] |
+--------------------------------------------------+
| Özellik      | Araç A    | Araç B    | Araç C    |
|--------------+-----------+-----------+-----------|
| Fiyat        | ...       | ...       | ...       |
| Yakıt        | ...       | ...       | ...       |
| Tüketim      | L/100km   | kWh/100km | L/100km   |
|              | veya kWh/100km (elektrikli)       |
| Yıllık maliyet | ...     | ...       | ...       |
| Güç          | ...       | ...       | ...       |
| Vites        | ...       | ...       | ...       |
+--------------------------------------------------+
| Grafik (Chart.js çubuk grafik)                   |
|  Metrik: [ v Fiyat ]                             |
|   ####                                           |
|   ####   ######                                  |
|   ####   ######   ###                            |
|   A      B        C                              |
+--------------------------------------------------+
| [ Senaryo dene ]                                 |
+--------------------------------------------------+
```

### 3.6 scenario.html

```text
+--------------------------------------------------+
| <ortak menü>                                     |
+--------------------------------------------------+
| Scenario Lab                                     |
+--------------------------------------------------+
| Varsayımlar                                      |
|  Yıllık km:      [----o-----------] 15.000 km    |
|  Yakıt fiyatı:   [-------o--------] <yakıt fiyatı> TL/L |
|  Elektrik fiyatı: TBD                            |
|                                                  |
| Öncelik ağırlıkları                              |
|  Yakıt ekonomisi:   [------o---------] 20%       |
|  İç hacim:          [------o---------] 20%       |
|  Performans:        [------o---------] 20%       |
|  Bütçeye uygunluk:  [------o---------] 20%       |
|  Güvenlik:          [------o---------] 20%       |
|                                                  |
|  [ Sıfırla ]                                     |
+--------------------------------------------------+
| Sıralama: önce / sonra                           |
|  +-------------------+   +-------------------+   |
|  | ÖNCE              |   | SONRA             |   |
|  | 1. Araç A         |   | 1. Araç B   (^1)  |   |
|  | 2. Araç B         |   | 2. Araç A   (v1)  |   |
|  | 3. Araç C         |   | 3. Araç C   (=)   |   |
|  | 4. ...            |   | 4. ...            |   |
|  | 5. ...            |   | 5. ...            |   |
|  +-------------------+   +-------------------+   |
+--------------------------------------------------+
```

Ağırlıkların toplamının %100'e nasıl normalize edileceği TBD. Elektrik fiyatı sürgüsü de TBD.

## 4. Ortak menü

Menü tüm sayfalarda aynıdır. Sıra soldan sağa:

| Sıra | Öğe | Link | i18n anahtarı |
| --- | --- | --- | --- |
| 1 | Ana sayfa | `index.html` | `nav.home` |
| 2 | Anket | `survey.html` | `nav.survey` |
| 3 | Sonuçlar | `results.html` | `nav.results` |
| 4 | Katalog | `catalog.html` | `nav.catalog` |
| 5 | Karşılaştır | `compare.html` | `nav.compare` |
| 6 | Scenario Lab | `scenario.html` | `nav.scenario` |
| 7 | Dil seçici (TR/EN) | yok (aynı sayfada dil değiştirir) | `nav.language` |

Aktif sayfa menüde vurgulanır. Dil seçimi `tr.json` / `en.json` arasında geçiş yapar.

## 5. Açık sorular

- **i18n anahtar adlandırması:** Önek-sayfa düzeni (`survey.*`, `nav.*`) önerilir; alt düzey adlandırma biçimi (ör. `survey.budget.label`) Fatih ile netleştirilecek.
- **Sonuç sayfasına veri taşıma:** Tercihlerin veya önerilerin `results.html` sayfasına URL parametresi ile mi, `sessionStorage` ile mi taşınacağı TBD.
- **Hibrit araç gösterimi:** Hibrit araçların yakıt/tüketim alanlarında nasıl gösterileceği TBD (Belis ile).
- **Bütçe alanı çakışması:** Bütçe aralığı alanı ile 'Bütçeye uygunluk' önceliği kullanıcıya karışık görünebilir; Fatih ile netleşecek.
