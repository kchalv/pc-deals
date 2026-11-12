# PC deals: έτοιμα gaming PC & περιφερειακά από ελληνικά καταστήματα

Σελίδα: **http://127.0.0.1:8765/** (κουμπί «↻ Ανανέωση τιμών»). Σάρωση **κάθε ώρα** και email με τις νέες πραγματικές ευκαιρίες (αν υπάρχουν).

## Online (GitHub Actions + Pages)

- Σελίδα: **https://kchalv.github.io/pc-deals/**, repo `kchalv/pc-deals` (δημόσιο).
- Το `.github/workflows/scan.yml` τρέχει τη σάρωση **κάθε ώρα στο GitHub** (:17 UTC), στέλνει τα email και ανεβάζει τη σελίδα. Δεν χρειάζεται ανοιχτός υπολογιστής.
- Ρυθμίσεις email: secret `NOTIFY_JSON` (ίδιο με το `notify.json`, που δεν ανεβαίνει). Το ιστορικό τιμών μένει στο branch `data`.
- Χειροκίνητα: Actions → scan → Run workflow (επιλογές: email, δοκιμαστικό email).
- Κάθε push στο `main` που αλλάζει `pc_deals.py` / `watchlist.json` / το workflow κάνει αμέσως σάρωση και deploy (χωρίς email).
- Τοπικά: το task «PC Deals Hourly» είναι **απενεργοποιημένο**, για να μη στέλνονται διπλά email. Το κουμπί ανανέωσης στο 127.0.0.1 σαρώνει χωρίς email.
- **Plaisio, U-Case, Κωτσόβολος** απαντούν 403 στους servers του GitHub. Τα σαρώνει ο υπολογιστής σου (task **PC Deals Relay**, κάθε ώρα στο :05, `pythonw pc_deals.py --relay`) και ανεβάζει μόνο τα προϊόντα στο branch `relay`. Το GitHub τα ενσωματώνει αν είναι νεότερα από 5 ώρες (`watchlist.json` → `relay`). Email στέλνει **μόνο** το GitHub. Κάθε push στο `relay` ξεκινά αμέσως και τη σάρωση στο GitHub (workflow `relay-trigger`, από το `.github/relay-trigger.yml`), γιατί το GitHub παραλείπει συχνά τα scheduled runs· το cron μένει ως εφεδρεία όταν ο υπολογιστής είναι κλειστός. Αν ο υπολογιστής είναι κλειστός, η σελίδα απλώς δεν έχει αυτά τα 3 καταστήματα.
- Αν αλλάξεις τον κωδικό του email: ενημέρωσε το `notify.json` και ξαναβάλε το secret (`gh secret set NOTIFY_JSON`).

## Τι κάνει

- **Έτοιμα PC** από ελληνικά καταστήματα, μόνο αν ισχύουν **και τα τρία**:
  - CPU: **Ryzen 7 9800X3D**, **Ryzen 7 7800X3D**, **Core Ultra 7 270K Plus** (και KF Plus) ή **Core i9-14900K / KF / KS**
  - **RAM ≥ 32 GB** (PC χωρίς RAM στο όνομα απορρίπτονται)
  - κάρτα γραφικών **AMD Radeon ή NVIDIA RTX με ≥ 16 GB VRAM**

  Laptops, mini PC και εξαρτήματα απορρίπτονται. Οι κανόνες είναι στο `watchlist.json` → `prebuilt` (`allowed_cpus`, `min_ram`, `min_vram`).
- Διαβάζει από το όνομα CPU / GPU / VRAM / RAM / SSD και βαθμολογεί:
  - **Fortnite** = 65% CPU (X3D κορυφή) + 35% GPU
  - **AI** = 75% VRAM + 25% GPU (AMD × 0,8: χωρίς CUDA, μόνο ROCm / Vulkan)
  - **Σύνολο** (± RAM) και **αξία** = βαθμός ανά 1.000 €
  - **★ ΣΤΟΧΟΣ** = 9800X3D με RTX 5070 Ti / 5080 / 5090 / 4090 ή RX 9070 XT / 7900 XTX
- **Περιφερειακά** σε ξεχωριστή καρτέλα:
  - οθόνες: AW2725DF, PG27AQDP/AQWP, LG 27GX790A, LG 27GR83Q
  - πληκτρολόγιο: **μόνο SteelSeries Apex Pro TKL Gen 3** (ενσύρματο ή Wireless, όχι full-size / Mini / Gen 2)
  - ποντίκια: **μόνο Logitech G Pro X2 Superstrike, Logitech G Pro X3 Superstrike, Razer Viper V4 Pro** Κάθε μοντέλο έχει σύντομη κριτική και link σε RTINGS.
