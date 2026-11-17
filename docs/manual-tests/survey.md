# AutoMatch — Anket Sayfası (T11) Elle Test Kontrol Listesi

> **Sayfa:** `app/static/survey.html`  
> **İlgili Görev:** T11 — Çok adımlı anket sayfası (`survey.html` + `survey.js`)  
> **Modül:** M2 — Tercih Girişi  
> **Sorumlu:** @fatihoguzkaya  
> **Issue:** Refs #5

Bu doküman, anket sayfasının işlevsellik, doğrulama, tarayıcı durumu, API hata yönetimi ve erişilebilirlik gereksinimlerini doğrulamak için elle test adımlarını içerir.

---

## 1. Test Ortamını Başlatma

Backend ve `app/main.py` henüz oluşturulmadığından, statik sayfayı yerel Python HTTP sunucusu ile test edin:

```bash
# Proje kök dizininde veya app/static dizininde:
python -m http.server 8000 --directory app/static
```

Tarayıcıda açın:  
👉 **`http://127.0.0.1:8000/survey.html`**

---

## 2. Adım Adım Doğrulama Senaryoları

### Adım 1: Bütçe Belirleme (`budget_max_try`, `budget_min_try`)

| Test No | Senaryo | Yapılacak İşlem | Beklenen Sonuç | Durum |
|---|---|---|---|---|
| **1.1** | Boş Maksimum Bütçe | "Maksimum Bütçe" alanını boş bırakıp "İleri" butonuna tıklayın. | İlerleme engellenmeli; alan kırmızı olmalı ve altında `"Maksimum bütçe zorunludur."` hata mesajı çıkmalıdır. | [ ] |
| **1.2** | Negatif / 0 Bütçe | Maksimum bütçeye `-1000` veya `0` girip "İleri"ye tıklayın. | İlerleme engellenmeli; `"Maksimum bütçe 0'dan büyük bir tamsayı olmalıdır."` hatası gösterilmelidir. | [ ] |
| **1.3** | Minimum > Maksimum | Maksimum: `1.000.000`, Minimum: `1.500.000` girip "İleri"ye tıklayın. | `"Minimum bütçe maksimum bütçeden büyük olamaz."` hatası gösterilmelidir. | [ ] |
| **1.4** | Minimum Bütçe 0 | Maksimum: `1.500.000`, Minimum: `0` girip "İleri"ye tıklayın. | Hata vermemeli, Adım 2'ye geçmelidir (şema 0 tabanına izin verir). | [ ] |
| **1.5** | Geçerli Bütçe | Maksimum: `1.500.000`, Minimum: `800.000` (veya boş) girip "İleri"ye tıklayın. | Adım 2'ye geçmeli, ilerleme çubuğu %40 olmalıdır. | [ ] |

---

### Adım 2: Kullanım Profili (`usage_type`, `annual_km`)

| Test No | Senaryo | Yapılacak İşlem | Beklenen Sonuç | Durum |
|---|---|---|---|---|
| **2.1** | Kullanım Tipi Seçimi | "Şehir İçi", "Uzun Yol", "Karma" veya "Aile" kartlarına tıklayın. | Seçilen kart mavi vurgulanmalı (`selected`), diğerleri kalkmalıdır. | [ ] |
| **2.2** | Seçim Yapmadan Geçiş | Kullanım tipini seçmeden ve km girmeden "İleri"ye tıklayın. | Her iki alan da opsiyonel olduğundan hata vermeden Adım 3'e geçmelidir. | [ ] |
| **2.3** | Düşük Yıllık km (<1.000) | Yıllık km alanına `500` yazıp "İleri"ye tıklayın. | `"Yıllık km 1.000 ile 200.000 arasında olmalıdır."` hatası gösterilmeli, geçiş engellenmelidir. | [ ] |
| **2.4** | Yüksek Yıllık km (>200.000) | Yıllık km alanına `250000` yazıp "İleri"ye tıklayın. | Aynı şekilde aralık hatası gösterilmelidir. | [ ] |
| **2.5** | Geçerli km | `15000` girip "İleri"ye tıklayın. | Hata vermemeli, Adım 3'e geçmelidir (%60 ilerleme). | [ ] |

---

### Adım 3: Araç Tercihleri (`transmission`, `fuel_types`, `body_types`, `min_seats`)

| Test No | Senaryo | Yapılacak İşlem | Beklenen Sonuç | Durum |
|---|---|---|---|---|
| **3.1** | Vites Tipi | "Fark Etmez", "Manuel" ve "Otomatik" kartlarına tıklayın. | Tekil seçim yapılabilmeli, varsayılan "Fark Etmez" (`null`) olmalıdır. | [ ] |
| **3.2** | Yakıt Tipleri (Çoklu) | "Benzin" ve "Hibrit" kartlarını seçin. | Birden fazla kart aynı anda seçili (`selected`) olabilmelidir. | [ ] |
| **3.3** | Kasa Tipleri (Çoklu) | "SUV" seçin, ardından seçim yapmadan bırakmayı deneyin. | Hiçbiri seçilmezse boş liste (`[]`) = "Fark etmez" sayılmalıdır. | [ ] |
| **3.4** | Koltuk Sayısı Sınırları | Koltuk alanına `1` veya `10` girip "İleri"ye tıklayın. | `"Koltuk sayısı 2 ile 9 arasında olmalıdır."` hatası gösterilmelidir. | [ ] |
| **3.5** | Geçerli Koltuk | Koltuk alanına `5` (veya boş) bırakıp "İleri"ye tıklayın. | Adım 4'e geçmelidir (%80 ilerleme). | [ ] |

