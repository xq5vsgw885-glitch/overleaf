import pathlib
import re


ROOT = pathlib.Path(__file__).resolve().parents[1]
INDEX_HTML = ROOT / "index.html"


def _index_html() -> str:
    return INDEX_HTML.read_text(encoding="utf-8")


def _function_body(name: str, html: str) -> str:
    match = re.search(rf"function\s+{re.escape(name)}\s*\([^)]*\)\s*\{{", html)
    assert match, f"{name}() not found"

    start = match.end()
    depth = 1
    i = start
    while i < len(html) and depth:
        if html[i] == "{":
            depth += 1
        elif html[i] == "}":
            depth -= 1
        i += 1
    assert depth == 0, f"{name}() body is not balanced"
    return html[start : i - 1]


def test_frontend_exposes_required_workflow_anchors_and_state():
    html = _index_html()

    for anchor_id in ["step-upload", "step-analysis", "step-preview", "step-quality"]:
        assert f'id="{anchor_id}"' in html

    assert "const appState={analysis:null,selectedBlocks:[],generatedProtocol:null,qualityReport:null}" in html

    for function_name in [
        "analyzeData",
        "renderAnalysis",
        "renderWarnings",
        "renderSelectableBlocks",
        "getSelectedBlocks",
    ]:
        assert re.search(rf"function\s+{function_name}\s*\(", html)


def test_frontend_experiment_type_selection_and_hints_are_ui_only():
    html = _index_html()
    type_body = _function_body("experimentType", html)
    render_hint = _function_body("renderExperimentHint", html)
    on_versuch = _function_body("onVersuch", html)
    hints_literal = next(line for line in html.splitlines() if line.startswith("const EXPERIMENT_HINTS="))

    for value, label in [
        ("general", "Allgemeines Physikprotokoll"),
        ("rubensrohr", "Rubensrohr"),
        ("ohmsches_gesetz", "Ohmsches Gesetz"),
        ("schwingungsversuch", "Schwingungsversuch"),
        ("optikversuch", "Optikversuch"),
        ("elektrischer_versuch", "Elektrischer Versuch"),
        ("custom", "Freier Versuch"),
    ]:
        assert f'value="{value}"' in html
        assert label in html

    for phrase in [
        "Wellenlänge, Frequenz, Schallgeschwindigkeit",
        "U-I-Diagramm, lineare Regression",
        "Periodendauer, Frequenz, Dämpfung und Resonanz",
    ]:
        assert phrase in hints_literal

    for digit in "0123456789":
        assert digit not in hints_literal

    assert "get('v-select')" in type_body
    assert "renderExperimentHint()" in on_versuch
    assert "experiment-hint" in render_hint
    assert "textContent=experimentHintText()" in render_hint


def test_frontend_prefers_preview_blocks_and_keeps_fallback_sections():
    html = _index_html()
    analysis_blocks = _function_body("analysisBlocks", html)
    fallback = _function_body("fallbackBlocksFromAnalysis", html)

    assert "analysis?.preview_blocks" in analysis_blocks
    assert "fallbackBlocksFromAnalysis(analysis)" in analysis_blocks

    for source_array in ["tables", "figures", "results", "calculations", "warnings"]:
        assert source_array in fallback

    for section in ["Tabellen", "Abbildungen", "Messergebnisse", "Rechnungen", "Warnungen"]:
        assert section in fallback


def test_frontend_sends_raw_data_only_to_analyze_endpoint():
    html = _index_html()
    analyze_body = _function_body("analyzeData", html)
    generate_body = _function_body("generate", html)
    build_payload_body = _function_body("buildGenerationPayload", html)

    assert "/api/analyze" in analyze_body
    assert "csv:raw" in analyze_body
    assert "filename:f.name" in analyze_body
    assert "experiment_type:experimentType()" in analyze_body
    assert "metadata:metadata()" in analyze_body
    assert "experimentHintText" not in analyze_body

    assert "/api/generate" in generate_body
    assert "body:JSON.stringify(payload)" in generate_body
    assert "model:'claude-sonnet-4-5'" not in generate_body
    assert "max_tokens:12000" not in generate_body
    assert "messages:" not in generate_body
    assert "system:" not in generate_body
    assert "csv:raw" not in generate_body
    assert "readTextFile" not in generate_body
    assert "renderProtocolPreview(appState.generatedProtocol)" in generate_body

    assert "getSelectedBlocks()" in build_payload_body
    assert "selected_analysis_blocks:selectedBlocks" in build_payload_body
    assert "summary_for_generation:" in build_payload_body
    assert "experiment_type:experimentType()" in build_payload_body
    assert "experimentHintText" not in build_payload_body
    assert "EXPERIMENT_HINTS" not in build_payload_body
    assert "no_invented_measurements:true" in build_payload_body
    assert "missing_values_as_todo:true" in build_payload_body
    assert "non_computable_results_as_not_computable:true" in build_payload_body
    assert "hide_internal_provenance_in_visible_text:true" in build_payload_body
    for forbidden_key in ["raw_csv", "rawtxt", "rawtext", "rawcsv", "file_content", "filecontent", "complete_raw_data", "get('v-custom')"]:
        assert forbidden_key not in build_payload_body.lower()

    assert "collectEditedBlocks()" in html
    assert "validateProtocol(texContent,bibContent)" in html


