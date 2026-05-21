export type DiagnosticWeight = "hoch" | "mittel" | "niedrig";

export type PhotoVisibility = "true" | "bedingt" | "false";

export type RequiredPhotoType = "habitus" | "standort" | "detail" | "blatt";

export interface MorphologicalFeature {
  id: string;
  group: string;
  name: string;
  possibleValues: string[];
  diagnosticWeight: DiagnosticWeight;
  photoVisibility: PhotoVisibility;
  requiredPhotoTypes: RequiredPhotoType[];
  userExplanation: string;
}

export const MORPHOLOGICAL_FEATURE_MATRIX: MorphologicalFeature[] = [
  // Gruppe 1: Wuchsform
  {
    id: "wuchsform",
    group: "Wuchsform",
    name: "Wuchsform",
    possibleValues: [
      "krautig",
      "grasartig",
      "rosettig",
      "strauchig",
      "baumförmig",
      "kletternd",
      "kriechend",
      "schwimmend",
      "wasserpflanze_untergetaucht",
    ],
    diagnosticWeight: "mittel",
    photoVisibility: "true",
    requiredPhotoTypes: ["habitus"],
    userExplanation:
      "Beschreibt die äußere Gesamtgestalt der Pflanze, zum Beispiel ob sie krautig, grasartig, verholzt, kletternd oder rosettig wächst.",
  },
  {
    id: "lebensform",
    group: "Wuchsform",
    name: "Lebensform",
    possibleValues: [
      "einjährig",
      "zweijährig",
      "ausdauernd",
      "holzig",
      "immergrün",
      "sommergrün",
    ],
    diagnosticWeight: "niedrig",
    photoVisibility: "bedingt",
    requiredPhotoTypes: ["habitus", "standort"],
    userExplanation:
      "Beschreibt die Lebensdauer und Überdauerungsweise der Pflanze. Dieses Merkmal ist auf Fotos oft nur indirekt erkennbar und wird daher niedrig gewichtet.",
  },

  // Gruppe 2: Spross/Stängel
  {
    id: "sprossform",
    group: "Spross/Stängel",
    name: "Sprossform",
    possibleValues: [
      "aufrecht",
      "aufsteigend",
      "niederliegend",
      "kriechend",
      "kletternd",
      "windend",
      "rankend",
      "verzweigt",
      "unverzweigt",
    ],
    diagnosticWeight: "mittel",
    photoVisibility: "bedingt",
    requiredPhotoTypes: ["habitus", "detail"],
    userExplanation:
      "Beschreibt die Gestalt und Wuchsrichtung des Sprosses oder Stängels, zum Beispiel ob er aufrecht, kriechend, kletternd oder windend wächst.",
  },
  {
    id: "sprossoberflaeche",
    group: "Spross/Stängel",
    name: "Sprossoberfläche",
    possibleValues: [
      "glatt",
      "gerieft",
      "gefurcht",
      "kantig",
      "rund",
      "hohl",
      "behaart",
      "stachelig",
      "druesig",
    ],
    diagnosticWeight: "niedrig",
    photoVisibility: "bedingt",
    requiredPhotoTypes: ["detail"],
    userExplanation:
      "Beschreibt sichtbare Oberflächenmerkmale des Stängels, etwa ob er glatt, kantig, hohl, behaart oder gefurcht ist.",
  },
  {
    id: "milchsaft",
    group: "Spross/Stängel",
    name: "Milchsaft",
    possibleValues: ["vorhanden", "nicht_vorhanden", "weiß", "gelblich", "orange"],
    diagnosticWeight: "niedrig",
    photoVisibility: "false",
    requiredPhotoTypes: ["detail"],
    userExplanation:
      "Beschreibt, ob beim Verletzen der Pflanze Milchsaft austritt. Dieses Merkmal ist auf normalen Fotos meist nicht sichtbar und darf nur vorsichtig bewertet werden.",
  },

  // Gruppe 3: Blattstellung
  {
    id: "blattstellung",
    group: "Blattstellung",
    name: "Blattstellung",
    possibleValues: [
      "wechselständig",
      "gegenständig",
      "kreuzgegenständig",
      "quirlig",
      "grundständig",
      "rosettig",
      "zweizeilig",
    ],
    diagnosticWeight: "hoch",
    photoVisibility: "bedingt",
    requiredPhotoTypes: ["habitus", "blatt", "detail"],
    userExplanation:
      "Beschreibt, wie die Blätter am Spross angeordnet sind. Die Blattstellung ist ein wichtiges diagnostisches Merkmal, weil sie häufig Familien, Gattungen oder Artengruppen eingrenzt.",
  },
];

export function getFeaturesByGroup(group: string): MorphologicalFeature[] {
  return MORPHOLOGICAL_FEATURE_MATRIX.filter((f) => f.group === group);
}

export function getFeatureById(id: string): MorphologicalFeature | undefined {
  return MORPHOLOGICAL_FEATURE_MATRIX.find((f) => f.id === id);
}

export function getHighDiagnosticFeatures(): MorphologicalFeature[] {
  return MORPHOLOGICAL_FEATURE_MATRIX.filter(
    (f) => f.diagnosticWeight === "hoch"
  );
}