---

### Adım 4: Öncelikler (`priorities`)

| Test No | Senaryo | Yapılacak İşlem | Beklenen Sonuç | Durum |
|---|---|---|---|---|
| **4.1** | Varsayılan Değerler | Adım 4 açıldığında 5 kriterin (Yakıt, İç Hacim, Performans, Fiyat, Güvenlik) butonlarını inceleyin. | Tüm kriterlerde "Orta" butonu mavi aktif (`active`) olmalıdır. | [ ] |
| **4.2** | Değer Değiştirme | Yakıt Ekonomisi için "Yüksek", Performans için "Düşük" butonuna tıklayın. | İlgili buton aktifleşmeli, önceki buton pasife dönmelidir. | [ ] |
| **4.3** | İleri Geçiş | "İleri" butonuna tıklayın. | Adım 5 (Özet) ekranına geçmeli, ilerleme çubuğu %100 olmalıdır. | [ ] |

---

### Adım 5: Özet, Düzenleme ve Gönderim

| Test No | Senaryo | Yapılacak İşlem | Beklenen Sonuç | Durum |
|---|---|---|---|---|
| **5.1** | Özet Doğruluğu | Özet kartlarındaki değerleri inceleyin. | Önceki adımlarda girilen değerler biçimlendirilmiş olarak (örn: `1.500.000 TL`, `Şehir İçi`, `SUV`, `Yüksek (3)`) görünmelidir. | [ ] |
| **5.2** | "Düzenle" ile Adıma Dönüş | "Bütçe" başlığındaki "Düzenle" butonuna tıklayın. | Sayfa Adım 1'e dönmeli, önceki girilen değerler formda korunmalıdır. | [ ] |
| **5.3** | Geri / İleri Butonları | "Geri" butonuna basarak adım adım geri gidin, "İleri" ile özet ekranına dönün. | Veri kaybı olmadan adımlar arasında gezilebilmelidir. | [ ] |

---

## 3. Durum Yönetimi & API Hata Senaryoları

### Senaryo A: Sayfa Yenileme (Draft Persistence)

1. Formda Adım 1 ve Adım 2'yi doldurun (Bütçe: `1.800.000`, Kullanım: `Aile`, km: `20000`).
2. Tarayıcıyı yenileyin (`F5` veya `Ctrl+R`).
3. **Beklenen Sonuç:**
   - Sayfa açıldığında form sıfırlanmamalı; `sessionStorage`'daki taslaktan tüm inputlar ve seçili kartlar geri yüklenmelidir.

---

### Senaryo B: 404 / Ağ Hatası Durumu (Dayanıklılık Testi)

1. Adım 5'te "Önerileri Gör" butonuna tıklayın (T12 henüz yazılmadığı için backend 404 veya bağlantı hatası verecektir).
2. **Beklenen Sonuç:**
   - Sayfa ÇÖKMEMELİDİR.
   - Konsolda `AutoMatch: /api/preferences/form unavailable...` uyarısı yazmalıdır.
   - `sessionStorage` kontrol edildiğinde `automatch.preference` anahtarının `Preference` şemasına tam uyumlu JSON ile kaydedildiği görülmelidir:
     ```js
     JSON.parse(sessionStorage.getItem("automatch.preference"))
     ```
   - Ekranda sarı/uyarı kutusu çıkmalı: `"API servisine ulaşılamadı. Tercihleriniz yerel olarak tarayıcınıza kaydedildi."` mesajı ve **"Sonuçlara Devam Et"** butonu görünmelidir.
   - Sayfa otomatik yönlenmemeli, kullanıcı "Sonuçlara Devam Et" butonuna tıklayınca `results.html`'e gitmelidir.

---

### Senaryo C: 422 Unprocessable Entity (Validasyon Yanıtı)

1. API'nin 422 döndürdüğü simüle edildiğinde (`{"detail": [{"loc": ["body", "budget_max_try"], "msg": "Input should be greater than 0"}]}`).
2. **Beklenen Sonuç:**
   - Kırmızı alert kutusu içinde hata ayrıntıları liste (`detail`) formatında kullanıcıya gösterilmelidir.

---

## 4. Mobil Görünüm ve Erişilebilirlik

| Test No | Kriter | Test Adımı | Beklenen Sonuç | Durum |
|---|---|---|---|---|
| **4.1** | Responsive Düzen | Geliştirici araçlarında (F12) ekranı 375px genişliğe (iPhone SE) getirin. | Yatay kaydırma çubuğu çıkmamalı, butonlar ve kartlar tek sütunda alt alta düzgün yerleşmelidir. | [ ] |
| **4.2** | Dokunma Alanı (Touch Target) | Mobil görünümde buton ve kart boyutlarını kontrol edin. | Tüm buton ve kartlar en az 44px yüksekliğe sahip olmalıdır. | [ ] |
| **4.3** | Klavye Erişilebilirliği | Yalnızca `Tab`, `Shift+Tab`, `Space` ve `Enter` tuşlarıyla formu doldurun. | Tüm form alanlarına odaklanılabilmeli, kartlar ve butonlar klavyeyle seçilebilmelidir. | [ ] |
| **4.4** | Ekran Okuyucu Desteği | Hata alanlarını inceleyin. | Hata mesajları `aria-live="polite"` konteynerlerinde yer almalı, her `<input>` kendine ait `<label>` ile eşleşmelidir. | [ ] |