def test_frontend_selection_updates_app_state_and_generation_items():
    html = _index_html()
    get_selected = _function_body("getSelectedBlocks", html)
    prepare_generation = _function_body("prepareGeneration", html)
    selected_items = _function_body("selectedItems", html)

    assert "#preview-items input[type=checkbox]:checked" in get_selected
    assert "appState.analysis?.preview_blocks" in get_selected
    assert "checked.includes(i._uid)" in get_selected

    assert "appState.selectedBlocks=getSelectedBlocks()" in prepare_generation
    assert "selectedAnalysisItems=selectedItems()" in prepare_generation
    assert "goStep(4)" in prepare_generation

    assert "appState.selectedBlocks.some" in prepare_generation
    assert "source_file:_file" in selected_items
    assert "description:content?.description" in selected_items
    assert "data:content?.data" in selected_items


def test_frontend_renders_editable_protocol_blocks():
    html = _index_html()
    render_preview = _function_body("renderProtocolPreview", html)
    generate_body = _function_body("generate", html)

    assert 'id="protocol-blocks"' in html
    assert "Array.isArray(protocol?.preview_blocks)" in render_preview
    assert "textToProtocolBlocks(protocol?.tex||texContent)" in render_preview
    assert 'data-field="title"' in render_preview
    assert 'data-field="section"' in render_preview
    assert 'data-field="type"' in render_preview
    assert 'data-field="content"' in render_preview
    assert "Nach oben" in render_preview
    assert "Nach unten" in render_preview
    assert "Entfernen" in render_preview
    assert "renderProtocolPreview(appState.generatedProtocol)" in generate_body


def test_frontend_collects_edited_blocks_for_validation_and_export():
    html = _index_html()
    collect_body = _function_body("collectEditedBlocks", html)
    prepare_export = _function_body("prepareExportState", html)
    safe_download = _function_body("safeDownloadCurrent", html)

    assert "#protocol-blocks .protocol-block" in collect_body
    for field in ["title", "section", "type", "content"]:
        assert f'getField(\'{field}\')' in collect_body
    assert "appState.generatedProtocol" in collect_body
    assert "texContent=protocolBlocksToText(blocks)" in collect_body

    assert "collectEditedBlocks()" in prepare_export
    assert "runQualityCheck()" in prepare_export
    assert "content=texContent" in safe_download
    assert "content=bibContent" in safe_download
    assert "generatedTextFromResponse" not in safe_download
    assert "cleanGeneratedText" not in safe_download


def test_frontend_quality_check_collects_blocks_and_reports_passed_state():
    html = _index_html()
    quality_body = _function_body("runQualityCheck", html)
    validate_body = _function_body("validateProtocol", html)
    render_body = _function_body("renderQualityReport", html)
    generate_body = _function_body("generate", html)

    assert "collectEditedBlocks()" in quality_body
    assert "validateProtocol(texContent,bibContent)" in quality_body
    assert "appState.qualityReport=report" in quality_body
    assert "renderQualityReport(report)" in quality_body

    assert "passed:errors.length===0" in validate_body
    assert "step-quality" in render_body
    assert "Qualitätsprüfung 2.0" in render_body
    assert "runQualityCheck()" in generate_body


def test_frontend_quality_check_flags_todos_internal_terms_and_estimates():
    html = _index_html()
    validate_body = _function_body("validateProtocol", html)

    for term in ["PL\\s+Generator", "Codex", "Claude", "Anthropic", "localhost", "Proxy", "SHA256", "Python-Analyse"]:
        assert term in html

    assert "%TODO" in validate_body
    assert "\\bTODO\\b" in validate_body
    assert "TODO-Platzhalter" in validate_body
    for phrase in ["angenommen", "geschätzt", "typischerweise\\s+beträgt", "plausibler\\s+Wert"]:
        assert phrase in validate_body
    assert "Problematische Schätzformulierung" in validate_body


def test_frontend_quality_check_blocks_bibliography_and_literal_keys():
    html = _index_html()
    validate_body = _function_body("validateProtocol", html)

    assert "\\\\printbibliography fehlt" in validate_body
    assert "\\\\printbibliography steht nicht direkt vor" in validate_body
    assert "\\\\end\\{document\\}" in validate_body
    assert "Literal-Citation-Key" in validate_body
    assert "Zitierter Key fehlt in literatur.bib" in validate_body
    assert "papula2018" in html


