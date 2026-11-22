# Veri Kaynakları (`data/vehicles.csv`)

> **Modül:** M1 — Araç Verisi ve Katalog · **Sorumlu:** @Belisozcelik · **Görev:** T03
> **Kontrol tarihi (id 2–11):** 2026-11-19
> Kolon tanımları ve birimler: [`docs/data-dictionary.md`](../docs/data-dictionary.md)

## Genel kurallar

- Teknik değerler ve fiyatlar yalnızca **üreticilerin / distribütörlerin resmî Türkiye sayfalarından** alındı. Haber siteleri yalnızca çapraz kontrol için kullanıldı.
- **Fiyatlar örnektir.** `price_try` = tavsiye edilen anahtar teslim **liste** fiyatı (kampanyalı fiyat değil). Fiyatlar her ay değişir; bayi fiyatı farklı olabilir.
- Tüketim ve menzil değerleri **WLTP birleşik (karma)** değerleridir. Kaynak bir aralık verdiyse (ör. 5,2–5,4) **üst değer** yazıldı; böylece maliyet hesabı iyimser olmaz.
- `power_hp`: hibritlerde **birleşik sistem gücü**.
- Kaynakta açıkça yazmayan opsiyonel değerler (`trunk_l`, `euro_ncap_stars`) **boş bırakıldı**, tahmin edilmedi (NFR-04).
- `euro_ncap_stars` yalnızca **geçerliliği süren** Euro NCAP derecelendirmesi için dolduruldu. Süresi dolmuş veya bu kontrolde doğrulanamamış dereceler boş bırakıldı.

## Özet tablo