- **Ιστορικό τιμών** (SQLite `history.sqlite`, ημερήσιο min): 30ήμερο χαμηλό, διάμεση, ιστορικό χαμηλό, γράφημα.
- **Έλεγχος έκπτωσης**: «ψεύτικη έκπτωση» όταν η τιμή ήταν ίδια ή χαμηλότερη μέσα σε 30 μέρες, ή είναι πάνω από την «ελάχιστη τιμή 30 ημερών» που δείχνει το κατάστημα (Omnibus). «Πραγματική έκπτωση» όταν επιβεβαιώνεται.
- **Κριτικές**: αστέρια και αριθμός κριτικών από Plaisio, e-gate, Praxi και την εισαγωγή από browser. Links σε Skroutz, BestPrice (ιστορικό τιμής & κριτικές) και YouTube review για κάθε προϊόν.
- **Black Friday** (27/11/2026): badge σε επιβεβαιωμένες εκπτώσεις 16/11–1/12 και links στις σελίδες Black Friday.

## Καταστήματα

| Αυτόματα | Πώς |
|---|---|
| Plaisio | κατηγορίες gaming desktops, οθόνες, πληκτρολόγια, ποντίκια |
| e-shop.gr | λίστα GAMER PC (με «ελάχιστη 30 ημερών») + αναζήτηση περιφερειακών |
| e-gate | αναζήτηση gaming desktop (Actina, MSI, ASUS ROG, Lenovo, E-GATE builds) |
| Praxi | αναζητήσεις 9800X3D / 7800X3D / 14900K / 270K Plus (Vengeance builds) |
| msystems | αναζήτηση gaming desktop / 9800X3D / 7800X3D |
| U-Case | WooCommerce Store API (αναζήτηση) |
| Tetrabyte | WooCommerce Store API (κυρίως εξαρτήματα) |
| i-aBox | κατάλογος + έτοιμα PC (κάθε παραλλαγή CPU/GPU/RAM με την τιμή της, από JSON-LD) |
| MG Manager | αναζήτηση (Crawl-delay 5 s) |
| KPL | sitemap.xml + σελίδες προϊόντων (η αναζήτηση απαγορεύεται στο robots.txt) |
| Κωτσόβολος | κατηγορίες desktops / gaming ποντίκια / πληκτρολόγια μέσω `getProductsByCategory` (επιτρέπεται ρητά στο robots.txt· η αναζήτηση όχι) |
| Germanos | μόνο περιφερειακά |

Τα περιφερειακά αναζητούνται σε όλα τα παραπάνω. Ο κώδικας **δεν** παρακάμπτει προστασίες και σέβεται το robots.txt. Γι' αυτό:

| Χειροκίνητα (links στον «Οδηγό» + bookmarklet) | Γιατί |
|---|---|
| Skroutz, You.gr | HTTP 403 σε αυτόματη ανάγνωση |
| Public | σελίδα JavaScript· το API του απαγορεύεται στο robots.txt |
| Cosmodata | τα προϊόντα φορτώνουν από Algolia στον browser |
| BestPrice | οι όροι του απαγορεύουν αυτόματη παρακολούθηση τιμών |
| Amazon.de / .it | οι όροι του απαγορεύουν αυτόματη ανάγνωση |
| Dell, Lenovo, HP | δεν πουλάνε online στην Ελλάδα (μόνο μέσω καταστημάτων) |

Για αυτά υπάρχει το **bookmarklet**:

1. Άνοιξε http://127.0.0.1:8765/bookmarklet και σύρε το κουμπί στη γραμμή σελιδοδεικτών.
2. Άνοιξε μια σελίδα αποτελεσμάτων στο Skroutz κ.λπ. στον browser σου και πάτα το bookmarklet.
3. Οι τιμές της σελίδας μπαίνουν στη λίστα ως «Εισαγωγή από browser» για 24 ώρες, με ιστορικό και βαθμολογία.

Τοπικά, αν το δίκτυο κάνει έλεγχο TLS (εταιρικό δίκτυο), κάνε `pip install truststore`: ο σκάνερ τότε χρησιμοποιεί τα πιστοποιητικά των Windows.

Το bookmarklet διαβάζει γενικά τις κάρτες προϊόντων (link + τιμή σε €). Αν κάποιο site αλλάξει εμφάνιση και δεν βρει προϊόντα, θα βγάλει μήνυμα.

## Email κάθε ώρα: νέες πραγματικές ευκαιρίες

Ρύθμιση στο `notify.json` (δεν ανεβαίνει στο GitHub· εκεί υπάρχει ως secret `NOTIFY_JSON`). **Χρειάζεται τον κωδικό**:
συμπλήρωσε `smtp_password` ή όρισε τη μεταβλητή περιβάλλοντος `PC_DEALS_SMTP_PASSWORD`. Δοκιμή:

```
python pc_deals.py --test-email
```

Αν δεν υπάρχει τοπικό `notify.json` (π.χ. σε νέο clone), το δοκιμαστικό στέλνεται από το GitHub: Actions → scan → Run workflow → «Μόνο δοκιμαστικό email».