def test_frontend_protocol_preview_is_blockwise_editable():
    html = _index_html()
    render_preview = _function_body("renderProtocolPreview", html)
    collect_edited = _function_body("collectEditedBlocks", html)
    move_block = _function_body("moveProtocolBlock", html)
    remove_block = _function_body("removeProtocolBlock", html)

    assert "preview_blocks" in render_preview
    assert "protocol-blocks" in render_preview
    assert "Nach oben" in render_preview
    assert "Nach unten" in render_preview
    assert "Entfernen" in render_preview
    assert "data-field=\"content\"" in render_preview
    assert "textToProtocolBlocks" in render_preview or "normalizeProtocolBlock" in render_preview
    assert "renderProtocolPreview" in move_block
    assert "preview_blocks:blocks" in move_block
    assert "renderProtocolPreview" in remove_block
    assert "preview_blocks:blocks" in remove_block

    assert "querySelectorAll('#protocol-blocks .protocol-block')" in collect_edited
    assert "protocolBlocksToText(blocks)" in collect_edited
    assert "appState.generatedProtocol" in collect_edited
    assert "tex-preview" in collect_edited


def test_frontend_quality_check_v2_reports_passed_errors_and_warnings():
    html = _index_html()
    run_quality = _function_body("runQualityCheck", html)
    validate_body = _function_body("validateProtocol", html)
    render_quality = _function_body("renderQualityReport", html)

    assert "collectEditedBlocks()" in run_quality
    assert "validateProtocol(texContent,bibContent)" in run_quality
    assert "appState.qualityReport" in run_quality

    assert "passed:errors.length===0" in validate_body
    assert "\\printbibliography" in validate_body
    assert "\\end{document}" in validate_body
    assert "Literal-Citation-Key im sichtbaren Text gefunden." in validate_body
    assert "%TODO" in validate_body
    assert "typischerweise" in validate_body
    assert "plausibler" in validate_body

    for term in ["PL\\s+Generator", "Codex", "Claude", "Anthropic", "localhost", "Proxy", "SHA256", "Python-Analyse"]:
        assert term in html

    assert "step-quality" in render_quality
    assert "Qualitätsprüfung 2.0" in render_quality
    assert "passed" in render_quality


def test_frontend_export_wrappers_use_edited_preview_and_block_on_errors():
    html = _index_html()
    safe_download = _function_body("safeDownloadCurrent", html)
    copy_tex = _function_body("copyTexCurrent", html)
    push_git = _function_body("pushGitHubCurrent", html)

    for body in [safe_download, copy_tex, push_git]:
        assert "prepareExportState()" in body
        assert "collectEditedBlocks()" not in body or "prepareExportState()" in body
        assert "runQualityCheck()" not in body or "prepareExportState()" in body

    assert "if(report.errors.length)" in safe_download
    assert "if(report.errors.length)" in copy_tex
    assert "if(report.errors.length)" in push_git
    assert "texContent" in safe_download
    assert "texContent" in copy_tex
    assert "texContent" in push_git
    assert "generatedTextFromResponse" not in safe_download
    assert "generatedTextFromResponse" not in copy_tex
    assert "generatedTextFromResponse" not in push_git
    assert "cleanGeneratedText" not in safe_download
    assert "cleanGeneratedText" not in copy_tex
    assert "cleanGeneratedText" not in push_git


def test_frontend_export_v2_uses_edited_blocks_for_all_actions():
    html = _index_html()
    collect_body = _function_body("collectEditedBlocks", html)
    quality_body = _function_body("runQualityCheck", html)
    export_state = _function_body("prepareExportState", html)
    safe_download = _function_body("safeDownloadCurrent", html)
    copy_body = _function_body("copyTexCurrent", html)
    push_body = _function_body("pushGitHubCurrent", html)

    assert "texContent=protocolBlocksToText(blocks)" in collect_body
    assert "collectEditedBlocks()" in quality_body
    assert "renderQualityReport(report)" in quality_body
    assert "collectEditedBlocks()" in export_state
    assert "runQualityCheck()" in export_state

    assert safe_download.index("prepareExportState()") < safe_download.index("new Blob")
    assert "content=texContent" in safe_download
    assert "content=bibContent" in safe_download
    assert copy_body.index("prepareExportState()") < copy_body.index("navigator.clipboard.writeText(texContent)")
    assert push_body.index("prepareExportState()") < push_body.index("pushFiles=")


def test_frontend_export_v2_blocks_errors_but_allows_warnings():
    html = _index_html()
    validate_body = _function_body("validateProtocol", html)
    render_quality = _function_body("renderQualityReport", html)
    safe_download = _function_body("safeDownloadCurrent", html)
    copy_body = _function_body("copyTexCurrent", html)
    push_body = _function_body("pushGitHubCurrent", html)

    assert "passed:errors.length===0" in validate_body
    assert "TODO-Platzhalter" in validate_body
    assert "warnings.push" in validate_body
    assert "Problematische Schätzformulierung" in validate_body

    assert "Warnungen" in render_quality
    assert "box info" in render_quality
    assert "if(report.errors.length)" in safe_download
    assert "if(report.errors.length)" in copy_body
    assert "if(report.errors.length)" in push_body