| id | Araç | Gövde / Yakıt / Vites | Fiyat (TL) | Euro NCAP |
| --- | --- | --- | --- | --- |
| 2 | Hyundai i20 1.0 T-GDI 90 PS 7DCT Jump | hatchback / petrol / automatic | 1.759.000 | 4 (2021) |
| 3 | Opel Corsa 1.2 100 HP MT6 Edition | hatchback / petrol / manual | 1.535.000 | boş |
| 4 | Opel Astra 1.5 130 HP Dizel AT8 Edition | hatchback / diesel / automatic | 2.350.000 | boş |
| 5 | Renault Megane Sedan Touch 1.3 TCe EDC 140 | sedan / petrol / automatic | 2.199.000 | boş |
| 6 | Renault 5 E-Tech Techno EV52 150 hp | hatchback / electric / automatic | 2.101.000 | boş |
| 7 | Peugeot 2008 Allure 1.2 Hybrid 145 eDCS6 | suv / hybrid / automatic | 2.353.000 | boş (2019 derecesi sona erdi) |
| 8 | Peugeot 3008 Allure 1.2 Hybrid 145 eDCS6 | suv / hybrid / automatic | 2.967.000 | boş |
| 9 | Opel Mokka 1.2 136 HP MT6 Edition | suv / petrol / manual | 1.990.000 | boş |
| 10 | Togg T10X V1 RWD Uzun Menzil | suv / electric / automatic | 2.219.668 | 5 (2025) |
| 11 | BYD Seal 390 kW AWD Excellence | sedan / electric / automatic | 4.077.000 | 5 (2023) |
| 31–35 | Toyota Corolla ×2, Corolla Cross, Renault Clio, Dacia Sandero | — | — | T57 (PR #70) |

---

## Araç bazında kaynaklar

### 2 · Hyundai i20 1.0 T-GDI 90 PS 7DCT Jump

- **Teknik:** Resmî yakıt ekonomisi etiketi (PDF): <https://www.hyundai.com/content/dam/hyundai/tr/tr/images/yakit-emisyon/i20-1-0-T-GDI-7DCT-90-PS.pdf> → WLTP birleşik **6,3 l/100 km**, 142 g/km CO2, 998 cc, 7 ileri DCT.
- **Bagaj:** <https://www.hyundai.com/tr/tr/modeller/i20/tasarim.html> → **352 l**.
- **Güç:** Resmî i20 dijital broşürü → 90 PS (66 kW).
- **Fiyat:** <https://www.hyundai.com/tr/tr/satis/fiyat-listesi.html> (Kasım 2026 listesi). Sayfa fiyat tablosunu dinamik yüklüyor; 1.759.000 TL (Jump DCT, kampanyasız) Kasım 2026 basın listeleriyle çapraz kontrol edildi.
- **Euro NCAP:** 4 yıldız (2021) — <https://www.euroncap.com/en/results/hyundai/i20/46622>

### 3 · Opel Corsa 1.2 100 HP MT6 Edition

- **Teknik:** Opel Türkiye WLTP tablosu: <https://www.opel.com.tr/opel-hakkinda/cevre-yakit-ekonomisi-emisyon-bilgileri.html> → birleşik **5,2–5,4 l/100 km** (üst değer 5,4 yazıldı), 118–126 g/km.
- **Fiyat:** <https://fiyatlisteleri.opel.com.tr/arac/corsa> → MY26 tavsiye edilen anahtar teslim **1.535.000 TL** (kampanyalı 1.460.000 TL, kullanılmadı).
- **Boş alanlar:** `trunk_l` resmî sayfada benzinli sürüm için bulunamadı. Euro NCAP 2019 derecesi (4 yıldız) geçerlilik durumu doğrulanamadığı için boş bırakıldı.

### 4 · Opel Astra 1.5 130 HP Dizel AT8 Edition

- **Teknik:** Aynı Opel WLTP tablosu → birleşik **4,9 l/100 km**, 130 g/km.
- **Fiyat:** <https://fiyatlisteleri.opel.com.tr/tum-araclar> (liste dosyası `Opel_Tum_Modeller_Fiyat_Listesi19.11.2026`) → **2.350.000 TL**.
- **Boş alanlar:** `trunk_l`, `euro_ncap_stars` resmî kaynakta doğrulanamadı.

### 5 · Renault Megane Sedan Touch 1.3 TCe EDC 140

- **Teknik:** <https://www.renault.com.tr/binek-araclar/megane-sedan/teknik-bilgiler.html> → 140 bg, 5 koltuk, bagaj **503 dm³**.
- **Tüketim + fiyat:** <https://www.renault.com.tr/binek-araclar/megane-sedan/konfigurator-yeni.html> → WLTP birleşik **6,2 l/100 km**, başlangıç fiyatı **2.199.000 TL** (Touch).
- **Not:** Model yılı sayfada yazmıyor; güncel satış listesi olduğu için 2026 yazıldı.

### 6 · Renault 5 E-Tech Techno EV52 150 hp

- **Teknik:** <https://www.renault.com.tr/elektrikli-araclar/r5-e-tech-elektrikli/teknik-bilgiler.html> → 110 kW (150 bg), 52 kWh, bagaj **326 dm³**, 5 koltuk.
- **Tüketim / menzil + fiyat:** <https://www.renault.com.tr/elektrikli-araclar/r5-e-tech-elektrikli/konfigurator-yeni.html> → **15,0 kWh/100 km**, WLTP menzil **410 km**, fiyat **2.101.000 TL**.
- **Not:** Konfigüratördeki "aracın fiyatı" (2.101.000 TL) esas alındı. Model yılı sayfada yazmıyor (2026).

### 7 · Peugeot 2008 Allure 1.2 Hybrid 145 eDCS6

- **Teknik:** <https://www.peugeot.com.tr/peugeot-modelleri/2008.html> → birleşik **5,0–5,1 l/100 km** (5,1 yazıldı), 145 hp birleşik güç. 48V hafif hibrit → sözlüğe göre `hybrid`.
- **Fiyat:** <https://kampanya.peugeot.com.tr/fiyat-listesi/> → 2026 MY **2.353.000 TL**.
- **Boş alanlar:** Sitede bagaj "tavana kadar 545 l" olarak verilmiş; bu VDA standart ölçüsü olmadığı için yazılmadı. Euro NCAP 2019 derecesi (4 yıldız) 1 Ocak 2026'da sona erdi: <https://www.euroncap.com/en/results/peugeot/2008/39840>

### 8 · Peugeot 3008 Allure 1.2 Hybrid 145 eDCS6

- **Teknik:** <https://www.peugeot.com.tr/peugeot-modelleri/3008.html> → birleşik **5,6 l/100 km**, 145 hp birleşik güç (48V hafif hibrit).
- **Fiyat:** <https://kampanya.peugeot.com.tr/fiyat-listesi/> → 2026 MY **2.967.000 TL**.
- **Boş alanlar:** `trunk_l`, `euro_ncap_stars` doğrulanamadı.

### 9 · Opel Mokka 1.2 136 HP MT6 Edition

- **Teknik:** Opel WLTP tablosu → birleşik **5,6 l/100 km**, 127 g/km, manuel.
- **Fiyat:** <https://fiyatlisteleri.opel.com.tr/tum-araclar> → MY26 **1.990.000 TL** (kampanyalı 1.770.000 TL, kullanılmadı).
- **Boş alanlar:** `trunk_l`, `euro_ncap_stars` doğrulanamadı.

### 10 · Togg T10X V1 RWD Uzun Menzil

- **Teknik:** <https://configurator.togg.com.tr/t10x> (V1 RWD Uzun Menzil özeti) → WLTP menzil **523 km**, enerji tüketimi **19,7 kWh/100 km**, 160 kW (**218 PS**).
- **Fiyat:** <https://www.togg.com.tr/en/price-list> → **2.219.668 TL** (opsiyonsuz anahtar teslim). Liste "15/06/2026'dan itibaren geçerli" olarak işaretli. Konfigüratördeki 2.309.668 TL, 19" jant (40.000 TL) ve Tekno-Konfor paketi (50.000 TL) dahil fiyattır.
- **Koltuk:** Resmî sayfa "5 kişilik aile" ifadesini kullanıyor.
- **Euro NCAP:** 5 yıldız (2025). Test edilen sürüm tam olarak bu sürüm (Long Range RWD): <https://www.euroncap.com/en/results/togg/t10x/56128>
- **Boş alan:** `trunk_l` (Togg kaynakları sürüme göre farklı değerler veriyor).

### 11 · BYD Seal 390 kW AWD Excellence

- **Teknik:** Resmî teknik broşür (PDF): <https://www.bydauto.com.tr/storage/pdf/teknik/byd-seal-teknik-ozellikler-ve-donanim-tablosu-23-01-26.pdf> → **18,2 kWh/100 km**, WLTP karma menzil **520 km**, 390 kW (**530 PS**), bagaj **400 l** (+53 l ön bagaj, CSV'ye yazılmadı).
- **Fiyat:** <https://www.bydauto.com.tr/fiyat-listesi> → "19 Kasım 2026 tarihli liste", 2025 model yılı, tavsiye edilen liste **4.077.000 TL** (kampanyalı 3.772.000 TL, kullanılmadı). Bu yüzden `year` = 2025.
- **Euro NCAP:** 5 yıldız (2023) — <https://www.euroncap.com/en/results/byd/seal/50012> (test edilen sürüm Design 4x2; derece model ailesi için yayımlandı).

---

## Mevcut satırlar (T57 — PR #70 ile eklendi)

| id | Araç | Not |
| --- | --- | --- |
| 31–33 | Toyota Corolla HB, Corolla Sedan, Corolla Cross | 2026-11-18 tarihinde PR #70 ile eklendi |
| 34 | Renault Clio TCe 115 EDC | 2026-11-18 tarihinde PR #70 ile eklendi |
| 35 | Dacia Sandero TCe 100 Expression | 2026-11-18 tarihinde PR #70 ile eklendi |

*(Not: T02 şablonundaki uydurma `id=1 ExampleBrand` satırı T03 kapsamında gerçek araç verileri eklendiği için kaldırıldı.)*

## Değerlendirilip eklenmeyen araçlar

| Araç | Neden |
| --- | --- |
| Fiat Egea Sedan 1.6 Multijet | `fiat.com.tr` dizel WLTP tüketimini yayımlamıyor. |
| VW Polo / Golf / T-Roc | `binekarac.vw.com.tr` fiyat tablosu dinamik yükleniyor. |
| BYD Atto 3 | 19 Kasım 2026 tarihli BYD fiyat listesinde yer almıyor. |
| Hyundai Tucson Hibrit | Hyundai Kasım 2026 fiyat listesinde fiyatı yok. |
