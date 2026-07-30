"""OMML → LaTeX.

Warum kein XSLT: Der kanonische Weg (OMML2MML.XSL → MathML → LaTeX) ist eine
zweistufige Kette mit einer proprietären Microsoft-Stylesheet-Datei, die
mitgeliefert und lizenzrechtlich mitgeschleppt werden muss, und er verliert
bei jedem Zwischenschritt Semantik. Für den in Physik-Folien tatsächlich
auftretenden OMML-Teilraum ist ein direkter rekursiver Parser kürzer,
abhängigkeitsfrei und diagnostizierbar.

ABDECKUNG: Brüche, Sub-/Superskripte, Wurzeln, n-äre Operatoren (Σ ∫ ∏),
Klammern, Matrizen, Akzente, Überstriche, Funktionsnamen, Limites.
Alles Nichterkannte erzeugt eine Warnung statt stiller Auslassung — das
ist der wichtigere Teil.
"""

import re

M = "{http://schemas.openxmlformats.org/officeDocument/2006/math}"

# Unicode-Mathematik → LaTeX. Auf den physikalisch relevanten Kern beschränkt.
SYMBOLS = {
    "α": r"\alpha", "β": r"\beta", "γ": r"\gamma", "δ": r"\delta",
    "ε": r"\varepsilon", "ζ": r"\zeta", "η": r"\eta", "θ": r"\theta",
    "κ": r"\kappa", "λ": r"\lambda", "μ": r"\mu", "ν": r"\nu", "ξ": r"\xi",
    "π": r"\pi", "ρ": r"\rho", "σ": r"\sigma", "τ": r"\tau", "φ": r"\varphi",
    "χ": r"\chi", "ψ": r"\psi", "ω": r"\omega",
    "Γ": r"\Gamma", "Δ": r"\Delta", "Θ": r"\Theta", "Λ": r"\Lambda",
    "Ξ": r"\Xi", "Π": r"\Pi", "Σ": r"\Sigma", "Φ": r"\Phi", "Ψ": r"\Psi",
    "Ω": r"\Omega",
    "ℏ": r"\hbar", "∂": r"\partial", "∇": r"\nabla", "∞": r"\infty",
    "≤": r"\leq", "≥": r"\geq", "≠": r"\neq", "≈": r"\approx",
    "≡": r"\equiv", "∝": r"\propto", "±": r"\pm", "∓": r"\mp",
    "×": r"\times", "·": r"\cdot", "→": r"\to", "⟨": r"\langle",
    "⟩": r"\rangle", "∈": r"\in", "∫": r"\int", "∑": r"\sum", "∏": r"\prod",
    "√": r"\sqrt", "†": r"^{\dagger}", "⊗": r"\otimes",
}

NARY = {"∑": r"\sum", "∫": r"\int", "∏": r"\prod", "∮": r"\oint",
        "⋃": r"\bigcup", "⋂": r"\bigcap"}

ACCENTS = {"̂": r"\hat", "⃗": r"\vec", "̄": r"\bar", "̇": r"\dot",
           "̈": r"\ddot", "̃": r"\tilde"}


def _escape_text(text: str) -> str:
    out = []
    for ch in text:
        sym = SYMBOLS.get(ch)
        if sym is None:
            out.append(ch)
        elif sym[1:].isalpha():
            # Trennzeichen zwingend: sonst wird aus \partial + "t" das
            # undefinierte Makro \partialt, und LaTeX bricht erst beim
            # Kompilieren ab — weit entfernt von der Ursache.
            out.append(sym + " ")
        else:
            out.append(sym)
    return "".join(out)


def _child(node, tag):
    return node.find(M + tag)


def _children_text(node, tag, warnings):
    sub = _child(node, tag)
    return convert_node(sub, warnings) if sub is not None else ""


