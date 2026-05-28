import { ObservedFeature } from "./featureScoring.js";
import { PlantTaxonProfile } from "./taxonProfile.js";
import { ObservationContext } from "./plausibilityScoring.js";
import {
  CombinedAssessmentResult,
  assessTaxonCandidates,
} from "./combinedAssessment.js";
import {
  IdentificationResult,
  buildIdentificationResult,
} from "./identificationResult.js";
import {
  IdentificationResultWithVisualControl,
  createNotPerformedVisualControlResult,
  attachVisualControlResult,
} from "./visualControl.js";

export type IdentificationPipelineInput = {
  observedFeatures: ObservedFeature[];
  observationContext: ObservationContext;
  candidateTaxa: PlantTaxonProfile[];
};

export type IdentificationPipelineResult = {
  assessments: CombinedAssessmentResult[];
  identification: IdentificationResult;
  identificationWithVisualControl: IdentificationResultWithVisualControl;
};

export function runIdentificationPipeline(
  input: IdentificationPipelineInput
): IdentificationPipelineResult {
  const assessments: CombinedAssessmentResult[] = assessTaxonCandidates(
    input.observedFeatures,
    input.observationContext,
    input.candidateTaxa
  );

  const identification: IdentificationResult =
    buildIdentificationResult(assessments);

  const visualControl = createNotPerformedVisualControlResult();

  const identificationWithVisualControl: IdentificationResultWithVisualControl =
    attachVisualControlResult(identification, visualControl);

  return {
    assessments,
    identification,
    identificationWithVisualControl,
  };
}
