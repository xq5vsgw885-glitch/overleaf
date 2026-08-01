"""Hybrider Output-Adapter (Spezifikation §5).

## Prioritaet

1. `native`  — Structured Outputs bzw. erzwungenes Tool Calling, wenn der
   Provider das zuverlaessig unterstuetzt.
2. `prompt`  — promptbasiertes Schema-Enforcement als dokumentierter
   Fallback. Der bestehende `<<<AUDIT>>>`-Block IST dieser Fallback und
   nur noch dieser; er ist nicht mehr der primaere Audit-Transport (§5).

## Autoritaet

Syntaktisch valides Provider-JSON ist kein Akzeptanzkriterium. Autoritativ
sind ausschliesslich: Pydantic-Validierung, referenzielle Validierung,
Channel Reconciler, Hard-Fail-Policy. Der Adapter liefert deshalb nie ein
'fertiges' Ergebnis, sondern ein `AdapterOutcome` mit Rohtext, geparster
Struktur und Validierungsbefunden — die Entscheidung faellt weiter oben.

## Keine Netzaufrufe in Tests

Der Adapter kennt nur das Protokoll `StructuredProvider`. Die
Testfixtures implementieren es deterministisch (`ScriptedNativeProvider`,
`ScriptedPromptProvider`). Es gibt keinen Codepfad, der in Tests ein
externes Modell braucht (§12).
"""

import json
import re
from typing import Any, Dict, List, Optional, Protocol, Tuple

from audit_models import (AgentResult, OutputEnforcement, RunContext)
from identity import sha256_text
from policy import ErrorClass, HardFail

#: Legacy-Vertrag aus rag_start.py v1.0. Bleibt als Prompt-Fallback.
AUDIT_BLOCK_RE = re.compile(r"<<<AUDIT>>>\s*(\{.*?\})\s*<<<END_AUDIT>>>",
                            re.DOTALL)

#: Konservative Injektionsmuster (§9.1). Bewusst wenige und eindeutige:
#: Ein zu breiter Detektor wuerde fachliche Texte blockieren, und ein
#: blockierter fachlicher Text sieht im Export wie ein Fabrikationsbefund
#: aus.
INJECTION_PATTERNS = [
    re.compile(r"ignore (all|any|previous|prior) (previous |prior )?instructions",
               re.IGNORECASE),
    re.compile(r"disregard (the )?(above|previous|prior|system)", re.IGNORECASE),
    re.compile(r"<<<END_AUDIT>>>.*<<<AUDIT>>>", re.DOTALL),
    re.compile(r"\b(INSERT|UPDATE|DELETE|DROP)\s+(INTO\s+|FROM\s+|TABLE\s+)?"
               r"(runs|actions|assertions|audit_events|claims|chain_head)\b",
               re.IGNORECASE),
    re.compile(r"audit_trail\.db", re.IGNORECASE),
    re.compile(r"system\s*prompt\s*:", re.IGNORECASE),
]


def detect_injection(text: str) -> Optional[str]:
    """Gibt das erkannte Muster zurueck oder None."""
    for pattern in INJECTION_PATTERNS:
        match = pattern.search(text or "")
        if match:
            return match.group(0)[:120]
    return None


# ---------------------------------------------------------------------------
# Providerschnittstelle
# ---------------------------------------------------------------------------

class StructuredProvider(Protocol):
    """Minimalvertrag eines Providers.

    `name` und `supports_native` sind Eigenschaften des Providers, nicht
    des Aufrufers: Ob native Structured Outputs zuverlaessig funktionieren,
    entscheidet der Provider-Adapter und nicht die Experimentkonfiguration.
    """

    name: str
    supports_native: bool

    def generate(self, prompt: str, schema: Dict[str, Any],
                 mode: str) -> Tuple[str, Optional[dict]]:
        """Gibt (rohtext, struktur_oder_None) zurueck."""


class ScriptedNativeProvider:
    """Deterministischer Provider mit nativer Strukturausgabe (Testfixture)."""

    supports_native = True

    def __init__(self, responses: List[dict], name: str = "scripted-native"):
        self.name = name
        self._responses = list(responses)
        self.calls = 0

    def generate(self, prompt: str, schema: Dict[str, Any], mode: str):
        self.calls += 1
        payload = self._responses[min(self.calls - 1, len(self._responses) - 1)]
        return json.dumps(payload, ensure_ascii=False), payload


class ScriptedPromptProvider:
    """Deterministischer Provider ohne native Strukturausgabe (Testfixture).

    Liefert Freitext mit `<<<AUDIT>>>`-Block — genau der Legacy-Pfad.
    """

    supports_native = False

    def __init__(self, texts: List[str], name: str = "scripted-prompt"):
        self.name = name
        self._texts = list(texts)
        self.calls = 0

    def generate(self, prompt: str, schema: Dict[str, Any], mode: str):
        self.calls += 1
        text = self._texts[min(self.calls - 1, len(self._texts) - 1)]
        return text, None


# ---------------------------------------------------------------------------
# Ergebnis eines Adapteraufrufs
# ---------------------------------------------------------------------------