def convert_node(node, warnings: list) -> str:
    """Rekursiver Abstieg über einen OMML-Knoten."""
    if node is None:
        return ""
    tag = node.tag.replace(M, "") if node.tag.startswith(M) else node.tag

    if tag == "t":                                   # Textlauf
        return _escape_text(node.text or "")

    if tag in ("oMath", "oMathPara", "e", "num", "den", "sup", "sub",
               "deg", "lim", "fName", "r"):
        return "".join(convert_node(c, warnings) for c in node)

    if tag == "f":                                   # Bruch
        num = _children_text(node, "num", warnings)
        den = _children_text(node, "den", warnings)
        return rf"\frac{{{num}}}{{{den}}}"

    if tag == "sSup":
        return (f"{{{_children_text(node, 'e', warnings)}}}"
                f"^{{{_children_text(node, 'sup', warnings)}}}")

    if tag == "sSub":
        return (f"{{{_children_text(node, 'e', warnings)}}}"
                f"_{{{_children_text(node, 'sub', warnings)}}}")

    if tag == "sSubSup":
        return (f"{{{_children_text(node, 'e', warnings)}}}"
                f"_{{{_children_text(node, 'sub', warnings)}}}"
                f"^{{{_children_text(node, 'sup', warnings)}}}")

    if tag == "rad":
        deg = _children_text(node, "deg", warnings)
        body = _children_text(node, "e", warnings)
        return rf"\sqrt[{deg}]{{{body}}}" if deg else rf"\sqrt{{{body}}}"

    if tag == "nary":
        pr = _child(node, "naryPr")
        chr_el = pr.find(M + "chr") if pr is not None else None
        symbol = chr_el.get(M + "val") if chr_el is not None else "∫"
        op = NARY.get(symbol)
        if op is None:
            op = NARY.get("∫")
            warnings.append(f"unbekannter n-ärer Operator '{symbol}'")
        sub = _children_text(node, "sub", warnings)
        sup = _children_text(node, "sup", warnings)
        body = _children_text(node, "e", warnings)
        out = op
        if sub:
            out += f"_{{{sub}}}"
        if sup:
            out += f"^{{{sup}}}"
        return f"{out} {body}"

    if tag == "d":                                   # Klammerausdruck
        pr = _child(node, "dPr")
        beg, end = "(", ")"
        if pr is not None:
            b = pr.find(M + "begChr")
            e = pr.find(M + "endChr")
            if b is not None:
                beg = b.get(M + "val") or beg
            if e is not None:
                end = e.get(M + "val") or end
        inner = "".join(convert_node(c, warnings)
                        for c in node if c.tag != M + "dPr")
        beg = {"⟨": r"\langle", "{": r"\{", "|": "|", "[": "["}.get(beg, beg)
        end = {"⟩": r"\rangle", "}": r"\}", "|": "|", "]": "]"}.get(end, end)
        return rf"\left{beg} {inner} \right{end}"

    if tag == "m":                                   # Matrix
        rows = []
        for mr in node.findall(M + "mr"):
            rows.append(" & ".join(
                convert_node(e, warnings) for e in mr.findall(M + "e")))
        return r"\begin{pmatrix}" + r" \\ ".join(rows) + r"\end{pmatrix}"

    if tag == "acc":
        pr = _child(node, "accPr")
        chr_el = pr.find(M + "chr") if pr is not None else None
        mark = chr_el.get(M + "val") if chr_el is not None else "̂"
        cmd = ACCENTS.get(mark, r"\hat")
        if mark not in ACCENTS:
            warnings.append(f"unbekannter Akzent '{mark}' → \\hat angenommen")
        return f"{cmd}{{{_children_text(node, 'e', warnings)}}}"

    if tag == "bar":
        return rf"\overline{{{_children_text(node, 'e', warnings)}}}"

    if tag == "func":
        name = _children_text(node, "fName", warnings)
        return rf"\operatorname{{{name}}}({_children_text(node, 'e', warnings)})"

    if tag == "limLow":
        return (f"{_children_text(node, 'e', warnings)}"
                f"_{{{_children_text(node, 'lim', warnings)}}}")

    if tag == "limUpp":
        return (f"{_children_text(node, 'e', warnings)}"
                f"^{{{_children_text(node, 'lim', warnings)}}}")

    if tag.endswith("Pr") or tag in ("ctrlPr", "rPr"):
        return ""                                    # reine Formatierung

    # Unbekannt: Inhalt retten, aber protokollieren. Stille Auslassung wäre
    # der gefährlichste Fall — der Text sähe danach korrekt aus.
    warnings.append(f"unbehandeltes OMML-Element <m:{tag}>")
    return "".join(convert_node(c, warnings) for c in node)


def omml_to_latex(element) -> tuple:
    """Gibt (latex, warnings) zurück."""
    warnings: list = []
    latex = convert_node(element, warnings)
    latex = re.sub(r"\s+", " ", latex).strip()
    return latex, warnings
