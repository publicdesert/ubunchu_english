<div align="center">

  <h3 align="center">Ubunchu Fan Translations</h3>

  <p align="center">
    My english fan translations for several chapters of the Ubunchu manga

  </p>
</div>

## About

Ubunchu is a manga about a high school's "Sysadmin Club" created by Hiroshi Seo. It was published between 2008 and 2013 by Ubuntu Magazine Japan. Most chapters were released under open licenses, which allowed for community translation projects.

This repository contains English-language fan translations and typeset versions of selected chapters, created for non-commercial purposes. Where possible, links to official sources are provided.

### My releases
| Chapter | Links |
|---|---|
| Chapter 12 | [PDF](https://raw.githubusercontent.com/publicdesert/ubunchu_english/main/Chapter_12/Ubunchu_12_eng.pdf), [PDF (compressed)](https://raw.githubusercontent.com/publicdesert/ubunchu_english/main/Chapter_12/Ubunchu_12_eng_compressed.pdf), [CBZ](https://raw.githubusercontent.com/publicdesert/ubunchu_english/main/Chapter_12/Ubunchu_12_eng.cbz)|
|Chapter 13 | [PDF](https://raw.githubusercontent.com/publicdesert/ubunchu_english/main/Chapter_13/Ubunchu_13_eng.pdf), [PDF (compressed)](https://raw.githubusercontent.com/publicdesert/ubunchu_english/main/Chapter_13/Ubunchu_13_eng_compressed.pdf), [CBZ](https://raw.githubusercontent.com/publicdesert/ubunchu_english/main/Chapter_13/Ubunchu_13_eng.cbz) |
|Chapter 15 | [Reading Aid PDF](https://raw.githubusercontent.com/publicdesert/ubunchu_english/main/Chapter_15/Ubunchu_15_eng_aid.pdf)
|Special Chapters | [Reading Aid PDF](https://raw.githubusercontent.com/publicdesert/ubunchu_english/main/Specials/Ubunchu_Specials_eng_aid.pdf) 

### Other translated chapters

Translated versions of chapters 01 to 08 are available at: https://gitlab.com/ubunchu-translators/ubunchu/

Translated versions of chapters 09 and onwards available at: https://sirtetris.gitlab.io/ubunchu-translation/

### Original untranslated chapters
| Chapter | Links |
|---|---|
|Chapter 12 | [PDF & CC Release announcement](https://web.archive.org/web/20160321151216/http://ubuntu.asciimw.jp/elem/000/000/010/10503/) |
|Chapter 13 | [PDF & CC Release announcement](https://web.archive.org/web/20160321151221/http://ubuntu.asciimw.jp/elem/000/000/010/10533/) |
|Chapter 15 | [Purchase on Bookwalker](https://bookwalker.jp/de25473cc5-4d0a-4223-88f8-2a2ac86e0182/), [Purchase on Amazon Japan](https://www.amazon.co.jp/-/en/dp/B00D8R85MC) |
|Special chapters | [Purchase on Bookwalker](https://bookwalker.jp/decf255320-459b-4d7c-92d3-8d5281052c28/), [Purchase on Amazon Japan](https://www.amazon.co.jp/-/en/dp/B00N4M5S8K) |

## On Chapter 15 and the Special Chapters

Please note: this repository does not include the original manga artwork for Chapter 15 and the Special Chapters. These chapters were not explicitly released under the same permissive license as earlier ones. However, official copies are available for purchase through platforms such as Bookwalker and Amazon Japan. The translations here are provided as text-only reading aids, aligned to match the original page layouts, so they can be read alongside legally obtained copies.

## Attribution
### Chapters 12 and 13
First printed in: Ubuntu Magazine Japan\
Published by: ASCII Media Works Inc. (ubuntu.asciimw.jp)\
Created by: Hiroshi Seo (aerialline.com)\
English translation: Tarek Saier (sirtetris.com)\
Cleaning and typesetting: PublicDesert (github.com/publicdesert)

The original manga is licensed unter a [CC BY-NC-SA 2.1 JP License](https://creativecommons.org/licenses/by-nc-sa/2.1/jp/deed.en).
The english translation is licensed under a [CC BY-NC-SA 4.0 License](https://creativecommons.org/licenses/by-nc-sa/4.0/).

### Chapter 15 and special chapters
First printed in: Ubuntu Magazine Japan / Ubunchu Tankōbon\
Published by: ASCII Media Works Inc. (ubuntu.asciimw.jp)\
Created by: Hiroshi Seo (aerialline.com)\
English translation and editing: PublicDesert (github.com/publicdesert)

All modfications to the original manga such as the translation text and the graphics overlaying the original manga are licensed under a [CC BY-NC-SA 4.0 License](https://creativecommons.org/licenses/by-nc-sa/4.0/).

## Process
### Extracting from the PDF (Chapters 12 & 13)
1. Images are extracted from the pdfs using the Poppler `pdfimages` tool.
2. Masks for covering text are done in Gimp (would probably do this in Inkscape now).
3. Finally the text is typset in Inkscape.

### Building
The `build.py` script is used to compile all published variants. `pcopy.sh` is used to strip non-free assets from the work files before publishing into this repo.

Compressed versions are created with
```
convert -density 50x50 -quality 40 -compress jpeg ./Ubunchu_12_eng.pdf Ubunchu_12_eng_compressed.pdf
```
for chapter 12 and double the density for chapter 13 since the png extracted from the pdf are around double the size.


## Fonts
CC Wild Words is used for speech and similar text, Lemon Milk for headings.