class AdapterOutcome:
    def __init__(self, raw_text: str, structured: Optional[dict],
                 mode: OutputEnforcement, provider: str,
                 parse_error: str = None, injection: str = None):
        self.raw_text = raw_text
        self.structured = structured
        self.mode = mode
        self.provider = provider
        self.parse_error = parse_error
        self.injection = injection

    @property
    def raw_sha256(self) -> str:
        return sha256_text(self.raw_text or "")

    def __repr__(self) -> str:                                # pragma: no cover
        return (f"<AdapterOutcome mode={self.mode.value} "
                f"provider={self.provider} parsed={self.structured is not None}>")


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------

class HybridOutputAdapter:
    """Providerunabhaengige Schnittstelle fuer strukturierte Ausgaben.

    Die Evaluierungsinvariante aus §5 ist hier verankert: Der Modus wird
    aus dem unveraenderlichen `RunContext` gelesen und darf innerhalb eines
    Runs nicht wechseln. Ein Wechselversuch ist §9.13.
    """

    def __init__(self, provider: StructuredProvider, context: RunContext):
        self.provider = provider
        self.context = context
        self._mode = context.output_enforcement
        if (self._mode is OutputEnforcement.NATIVE
                and not getattr(provider, "supports_native", False)):
            # Kein stiller Fallback: Der Modus ist eine Kontrollvariable des
            # Experiments. Ein automatischer Wechsel auf 'prompt' wuerde
            # zwei Bedingungen vermischen, ohne dass es auffaellt.
            raise HardFail(
                ErrorClass.OUTPUT_ENFORCEMENT_SWITCH,
                f"Kontext verlangt output_enforcement=native, Provider "
                f"{provider.name!r} unterstuetzt das nicht. Der Modus wird "
                f"nicht stillschweigend gewechselt (§5).")

    @property
    def mode(self) -> OutputEnforcement:
        return self._mode

    def assert_mode(self, mode) -> None:
        """§5/§9.13 — Modus darf innerhalb eines Runs nicht wechseln."""
        wanted = OutputEnforcement(mode)
        if wanted is not self._mode:
            raise HardFail(
                ErrorClass.OUTPUT_ENFORCEMENT_SWITCH,
                f"output_enforcement wechselt innerhalb des Runs: "
                f"{self._mode.value} -> {wanted.value}")

    def schema(self) -> Dict[str, Any]:
        return AgentResult.model_json_schema()

    def prompt_contract(self, run_id: str, agent_id: str) -> str:
        """Der dokumentierte Prompt-Fallback (§5)."""
        return PROMPT_CONTRACT.format(run_id=run_id, agent_id=agent_id)

    def generate(self, prompt: str) -> AdapterOutcome:
        raw, structured = self.provider.generate(
            prompt, self.schema(), self._mode.value)
        injection = detect_injection(raw)
        parse_error = None
        if structured is None:
            structured, parse_error = self._parse(raw)
        return AdapterOutcome(raw, structured, self._mode, self.provider.name,
                              parse_error=parse_error, injection=injection)

    def _parse(self, raw: str) -> Tuple[Optional[dict], Optional[str]]:
        """Struktur aus Rohtext gewinnen.

        Reihenfolge: erst der Legacy-`<<<AUDIT>>>`-Block, dann der Versuch,
        den gesamten Text als JSON zu lesen. Die umgekehrte Reihenfolge
        waere fehleranfaellig, weil ein Freitext mit eingebettetem JSON
        haeufig auch ausserhalb des Blocks JSON-aehnliche Fragmente hat.
        """
        match = AUDIT_BLOCK_RE.search(raw or "")
        candidate = match.group(1) if match else (raw or "").strip()
        if not candidate:
            return None, "leere Ausgabe"
        try:
            data = json.loads(candidate)
        except json.JSONDecodeError as exc:
            return None, f"kein gueltiges JSON: {exc}"
        if not isinstance(data, dict):
            return None, "Wurzelobjekt ist kein JSON-Objekt"
        return data, None


PROMPT_CONTRACT = """\
AUDIT-PFLICHT (nicht verhandelbar, wird maschinell geprueft):

Beende deine finale Antwort mit einem Evidenzblock in genau dieser Form:

<<<AUDIT>>>
{{"schema_version": "2.0.0", "run_id": "{run_id}", "agent_id": "{agent_id}",
  "claims": [
    {{"claim_id": "c1", "text": "...", "stance": "supports",
     "evidence_free": false,
     "evidence": [
       {{"evidence_id": "e1", "source_ref": "pfad/oder/doi",
        "locator": "S. 42", "quote": "...", "required": true}}
     ]}}
  ]}}
<<<END_AUDIT>>>

Regeln:
- source_ref ist Pfad, DOI oder Zotero-Key einer Quelle, die du in DIESEM
  Lauf tatsaechlich geoeffnet hast. Pfadangabe mit Verzeichnis und Endung.
  Nicht aus dem Gedaechtnis zitieren.
- stance ist "supports", "contradicts" oder "unclear".
- Eine Aussage ohne externe Quelle (Definition, Rechenweg) markierst du mit
  "evidence_free": true und leerer evidence-Liste. Sie gilt dann als
  UNVERIFIED, nicht als Fehler.
- Eine leere claims-Liste ist zulaessig. Eine erfundene Quelle nicht.
- Schreibe NICHT selbst in die Audit-Datenbank. Der Schreibzugriff liegt
  ausschliesslich beim Audit-Writer-Prozess.
"""
