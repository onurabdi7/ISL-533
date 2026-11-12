"""6 · Kullanım Kılavuzu — panelin nasıl kullanılacağı, görsel ve metriklerin nasıl çalıştığı."""

import streamlit as st

from core.style import page_header

page_header("Kullanım Kılavuzu")

st.markdown("""
Bu panel, bir B2B kitap dağıtıcısının 2020 yılı satış hareketlerini satış, pazarlama ve tedarik zinciri
ekiplerinin karar verebileceği bir biçime getirir. Aşağıda önce paneli nasıl kullanacağınızı, sonra her
sayfadaki görsel ve ölçülerin neyi, neden ve nasıl gösterdiğini bulacaksınız.

---

### Panelde gezinme

**Sayfalar.** Sol menüde dört rapor sayfası vardır: *Satış*, *Müşteri & Pazarlama*, *Ürün & Tedarik* ve
*Veri Kalitesi*. Her sayfa bir departmanın sorusuna odaklanır; ortak bir özet sayfası yerine her sayfa
kendi başına okunabilir.

**Filtre şeridi.** Her sayfanın üstünde o sayfaya ait filtreler bulunur. Bir sayfada seçtiğiniz kategori
başka sayfayı etkilemez; böylece örneğin Satış'ta Sınav & Ders'e bakarken Müşteri sayfasında tüm
müşterileri görmeye devam edebilirsiniz. Seçimler sayfa değiştirdiğinizde korunur. Boş bırakılan bir
filtre "tümü" demektir. **Sıfırla** o sayfanın bütün filtrelerini başlangıç durumuna döndürür.
Tarih için iki ayrı alan vardır: başlangıcı bitişten sonraya alırsanız bitiş otomatik olarak aynı güne
çekilir, böylece aralık hiçbir zaman ters dönmez.

**Tutar birimi: Reel / Nominal.** Kenar çubuğundaki bu seçim tüm sayfalardaki tutarları birlikte değiştirir.
2020'de yıllık enflasyon %14,6 olduğu için Ocak'taki 100 ₺ ile Aralık'taki 100 ₺ aynı alım gücünü
temsil etmez. Nominal tutarlar faturadaki rakamlardır; bu yüzden yıl içinde fiyatlar arttıkça satışlar
büyüyormuş gibi görünür. Reel tutarlar her ayın satışını TÜİK Tüketici Fiyat Endeksi ile Aralık 2020
fiyatlarına taşır (*reel tutar = nominal tutar × Aralık TÜFE / işlem ayı TÜFE*). Büyümenin gerçek mi yoksa
fiyat artışından mı geldiğini anlamak için reel, faturayla mutabakat için nominal kullanılır.

**Grafik / Tablo sekmeleri.** Sayısal her görselin yanında aynı verinin tablosu bulunur. Tablolar
sıralanabilir, aranabilir ve sağ üstteki simgeyle CSV olarak indirilebilir. Zaman serisi tablolarında
önceki döneme göre artış **yeşil**, düşüş **kırmızı** gösterilir. İndirim tablolarında renk terstir:
indirim artışı marj kaybı anlamına geldiği için kırmızıdır.

**Ayrıntı için üzerine gelin.** Grafiklerde bir çizginin, hücrenin ya da ilin üzerine geldiğinizde tam değer
görünür.

---

### Temel ölçüler

| Ölçü | Nasıl hesaplanır | Neden böyle |
|---|---|---|
| **Net ciro** | Adet × net birim fiyat | Faturada tahsil edilen gerçek tutar. |
| **Liste tutarı** | Adet × liste fiyatı | İndirim öncesi değer; indirim hesabının tabanı. |
| **Ağırlıklı indirim** | (Liste tutarı − net ciro) / liste tutarı | Satır indirimlerinin basit ortalaması, 1 adetlik satırla 500 adetlik satırı eşit sayardı. Ağırlıklı oran büyük satırlara hak ettiği ağırlığı verir. |
| **Gün başı ciro** | Ciro / ilgili gün sayısı | Ayların ve dönemlerin gün sayısı farklıdır. 56 günlük kapanma dönemini 162 günlük normalleşmeyle toplam üzerinden kıyaslamak yanıltır. |
| **Ortalama sepet** | Net ciro / fatura sayısı | Sipariş büyüklüğünün özeti; sevkiyat planlamasına girdi. |

---

### Satış sayfası

**KPI kartı.** Seçili filtreye göre net ciro, adet, fatura, lider kategori ve lider şehir. Net cironun
altındaki ok, aralığın tamamen kapsadığı ilk ve son ayın karşılaştırmasıdır. Yarım aylar karşılaştırmayı
bozacağı için yalnızca tam aylar kullanılır; aralıkta iki tam ay yoksa ok gösterilmez.

**Ciro trendi.** Seçtiğiniz aralık 60 günden kısaysa grafik günlük, uzunsa haftalık çizilir. Kısa aralıkta
günlük ayrıntı bilgi verir; uzun aralıkta ise günlük dalgalanma (Pazar günleri sıfır satış gibi) asıl eğilimi
gizler. Haftalar Pazartesi başlar. Aralığın başında ya da sonunda kalan yarım haftalar çizilmez, çünkü
eksik gün sayısı sahte bir düşüş gibi görünürdü.

**Kategori mevsimselliği.** Her satır bir kategoridir; hücre o kategorinin o aydaki günlük ortalama
cirosunun, kategorinin yıllık günlük ortalamasına oranıdır (100 = sıradan bir gün). Mavi hücreler
ortalamanın üstünü, kırmızılar altını gösterir. Her kategori kendi ortalamasına göre ölçüldüğü için
küçük ve büyük kategoriler aynı tabloda karşılaştırılabilir. Tek bir ana kategori seçerseniz tablo o
kategorinin alt kategorilerine iner. Altındaki özet cümle yalnızca cironun en az %2'sini yapan grupları
dikkate alır, çünkü çok küçük gruplarda birkaç büyük sipariş endeksi abartılı biçimde oynatır.
*Kullanım:* tepe aylardan önce stok ve tedarik hazırlığı (ör. okul dönemi öncesi Sınav & Ders).

**Haftanın günü × ay.** Hücre, o ayın o gününe düşen ortalama günlük cirodur. Toplam yerine ortalama
kullanılır, çünkü bir ayda dört ya da beş Pazartesi olabilir. *Kullanım:* depo ve sevkiyat vardiya planı.

**İllere göre ciro.** Harita renkleri logaritmik ölçektedir. İstanbul tek başına cironun yaklaşık yarısını
yaptığından doğrusal ölçekte diğer bütün iller aynı açık renkte görünürdü; logaritmik ölçek 10 bin ₺ ile
100 bin ₺ arasındaki farkı da görünür kılar. Gri iller seçili dönemde satış olmayan illerdir. İli
bilinmeyen satırlar haritada yer almaz, altta ayrıca belirtilir.

**COVID dönemleri.** Yıl üç döneme ayrılır: Öncesi (–10.03), Kapanma (11.03–31.05), Normalleşme (01.06–).
Dönemler satış yapılan gün başına ciroyla karşılaştırılır. Alttaki tablo her ana kategorinin bu dönemlerde
ne kadar değiştiğini, en çok etkilenenden başlayarak gösterir.

---

### Müşteri & Pazarlama sayfası

**RFM nedir?** Her müşteri üç ölçüyle tanımlanır: **R**ecency (son alımdan bu yana geçen gün),
**F**requency (fatura sayısı), **M**onetary (ciro). Müşteriler her ölçüde sıralanıp beş eşit gruba
bölünür ve 1–5 arası skor alır; 5 her zaman "en iyi"dir (en yakın, en sık, en yüksek). Skorlar seçili
filtreye göre yeniden hesaplanır ve referans gün, seçili bitiş tarihinin ertesi günüdür.

**Neden müşteri etiketi yok?** "Kaybedilen", "riskli", "büyüyen" gibi etiketler geleceğe dair bir iddia
taşır. Veri tek yılı kapsadığından, Aralık'ta sessiz kalan bir müşterinin kaybedildiğini mi yoksa okul
dönemine göre alım yapan dönemsel bir müşteri mi olduğunu ayırt edemeyiz. Bu yüzden panel ölçer ve
gösterir, nitelemeyi kullanıcıya bırakır. Filtredeki *değer grubu* (F ve M skor toplamına göre Yüksek /
Orta / Düşük) ve *alım düzeni* (alımlar arası sürenin düzenliliğine göre) yalnızca 2020'deki davranışı
tanımlar.

**Pareto eğrisi.** Müşteriler cirodan büyüğe sıralanır ve eğri "en iyi %x müşteri cironun %y'sini
yapıyor" sorusunu yanıtlar. Kesikli çizgi herkesin eşit ciro yaptığı durumdur; eğri bu çizgiden ne
kadar uzaksa ciro o kadar az müşteride yoğunlaşmıştır. Yoğunlaşma yüksekse birkaç büyük müşteriyi
kaybetmek ciroyu orantısız etkiler.

**RFM ısı haritası.** Satırlar yakınlık, sütunlar sıklık skorudur. Hücredeki sayı müşteri adedi, renk o
hücrenin ciro payıdır. Sağ üst köşe (yakın ve sık alan) genellikle ciroyu taşır; alt satırlar uzun
süredir alım yapmamış müşterilerdir. Skor sınırları açılır kutuda yer alır.

**Birlikte alınan kategoriler (pazar sepeti analizi).** Aynı faturada hangi kategorilerin birlikte
geçtiğini üç ölçüyle değerlendirir:
- **Destek:** iki kategoriyi birlikte içeren faturaların tüm faturalara oranı. Çiftin ne kadar yaygın
  olduğunu söyler; kaydırıcıyla düşük destekli, tesadüfi olabilecek çiftler elenir.
- **Güven (A→B):** A'yı alan faturaların yüzde kaçında B'nin de bulunduğu. Yönlüdür: "A alana B önermek"
  için kullanılır.
- **Lift:** çiftin gerçekte birlikte görülme sıklığının, iki kategori birbirinden bağımsız olsaydı
  beklenen sıklığa oranı. **1** tesadüf düzeyidir; **1'in üstü** (mavi) beklenenden sık birlikte
  alındığını, **1'in altı** (kırmızı) beklenenden seyrek, yani genellikle farklı müşteri kitlelerine
  gittiğini gösterir.

B2B siparişleri büyük olduğu için bir faturada ortalama dört ana kategori bulunur; bu yüzden çiftlerin
çoğu 1'in üstünde çıkar. Asıl anlamlı olan, diğerlerine göre belirgin biçimde yüksek değerlerdir.
*Kullanım:* çapraz satış önerileri, birlikte kampanya ve katalog/raf yerleşimi. Alt kategori seviyesi
(en sık 25) daha somut öneriler verir.

---

### Ürün & Tedarik sayfası

**ABC analizi.** Ürünler cirodan büyüğe sıralanır. Cironun ilk %80'ini yapan ürünler **A**, sonraki
%15'i **B**, kalan %5'i **C** sınıfıdır. Eğrinin yatay ekseni logaritmiktir, çünkü A sınıfı ürünler
toplamın çok küçük bir kısmıdır ve doğrusal eksende sola yapışık görünürdü. *Kullanım:* A ürünlerinde
stoksuz kalmamak öncelik, C ürünlerinde (uzun kuyruk) stok tutma maliyeti sorgulanır. En çok ciro yapan
50 ürün açılır kutudadır.

**Haftalık talep tahmini.** Panel tek bir modele güvenmek yerine dört adayı yarıştırır: naif (son
haftayı tekrarla), 4 haftalık hareketli ortalama, basit üstel düzeltme ve sönümlü trendli üstel
düzeltme. Her aday, son 8 hafta hiç görmemiş gibi bu haftaları tahmin eder (geri test). Gerçekle
arasındaki ortalama yüzde hatası (**MAPE**) en düşük olan model tüm veriyle yeniden kurulup ileriyi
tahmin eder. Turuncu noktalı çizgi geri testte seçilen modelin ne tahmin ettiğini gösterir; böylece
tahmine ne kadar güvenebileceğinizi görürsünüz. Gölgeli alan yaklaşık %80 tahmin aralığıdır ve ufuk
uzadıkça genişler. Geri test hatası %30'u aşarsa panel uyarı verir.
Bu veride genellikle naif yöntem kazanır: tek yıllık ve dalgalı bir seride karmaşık modellerin
öğrenebileceği kalıcı bir yapı yoktur. Bu bir eksiklik değil, verinin söylediği şeydir; tahmin yakın
vadeli seviye göstergesi olarak okunmalıdır.

**Kitap fiyat endeksi ve TÜFE.** Her ay, hem ilk ayda hem o ayda satılmış aynı ürünlerin liste
fiyatlarının oranları alınır ve geometrik ortalaması hesaplanır. Aynı ürünler karşılaştırıldığı için
ürün karmasındaki değişim (o ay daha pahalı kitapların satılması) endeksi bozmaz. Endeks nominal liste
fiyatıyla hesaplanır, çünkü TÜFE de nominal bir endekstir. Kitap endeksi TÜFE'nin altında kalıyorsa
kitaplar genel fiyatlara göre reel olarak ucuzlamış demektir; bu, fiyat artışlarının enflasyonun gerisinde
kaldığını ve marj baskısı olabileceğini gösterir.

---

### Veri Kalitesi sayfası

**Usul: bayrakla, raporla, analizden dışla.** Ham veride yalnızca birebir tekrar eden satırlar silinmiştir.
Sorunlu diğer satırlar (boş ya da sıfır miktar, sıfır/negatif fiyat, liste fiyatından yüksek net fiyat,
yer tutucu fiyat) silinmez; işaretlenir, analiz dışında tutulur ve *Geçersiz satırlar* sekmesinde
listelenir. Böylece hiçbir veri sessizce kaybolmaz. Boş şehir ve kategori değerleri başka satırlardan
doldurulamadığı için "Bilinmiyor" / "Kategorisiz" olarak etiketlenmiştir.

**Uç satış & indirim.** Uç satış, reel satır tutarı logaritmik ölçekte Tukey üst sınırını (k=3) aşan
satırdır. Logaritma kullanılır çünkü satır tutarları sağa çarpıktır; doğrusal ölçekte sınır anlamsız
derecede düşük çıkardı. Uç satırlar silinmez: B2B'de toplu alımlar gerçektir ve cironun önemli bir
kısmını oluşturur. Belge serisi grafiği, uç satışların çoğunun toplu alım serilerinden (DPE/DPF)
geldiğini gösterir. İndirim bantları da aynı yöntemle belirlenir; çok yüksek ya da çok düşük indirimli
satırlar denetim için işaretlenir. *Dönemsel indirim* grafiği aylık ağırlıklı indirim oranının ve
kategorilere göre kırılımının zaman içindeki seyrini gösterir.

---

### Sınırlar

- Veri yalnızca 2020'yi kapsar; mevsimsellik tek yıldan gözlenir, yıllar arası doğrulanamaz.
- 2020 COVID nedeniyle olağandışı bir yıldır; gözlenen kalıplar normal yıllara aynen taşınmamalıdır.
- Reel tutarlar genel TÜFE ile hesaplanır; kitap sektörüne özgü bir deflatör değildir.
- Yıl başında alım yapan müşterilerin bir kısmı 2020 öncesinden de müşteri olabilir; veri bunu göstermez.
""")
