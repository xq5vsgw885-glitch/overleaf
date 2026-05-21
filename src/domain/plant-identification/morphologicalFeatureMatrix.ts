export type DiagnosticWeight = "sehr_hoch" | "hoch" | "mittel" | "niedrig";

export type PhotoVisibility = "true" | "bedingt" | "false";

export type RequiredPhotoType = "habitus" | "standort" | "detail" | "blatt" | "bluete" | "frucht";

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

  // Gruppe 4: Blattform
  {
    id: "blattform",
    group: "Blattform",
    name: "Blattform",
    possibleValues: [
      "linealisch",
      "lanzettlich",
      "eiförmig",
      "verkehrt_eiförmig",
      "elliptisch",
      "rundlich",
      "herzförmig",
      "nierenförmig",
      "pfeilförmig",
      "spießförmig",
      "nadelförmig",
      "schuppenförmig",
    ],
    diagnosticWeight: "mittel",
    photoVisibility: "true",
    requiredPhotoTypes: ["blatt", "detail"],
    userExplanation:
      "Beschreibt die äußere Form der Blattspreite. Die Blattform hilft bei der Eingrenzung, ist aber innerhalb vieler Arten variabel und wird deshalb nur mittel gewichtet.",
  },
  {
    id: "blattgliederung",
    group: "Blattform",
    name: "Blattgliederung",
    possibleValues: [
      "einfach",
      "dreizählig",
      "gefingert",
      "gefiedert",
      "doppelt_gefiedert",
      "fiederteilig",
      "handförmig_gelappt",
      "fiederlappig",
      "ungeteilt",
    ],
    diagnosticWeight: "mittel",
    photoVisibility: "true",
    requiredPhotoTypes: ["blatt", "detail"],
    userExplanation:
      "Beschreibt, ob ein Blatt einfach, gelappt, geteilt oder aus mehreren Teilblättchen zusammengesetzt ist. Dieses Merkmal ist für viele Pflanzengruppen diagnostisch nützlich.",
  },

  // Gruppe 5: Blattrand
  {
    id: "blattrand",
    group: "Blattrand",
    name: "Blattrand",
    possibleValues: [
      "ganzrandig",
      "gesägt",
      "doppelt_gesägt",
      "gezähnt",
      "gekerbt",
      "gebuchtet",
      "gelappt",
      "gewellt",
      "dornig",
      "bewimpert",
    ],
    diagnosticWeight: "mittel",
    photoVisibility: "true",
    requiredPhotoTypes: ["blatt", "detail"],
    userExplanation:
      "Beschreibt die Ausgestaltung des Blattrandes, zum Beispiel ob er glatt, gesägt, gezähnt, gekerbt, gelappt oder dornig ist. Der Blattrand unterstützt die Eingrenzung, ist aber allein nicht artentscheidend.",
  },

  // Gruppe 6: Blattnervatur
  {
    id: "nervatur",
    group: "Blattnervatur",
    name: "Blattnervatur",
    possibleValues: [
      "parallelnervig",
      "bogennervig",
      "fiedernervig",
      "handnervig",
      "netznervig",
      "einnervig",
      "mehrnervig",
    ],
    diagnosticWeight: "mittel",
    photoVisibility: "bedingt",
    requiredPhotoTypes: ["blatt", "detail"],
    userExplanation:
      "Beschreibt den Verlauf der Blattadern. Die Blattnervatur hilft besonders bei der groben Einordnung von Pflanzengruppen, ist aber allein nicht artentscheidend.",
  },

  // Gruppe 7: Blattoberfläche/Behaarung
  {
    id: "blattoberflaeche",
    group: "Blattoberfläche/Behaarung",
    name: "Blattoberfläche",
    possibleValues: [
      "glatt",
      "runzelig",
      "glänzend",
      "matt",
      "lederig",
      "wachsig",
      "bereift",
      "druesig",
      "rau",
    ],
    diagnosticWeight: "niedrig",
    photoVisibility: "bedingt",
    requiredPhotoTypes: ["blatt", "detail"],
    userExplanation:
      "Beschreibt sichtbare Oberflächenmerkmale des Blattes, etwa ob es glatt, rau, glänzend, matt, wachsig oder bereift wirkt. Dieses Merkmal ist fotoabhängig und wird deshalb niedrig gewichtet.",
  },
  {
    id: "behaarung",
    group: "Blattoberfläche/Behaarung",
    name: "Behaarung",
    possibleValues: [
      "kahl",
      "locker_behaart",
      "dicht_behaart",
      "filzig",
      "zottig",
      "borstig",
      "seidig",
      "sternhaarig",
      "druesig_behaart",
    ],
    diagnosticWeight: "mittel",
    photoVisibility: "bedingt",
    requiredPhotoTypes: ["blatt", "detail"],
    userExplanation:
      "Beschreibt Art und Stärke der Behaarung. Behaarung kann diagnostisch hilfreich sein, ist aber oft nur auf Detailfotos sicher zu erkennen.",
  },

  // Gruppe 8: Blüte
  {
    id: "bluetentyp",
    group: "Blüte",
    name: "Blütentyp",
    possibleValues: [
      "einzelbluete",
      "scheinbluete",
      "korbbluete",
      "lippenbluete",
      "schmetterlingsbluete",
      "roehrenbluete",
      "zungenbluete",
      "glockenfoermig",
      "trichterfoermig",
      "unscheinbar",
    ],
    diagnosticWeight: "hoch",
    photoVisibility: "bedingt",
    requiredPhotoTypes: ["bluete", "detail"],
    userExplanation:
      "Beschreibt den erkennbaren Grundtyp der Blüte. Der Blütentyp ist für viele Pflanzenfamilien diagnostisch wichtig, muss aber mit weiteren Blütenmerkmalen kombiniert werden.",
  },
  {
    id: "bluetengroesse",
    group: "Blüte",
    name: "Blütengröße",
    possibleValues: [
      "sehr_klein",
      "klein",
      "mittel",
      "groß",
      "sehr_groß",
    ],
    diagnosticWeight: "niedrig",
    photoVisibility: "bedingt",
    requiredPhotoTypes: ["bluete", "detail"],
    userExplanation:
      "Beschreibt die ungefähre Größe der Blüte. Dieses Merkmal ist ohne Maßstab oft unsicher und wird deshalb niedrig gewichtet.",
  },

  // Gruppe 9: Blütenfarbe
  {
    id: "bluetenfarbe",
    group: "Blütenfarbe",
    name: "Blütenfarbe",
    possibleValues: [
      "weiß",
      "gelb",
      "orange",
      "rot",
      "rosa",
      "violett",
      "blau",
      "grün",
      "braun",
      "schwarz",
      "mehrfarbig",
      "unscheinbar",
    ],
    diagnosticWeight: "niedrig",
    photoVisibility: "true",
    requiredPhotoTypes: ["bluete"],
    userExplanation:
      "Beschreibt die auffällige Grundfarbe der Blüte. Die Blütenfarbe ist für Nutzer leicht erfassbar, kann aber innerhalb einer Art variieren und wird deshalb niedrig gewichtet.",
  },

  // Gruppe 10: Blütensymmetrie
  {
    id: "bluetensymmetrie",
    group: "Blütensymmetrie",
    name: "Blütensymmetrie",
    possibleValues: [
      "radiärsymmetrisch",
      "zygomorph",
      "asymmetrisch",
      "scheinbar_radiärsymmetrisch",
      "unscheinbar_nicht_beurteilbar",
    ],
    diagnosticWeight: "sehr_hoch",
    photoVisibility: "bedingt",
    requiredPhotoTypes: ["bluete", "detail"],
    userExplanation:
      "Beschreibt, ob eine Blüte radiärsymmetrisch, zweiseitig symmetrisch oder asymmetrisch aufgebaut ist. Die Blütensymmetrie ist ein sehr wichtiges diagnostisches Merkmal, muss aber mit weiteren Blüten- und Pflanzenmerkmalen kombiniert werden.",
  },

  // Gruppe 11: Blütenstand
  {
    id: "bluetenstand",
    group: "Blütenstand",
    name: "Blütenstand",
    possibleValues: [
      "einzelbluete",
      "traube",
      "aehre",
      "rispe",
      "dolde",
      "doppeldolde",
      "koerbchen",
      "koepfchen",
      "kolben",
      "wickel",
      "schirmrispe",
      "quirl",
      "scheinquirl",
      "unscheinbar",
    ],
    diagnosticWeight: "hoch",
    photoVisibility: "bedingt",
    requiredPhotoTypes: ["habitus", "bluete", "detail"],
    userExplanation:
      "Beschreibt die Anordnung der Blüten an der Pflanze, zum Beispiel als Traube, Ähre, Rispe, Dolde, Körbchen oder Köpfchen. Der Blütenstand ist diagnostisch wichtig, muss aber mit weiteren Merkmalen kombiniert werden.",
  },

  // Gruppe 12: Frucht
  {
    id: "fruchttyp",
    group: "Frucht",
    name: "Fruchttyp",
    possibleValues: [
      "kapsel",
      "schote",
      "schötchen",
      "beere",
      "steinfrucht",
      "nuss",
      "achäne",
      "sammelfrucht",
      "spaltfrucht",
      "fluegelfrucht",
      "balgfrucht",
      "huelse",
      "zapfen",
      "frucht_nicht_sichtbar",
    ],
    diagnosticWeight: "sehr_hoch",
    photoVisibility: "bedingt",
    requiredPhotoTypes: ["frucht", "detail"],
    userExplanation:
      "Beschreibt den erkennbaren Fruchttyp, zum Beispiel Kapsel, Schote, Beere, Nuss, Achäne oder Spaltfrucht. Der Fruchttyp ist diagnostisch sehr wichtig, aber nur nutzbar, wenn Früchte vorhanden und sichtbar sind.",
  },

  // Gruppe 13: Samen/Ausbreitung
  {
    id: "ausbreitungseinheit",
    group: "Samen/Ausbreitung",
    name: "Ausbreitungseinheit",
    possibleValues: [
      "flugschirm",
      "fluegel",
      "haken",
      "klettfrucht",
      "schwimmfaehig",
      "fleischige_frucht",
      "trockene_frucht",
      "springfrucht",
      "samen_nackt_sichtbar",
      "nicht_sichtbar",
    ],
    diagnosticWeight: "niedrig",
    photoVisibility: "bedingt",
    requiredPhotoTypes: ["frucht", "detail"],
    userExplanation:
      "Beschreibt sichtbare Strukturen, die der Ausbreitung von Samen oder Früchten dienen, zum Beispiel Flugschirm, Flügel, Haken oder fleischige Früchte. Dieses Merkmal ist oft nicht sichtbar und wird deshalb niedrig gewichtet.",
  },

  // Gruppe 14: Unterirdische Organe
  {
    id: "unterirdisches_organ",
    group: "Unterirdische Organe",
    name: "Unterirdisches Organ",
    possibleValues: [
      "pfahlwurzel",
      "faserwurzel",
      "rhizom",
      "knolle",
      "zwiebel",
      "sprossknolle",
      "wurzelknolle",
      "auslaeufer",
      "stolon",
      "nicht_sichtbar",
    ],
    diagnosticWeight: "hoch",
    photoVisibility: "false",
    requiredPhotoTypes: ["detail"],
    userExplanation:
      "Beschreibt unterirdische Überdauerungs- oder Speicherorgane wie Rhizom, Knolle, Zwiebel oder Ausläufer. Dieses Merkmal ist diagnostisch wichtig, aber auf normalen Fotos meist nicht sichtbar.",
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
