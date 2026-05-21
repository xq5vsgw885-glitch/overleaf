# Plant Identification – Morphologische Merkmalsmatrix

## Fachlicher Stand

### Bereits umgesetzt

1. **Wuchsform**
   - wuchsform
   - lebensform

2. **Spross/Stängel**
   - sprossform
   - sprossoberflaeche
   - milchsaft

3. **Blattstellung**
   - blattstellung

4. **Blattform**
   - blattform
   - blattgliederung

5. **Blattrand**
   - blattrand

6. **Blattnervatur**
   - nervatur

7. **Blattoberfläche/Behaarung**
   - blattoberflaeche
   - behaarung

8. **Blüte**
   - bluetentyp
   - bluetengroesse

9. **Blütenfarbe**
   - bluetenfarbe

10. **Blütensymmetrie**
    - bluetensymmetrie

11. **Blütenstand**
    - bluetenstand

12. **Frucht**
    - fruchttyp

13. **Samen/Ausbreitung**
    - ausbreitungseinheit

14. **Unterirdische Organe**
    - unterirdisches_organ

15. **Standortkontext**
    - standorttyp
    - feuchte
    - licht

16. **Phänologie**
    - bluetezeit
    - fruchtzeit

Alle 16 geplanten Merkmalsgruppen der ersten Merkmalsmatrix sind umgesetzt.
Es gibt keine offenen Merkmalsgruppen in diesem Bereich.

### Technische Hinweise

`DiagnosticWeight` enthält die Werte: `"sehr_hoch"`, `"hoch"`, `"mittel"`, `"niedrig"`.

`RequiredPhotoType` enthält die Werte: `"habitus"`, `"standort"`, `"detail"`, `"blatt"`, `"bluete"`, `"frucht"`.

## Nächster Entwicklungsschritt

Der nächste fachliche Schritt ist die Entwicklung eines **Scoring-/Vergleichsmodells** auf Basis der vorhandenen Merkmalsmatrix.

Dieses Modell ist noch nicht implementiert.

Es soll erfasste Merkmalswerte gewichten, kombinieren und mit Referenzdaten abgleichen, um eine merkmalsbasierte Pflanzenbestimmung zu ermöglichen.

Der **visuelle Fotoabgleich** bleibt weiterhin ausschließlich ein abschließender Kontrollschritt und ist noch nicht Teil der aktuellen Implementierung.
