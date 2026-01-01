# Elections Scraper (PS 2017)

Tento projekt slúži na stiahnutie výsledkov parlamentných volieb v ČR z roku 2017
pre zvolený okres priamo zo stránky https://www.volby.cz.

Projekt bol vytvorený ako 3. projekt v rámci Engeto Online Python Akademie.

---

## Inštalácia

Odporúčaný postup je použiť virtuálne prostredie.

python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

---

## Spustenie projektu

Skript sa spúšťa pomocou dvoch argumentov:

- URL okresu z webu volby.cz
- názov výstupného CSV súboru

Príklad spustenia:

python main.py "https://www.volby.cz/pls/ps2017nss/ps32?xjazyk=CZ&xkraj=2&xnumnuts=2105" "vysledky_kutna_hora.csv"

---

## Výstup

Výsledkom je CSV súbor, kde každý riadok obsahuje údaje o jednej obci:

- kód obce
- názov obce
- voliči v zozname
- vydané obálky
- platné hlasy
- počet hlasov pre každú kandidujúcu stranu

Ukážkový výstup je uložený v súbore vysledky_kutna_hora.csv.

---

## Autor

Lubomír Tatran
