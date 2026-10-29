# Utvecklingslogg

Hur projektet kom till, i den ordning besluten togs. Siffrorna och underlaget finns i `experiments/results/`, koden i historiken.

## 28 oktober: första versionen

- Pipeline: SMHI:s öppna komposit (GeoTIFF, 5 min, 2 km), Lucas-Kanade och semi-Lagrangesk extrapolering med pysteps, PNG-rutor och manifest, GitHub Pages via grenen `data` som skrivs om varje cykel.
- Systemd-timer på Pi:n och en utvecklingscontainer för Claude Code.

## 28 oktober: jämförelse mot en KNEP-proxy

- KNEP är inte fri öppen data, så en proxy byggdes: kvartsmedel, Lucas-Kanade på tre kvartar, 15-minuterssteg, 10 min fördröjning.
- Fyra öppna fall ur pysteps-data. Kedjan med fördelningsmatchning och en platskarta (tillväxt och avtagande lärd online) vann vid 1 mm/h på alla horisonter och valdes i korsvalidering över länder. S-PROG och STEPS föll på formkraven (utsmetade fält).
- PM: "Nowcast som slår KNEP".

## 29 oktober: extremer

- Sex fall (KNMI 2010 och RMI 2021 tillkom). Mått för extremer: SEDI, ETS och bias vid 10 och 20 mm/h, toppkvoter.
- Gradient boosting per tröskel på lagrangeska särdrag, med ett fall utanför i taget och nästlad isoton omkalibrering. Sannolikheterna har skicklighet; att skala om fältets toppar efter dem förlorade ETS, SEDI och FSS och togs inte in.

## 29 oktober: radarbortfall och komposit

- Lager: SMHI, enskilda ODIM-volymer från EUMETNET:s öppna data, OPERA-kompositen, sist förra analysen flyttad med rörelsen.
- Simulerat bortfall: utfyllnaden räddar analysen och ETS 1, men inte kraftig nederbörd. En åldersberoende utjämning prövades och togs inte in.

## 29 oktober: händelseflikar

- Hans 2023, Anna 2026 och Gävle 2021 definierade; byggs ur SMHI:s arkiv på Pi:n. Testfallen visas tills dess.

## 29 oktober: volym, aspekter och jämförelsevyer

- Volymkorrektion mot SMHI:s timstationer: nivå per strålhöjd och månad (som BALTEX-justeringen), restkarta, svansterm över 5 mm/h, volymslutning sist, veckofaktor utan skyfallstimmar. Prövad på syntetiska data.
- Aspektmått för tajming, volym, intensitet, spridning och avtagande. Alla extrapoleringar ligger efter; högre fart hjälpte inte poängen, glesare bilder till rörelsen gjorde det. Matchning mot den flyttade analysen gav rätt avtagande vid randen. Båda valdes i alla korsvalideringsvarv och togs in; extremmodellen tränades om på den nya kedjan.
- Sidan: 5 min, 15 min och 1 h, och punktserie mot SNOW-medianen och MET Norges nowcast.

## 29 oktober: versioner och driftsättning

- Tränade modeller versioneras i GitHub Releases och låses i `models/models.json`. Driften skriver aldrig över en låst modell; den räknar kandidater som släpps för hand.
- Testerna körs i GitHub Actions på varje pull request.
