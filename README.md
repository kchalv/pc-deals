# PC deals: έτοιμα gaming PC & περιφερειακά από ελληνικά καταστήματα

Σελίδα: **http://127.0.0.1:8765/** (κουμπί «↻ Ανανέωση τιμών»). Σάρωση κάθε ώρα και email για εξαιρετικές προσφορές.

Online αντίγραφο: **https://kchalv.github.io/pc-deals/** (GitHub Pages, repo `kchalv/pc-deals`). Ανεβαίνει αυτόματα μετά από
κάθε σάρωση από τον φάκελο `site/` (ρύθμιση `publish.json`, `--no-publish` για παράλειψη). Ανεβαίνει μόνο η σελίδα, χωρίς emails.

## Τι κάνει

- **Έτοιμα PC** από ελληνικά καταστήματα, μόνο **NVIDIA RTX** (για CUDA / local LLM / AI agents). Laptops, mini PC, εξαρτήματα και AMD/Intel κάρτες απορρίπτονται.
- Διαβάζει από το όνομα CPU / GPU / VRAM / RAM / SSD και βαθμολογεί:
  - **Fortnite** = 65% CPU (X3D κορυφή) + 35% GPU
  - **AI/CUDA** = 75% VRAM + 25% GPU
  - **Σύνολο** (± RAM) και **αξία** = βαθμός ανά 1.000 €
  - **★ ΣΤΟΧΟΣ** = 9800X3D / 9850X3D / 9900X3D / 9950X3D με RTX 5070 Ti / 5080 / 5090 / 4090
- **Περιφερειακά** σε ξεχωριστή καρτέλα: AW2725DF, PG27AQDP/AQWP, LG 27GX790A, LG 27GR83Q, Wooting 60HE+/80HE, Apex Pro TKL Gen 3, Viper V3 Pro, Superlight 2. Κάθε μοντέλο έχει σύντομη κριτική και link σε RTINGS.
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
| Praxi | αναζητήσεις RTX 5090 / 4090 / 5080 / 5070 Ti / 9800X3D / 9850X3D (Vengeance builds) |
| msystems | αναζήτηση gaming desktop |
| Germanos | μόνο περιφερειακά |

**Skroutz, Κωτσόβολος, Public, You.gr, BestPrice** μπλοκάρουν την αυτόματη ανάγνωση (HTTP 403 / JavaScript).
Ο κώδικας δεν παρακάμπτει την προστασία τους. Αντί γι' αυτό υπάρχει το **bookmarklet**:

1. Άνοιξε http://127.0.0.1:8765/bookmarklet και σύρε το κουμπί στη γραμμή σελιδοδεικτών.
2. Άνοιξε μια σελίδα αποτελεσμάτων στο Skroutz κ.λπ. στον browser σου και πάτα το bookmarklet.
3. Οι τιμές της σελίδας μπαίνουν στη λίστα ως «Εισαγωγή από browser» για 24 ώρες, με ιστορικό και βαθμολογία.

Το bookmarklet διαβάζει γενικά τις κάρτες προϊόντων (link + τιμή σε €). Αν κάποιο site αλλάξει εμφάνιση και δεν βρει προϊόντα, θα βγάλει μήνυμα.

## Email για εξαιρετικές προσφορές

Ρύθμιση στο `notify.json` (δεν ανεβαίνει στο GitHub· εκεί υπάρχει ως secret `NOTIFY_JSON`). **Χρειάζεται τον κωδικό**:
συμπλήρωσε `smtp_password` ή όρισε τη μεταβλητή περιβάλλοντος `PC_DEALS_SMTP_PASSWORD`. Δοκιμή:

```
python pc_deals.py --test-email
```

«ΕΞΑΙΡΕΤΙΚΗ» (κανόνες στο `watchlist.json` -> `alerts`), αρκεί ένας, αν είναι διαθέσιμο:

- ≥10% κάτω από τη διάμεση 30 ημερών και φθηνότερο από κάθε τιμή του μήνα (θέλει ≥4 μέρες ιστορικό)
- ≥6% κάτω από το προηγούμενο ιστορικό χαμηλό
- επιβεβαιωμένη έκπτωση καταστήματος ≥20%
- PC-στόχος κάτω από: 5070 Ti 2.799 € · 5080 3.399 € · 4090 4.499 € · 5090 5.499 €
- περιφερειακό ≥12% κάτω από την τιμή αναφοράς

Για κάθε προϊόν φεύγει ένα email. Ξαναστέλνει μόνο αν η τιμή πέσει ακόμα ≥2%.

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
