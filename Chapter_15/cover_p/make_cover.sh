#!/bin/bash
pdflatex -interaction=nonstopmode -jobname=tmp 0.tex
gs -sDEVICE=pdfwrite -dPDFFitPage -sPAPERSIZE=a3 -o 0.pdf tmp.pdf
rm -f tmp.*