Αν το Python βγάζει `SSLError` σε δίκτυο με έλεγχο TLS (εταιρικό proxy): `pip install truststore`. Το `pc_deals.py` το χρησιμοποιεί αυτόματα, ώστε να εμπιστεύεται τα πιστοποιητικά των Windows.

Κάθε ώρα φεύγει email **μόνο αν υπάρχουν νέες** ευκαιρίες. Ευκαιρία είναι κάθε διαθέσιμο προϊόν που ισχύει ένα από τα παρακάτω:

- είναι «ΕΞΑΙΡΕΤΙΚΗ» (βλ. παρακάτω)
- έχει **πραγματική** έκπτωση ≥ 5%, επιβεβαιωμένη από το ιστορικό ή το 30ήμερο χαμηλό του καταστήματος, όχι φουσκωμένη αρχική τιμή (`email_real_discount_min`)
- έπιασε **νέο ιστορικό χαμηλό**, ≥ 2% κάτω, με ≥ 3 μέρες ιστορικό (`email_new_low`)

«ΕΞΑΙΡΕΤΙΚΗ» (κανόνες στο `watchlist.json` -> `alerts`), αρκεί ένας, αν είναι διαθέσιμο:

- ≥10% κάτω από τη διάμεση 30 ημερών και φθηνότερο από κάθε τιμή του μήνα (θέλει ≥4 μέρες ιστορικό)
- ≥6% κάτω από το προηγούμενο ιστορικό χαμηλό
- επιβεβαιωμένη έκπτωση καταστήματος ≥20%
- PC-στόχος κάτω από: 5070 Ti 2.799 € · 5080 3.399 € · 4090 4.499 € · 5090 5.499 € · RX 9070 XT 2.399 € · RX 7900 XTX 2.899 €
- περιφερειακό ≥12% κάτω από την τιμή αναφοράς

Κάθε ευκαιρία στέλνεται μία φορά. Ξαναστέλνεται μόνο αν η τιμή πέσει ακόμα ≥ 2%. Στη σελίδα έχει το σήμα «ευκαιρία (email)».

## Αρχεία

| Αρχείο | Τι είναι |
|---|---|
| `pc_deals.py` | ο σκάνερ (σάρωση, βαθμολογία, ιστορικό, σελίδα, email) |
| `server.py` | τοπικός server της σελίδας (127.0.0.1:8765), ανανέωση, εισαγωγή bookmarklet |
| `watchlist.json` | πηγές, φίλτρα, περιφερειακά, κανόνες alerts, οδηγός, links |
| `notify.json` | ρυθμίσεις email |
| `history.sqlite` | ιστορικό τιμών (το παλιό `pc_deals.sqlite` μεταφέρθηκε για τα ελληνικά καταστήματα) |
| `reports/latest.html` | η σελίδα (ανοίγει και ως αρχείο, χωρίς κουμπί ανανέωσης) |
| `logs/hourly.log` | έξοδος της ωριαίας σάρωσης |

## Χρήση

```
python pc_deals.py               # πλήρης σάρωση + email
python pc_deals.py --no-email    # χωρίς email
python pc_deals.py --no-fetch    # ξαναφτιάχνει τη σελίδα από την τελευταία σάρωση
python pc_deals.py --debug       # δείχνει και τι απορρίφθηκε
python server.py                 # η σελίδα στο http://127.0.0.1:8765/
```

## Χρονοπρογραμματισμός

- Task Scheduler **PC Deals Relay** (εγκατάσταση: `powershell -ExecutionPolicy Bypass -File install_relay_task.ps1`): κάθε ώρα στο :05, `pythonw pc_deals.py --relay --log logs\relay.log`. Σαρώνει μόνο Plaisio / U-Case / Κωτσόβολο και κάνει push στο branch `relay`. Δεν στέλνει email.

```
schtasks /run /tn "PC Deals Relay"
schtasks /delete /tn "PC Deals Relay" /f
```

- Task Scheduler **PC Deals Hourly**: κάθε ώρα, `pythonw pc_deals.py --log logs\hourly.log` (χωρίς παράθυρο).
- Ο server πρέπει να τρέχει για το κουμπί ανανέωσης. Για αυτόματη εκκίνηση στο login, βάλε συντόμευση στον φάκελο Startup:

```
powershell -NoProfile -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Startup')+'\PC Deals Server.lnk');$s.TargetPath='C:\Python310\pythonw.exe';$s.Arguments='C:\claude\pc\server.py';$s.WorkingDirectory='C:\claude\pc';$s.Save()"
```

Χειροκίνητα: διπλό κλικ στο `start_server.cmd`.

```
schtasks /query /tn "PC Deals Hourly"
schtasks /run /tn "PC Deals Hourly"
schtasks /delete /tn "PC Deals Hourly" /f
```
