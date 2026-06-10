"""
astro_spectra agent handler.
"""

from __future__ import annotations

import os
import json
import numpy as np
from typing import Optional
from astropy.io import fits
from dotenv import load_dotenv

load_dotenv()

from blocks_network import StartTaskMessage, TaskContext


def handler(task: StartTaskMessage, ctx: Optional[TaskContext] = None) -> dict:
    """Handle an incoming task.

    Parameters
    ----------
    task : StartTaskMessage
        The incoming task message with request_parts.
    ctx : TaskContext, optional
        Task context for status reporting.

    Returns
    -------
    dict
        Result with "artifacts" key containing a list of {data, mimeType} entries.
    """
    if ctx is not None:
        ctx.report_status("Starting spectral analysis...")

    # 1. Extract inputs from request parts
    fits_bytes = None
    parameters_text = None

    for part in task.request_parts:
        if part.part_id == "fits_file":
            if hasattr(part, "data") and getattr(part, "data") is not None:
                fits_bytes = part.data
            elif getattr(part, "artifact_ref", None) is not None:
                if ctx is not None:
                    fits_bytes = ctx.download_input_artifact(part)
                else:
                    # Ephemeral fallback for offline tests with inline data
                    import base64
                    ref = part.artifact_ref
                    kind = getattr(ref, "kind", None) or (ref.get("kind") if isinstance(ref, dict) else None)
                    if kind == "inline":
                        data_b64 = getattr(ref, "data", None) or (ref.get("data") if isinstance(ref, dict) else None)
                        if data_b64:
                            fits_bytes = base64.b64decode(data_b64)
                    if fits_bytes is None:
                        raise ValueError("Cannot download file-based artifact without TaskContext (ctx).")
            elif hasattr(part, "extra") and "data" in part.extra:
                fits_bytes = part.extra["data"]
        elif part.part_id == "parameters":
            parameters_text = part.text

    if fits_bytes is None:
        raise ValueError('Missing required file part "fits_file"')

    # Parse parameters
    polynomial_order = 5
    mask_regions_str = ""
    if parameters_text:
        try:
            params = json.loads(parameters_text)
            polynomial_order = int(params.get("polynomial_order", 5))
            mask_regions_str = str(params.get("mask_regions", ""))
        except Exception as e:
            if ctx is not None:
                ctx.report_status(f"Warning: Failed to parse parameters, using defaults. Error: {e}")

    # 2. Write bytes to a temporary file inside the workspace for Astropy to read
    temp_filename = "temp_spectrum_input.fits"
    with open(temp_filename, "wb") as f:
        f.write(fits_bytes)

    wavelength = None
    flux = None
    units_wavelength = "Unknown"
    units_flux = "Unknown"
    meta = {}

    # 3. Adaptive Auto-Parser
    try:
        if ctx is not None:
            ctx.report_status("Parsing FITS headers and columns...")

        with fits.open(temp_filename) as hdul:
            # Extract observation metadata from primary header if available
            if len(hdul) > 0 and hdul[0].header is not None:
                for key in ["TELESCOP", "INSTRUME", "TARGNAME", "OBJECT", "DATE-OBS", "EXPTIME", "DEC", "RA"]:
                    if key in hdul[0].header:
                        meta[key.lower()] = str(hdul[0].header[key])

            # Case A: Binary Table HDU (SDSS, JWST, HST data tables)
            for hdu in hdul:
                if hdu.data is not None and hasattr(hdu.data, "names"):
                    names_lower = [n.lower() for n in hdu.data.names]
                    
                    # Search for flux column
                    flux_col = None
                    for possible_flux in ["flux", "flux_density", "flux_calib", "spec", "spectrum", "data"]:
                        if possible_flux in names_lower:
                            flux_col = hdu.data.names[names_lower.index(possible_flux)]
                            break
                    
                    # Search for wavelength column
                    wave_col = None
                    for possible_wave in ["wave", "wavelength", "wavelength_calib", "loglam", "wavel", "coord"]:
                        if possible_wave in names_lower:
                            wave_col = hdu.data.names[names_lower.index(possible_wave)]
                            break
                    
                    if flux_col and wave_col:
                        flux_data = hdu.data[flux_col]
                        wave_data = hdu.data[wave_col]
                        
                        # Flatten to 1D if multidimensional (e.g. HST multi-segment or multi-order spectra)
                        if len(wave_data.shape) > 1:
                            wave_data = wave_data.ravel()
                            flux_data = flux_data.ravel()
                            
                        # Handle loglam encoding (SDSS uses log10 of wavelength in Angstroms)
                        if "loglam" in wave_col.lower():
                            wave_data = 10 ** wave_data
                            
                        # Sort arrays by wavelength to ensure a continuous ordered spectrum
                        sort_idx = np.argsort(wave_data)
                        wave_data = wave_data[sort_idx]
                        flux_data = flux_data[sort_idx]
                        
                        wavelength = wave_data.tolist()
                        flux = flux_data.tolist()
                        
                        # Get units if available
                        if hasattr(hdu, "columns"):
                            try:
                                units_flux = hdu.columns[flux_col].unit or "Unknown"
                                units_wavelength = hdu.columns[wave_col].unit or "Unknown"
                            except Exception:
                                pass
                        break

            # Case B: 1D Image HDU (Simple FITS spectra, e.g. IRAF format)
            if flux is None:
                primary_hdu = hdul[0]
                if primary_hdu.data is not None and len(primary_hdu.data.shape) in [1, 2]:
                    data = primary_hdu.data
                    if len(data.shape) == 2:
                        data = data.squeeze()
                    flux = data.tolist()
                    
                    # Read coordinate keywords
                    hdr = primary_hdu.header
                    crval = hdr.get("CRVAL1")
                    cdelt = hdr.get("CDELT1") or hdr.get("CD1_1")
                    crpix = hdr.get("CRPIX1", 1)
                    naxis1 = hdr.get("NAXIS1")
                    units_wavelength = hdr.get("CUNIT1", "Angstrom")
                    units_flux = hdr.get("BUNIT", "Unknown")
                    
                    if crval is not None and cdelt is not None and naxis1 is not None:
                        pixels = np.arange(1, naxis1 + 1)
                        dc_flag = hdr.get("DC-FLAG", 0)
                        if dc_flag == 1 or hdr.get("WFITTYPE") == "log-linear":
                            wavelength = (10 ** (crval + cdelt * (pixels - crpix))).tolist()
                        else:
                            wavelength = (crval + cdelt * (pixels - crpix)).tolist()

    finally:
        # Clean up the temp file immediately
        if os.path.exists(temp_filename):
            os.remove(temp_filename)

    if flux is None or wavelength is None:
        raise ValueError("Failed to auto-parse spectral columns. File structure not recognized.")

    # 4. Continuum Reflection Loop
    if ctx is not None:
        ctx.report_status("Executing Continuum Reflection Loop...")

    x = np.array(wavelength)
    y = np.array(flux)

    # Filter NaNs
    valid = np.isfinite(x) & np.isfinite(y)
    x_clean = x[valid]
    y_clean = y[valid]

    # Apply manual mask regions if provided
    mask = np.ones_like(x_clean, dtype=bool)
    if mask_regions_str.strip():
        for region in mask_regions_str.split(","):
            try:
                low, high = map(float, region.strip().split("-"))
                mask = mask & ~((x_clean >= low) & (x_clean <= high))
            except Exception:
                pass

    fit_mask = mask.copy()
    prev_coeffs = None
    continuum_clean = np.ones_like(x_clean)

    # Iterative reflection fitting
    for iteration in range(10):
        if np.sum(fit_mask) < polynomial_order + 2:
            break
        
        # Fit polynomial to currently unmasked regions
        coeffs = np.polyfit(x_clean[fit_mask], y_clean[fit_mask], polynomial_order)
        poly = np.poly1d(coeffs)
        
        # Calculate continuum over all clean points
        continuum_clean = poly(x_clean)
        residuals = y_clean - continuum_clean
        std = np.std(residuals[fit_mask])
        
        if std == 0:
            break
            
        # Refine mask: exclude peaks/absorption lines (> 2.5 sigma)
        new_fit_mask = fit_mask & (np.abs(residuals) < 2.5 * std)
        
        if prev_coeffs is not None and np.allclose(coeffs, prev_coeffs, rtol=1e-4):
            break
        prev_coeffs = coeffs
        fit_mask = new_fit_mask

    # Re-insert NaN points for returning aligned arrays
    final_continuum = np.zeros_like(x)
    final_continuum[valid] = continuum_clean
    final_normalized = np.zeros_like(x)
    final_normalized[valid] = y_clean / continuum_clean

    # 5. Peak/Line Detection
    residuals_clean = y_clean - continuum_clean
    std_clean = np.std(residuals_clean[fit_mask])
    
    detected_lines = []
    if std_clean > 0:
        # Outliers threshold at 3 sigma
        outliers = np.where(np.abs(residuals_clean) > 3.0 * std_clean)[0]
        if len(outliers) > 0:
            groups = []
            current_group = [outliers[0]]
            for idx in outliers[1:]:
                if idx == current_group[-1] + 1:
                    current_group.append(idx)
                else:
                    groups.append(current_group)
                    current_group = [idx]
            groups.append(current_group)
            
            for g in groups:
                peak_idx = g[np.argmax(np.abs(residuals_clean[g]))]
                wavelength_peak = x_clean[peak_idx]
                line_type = "emission" if residuals_clean[peak_idx] > 0 else "absorption"
                significance = float(abs(residuals_clean[peak_idx] / std_clean))
                detected_lines.append({
                    "wavelength": float(wavelength_peak),
                    "type": line_type,
                    "significance": significance
                })

    # 6. AI Agent Reasoning (OpenRouter API Integration)
    ai_report = None
    used_model = None
    openrouter_api_key = os.environ.get("OPENROUTER_API_KEY")
    if openrouter_api_key:
        try:
            if ctx is not None:
                ctx.report_status("Performing AI spectral classification and element mapping via OpenRouter...")

            from openai import OpenAI
            client = OpenAI(
                api_key=openrouter_api_key,
                base_url="https://openrouter.ai/api/v1",
            )

            # Build LLM prompt
            prompt_lines = []
            prompt_lines.append("You are an expert astrophysicist and spectral analyst.")
            prompt_lines.append("Analyze the following detected spectral lines and metadata to classify the astronomical object, match the lines to chemical elements, and estimate the redshift (z) and radial velocity.")
            prompt_lines.append("")
            prompt_lines.append("Observation Metadata:")
            for k, v in meta.items():
                prompt_lines.append(f"  - {k.upper()}: {v}")
            prompt_lines.append(f"  - Wavelength Units: {units_wavelength}")
            prompt_lines.append(f"  - Flux Units: {units_flux}")
            prompt_lines.append("")
            prompt_lines.append("Detected Line Peaks (Observed wavelengths):")
            for idx, line in enumerate(detected_lines):
                prompt_lines.append(f"  - Line {idx+1}: Wavelength={line['wavelength']:.2f}, Type={line['type']}, Significance={line['significance']:.2f} sigma")
            prompt_lines.append("")
            prompt_lines.append("Instructions:")
            prompt_lines.append("1. Match the detected observed wavelengths against known rest transitions (e.g. H-alpha [6563 Å], H-beta [4861 Å], [O III] [5007 Å], He II [4686 Å], Ca H [3968 Å], Ca K [3934 Å], Lyman-alpha [1216 Å], etc.).")
            prompt_lines.append("2. Compute the estimated redshift z = (observed_wavelength / rest_wavelength) - 1. If the target is a star in our galaxy, z should be near 0.0.")
            prompt_lines.append("3. Return a valid JSON object matching the schema below. Do not output any thinking or markdown code blocks outside of the JSON.")
            prompt_lines.append("")
            prompt_lines.append("Expected JSON Schema:")
            prompt_lines.append("{")
            prompt_lines.append('  "object_classification": "Astronomical classification (e.g. White Dwarf, Quasar, Star, Galaxy)",')
            prompt_lines.append('  "estimated_redshift": 0.0023,')
            prompt_lines.append('  "radial_velocity_km_s": 690.0,')
            prompt_lines.append('  "elements_detected": [')
            prompt_lines.append("    {")
            prompt_lines.append('      "element_name": "Element name (e.g. H-alpha)",')
            prompt_lines.append('      "rest_wavelength": 6563.0,')
            prompt_lines.append('      "observed_wavelength": 6578.0,')
            prompt_lines.append('      "confidence": 0.95')
            prompt_lines.append("    }")
            prompt_lines.append("  ],")
            prompt_lines.append('  "summary": "Narrative analysis of the spectrum."')
            prompt_lines.append("}")

            models_to_try = [
                os.environ.get("OPENROUTER_MODEL", "openai/gpt-oss-20b:free"),
                "google/gemma-4-31b-it:free",
                "meta-llama/llama-3.3-70b-instruct:free"
            ]

            # Remove duplicates while preserving order
            seen = set()
            unique_models = [m for m in models_to_try if not (m in seen or seen.add(m))]

            response_text = None
            last_err = None
            prompt_content = "\n".join(prompt_lines)

            for m_name in unique_models:
                try:
                    if ctx is not None:
                        ctx.report_status(f"Trying model: {m_name}...")
                    else:
                        print(f"Trying model: {m_name}...")

                    response = client.chat.completions.create(
                        model=m_name,
                        messages=[
                            {
                                "role": "system",
                                "content": "You are a professional astrophysicist that only outputs valid JSON matching the requested schema."
                            },
                            {
                                "role": "user",
                                "content": prompt_content
                            }
                        ],
                        response_format={"type": "json_object"}
                    )
                    response_text = response.choices[0].message.content
                    used_model = m_name
                    break  # Success!
                except Exception as e:
                    last_err = e
                    if ctx is not None:
                        ctx.report_status(f"Model {m_name} rate-limited/failed. Trying fallback...")
                    else:
                        print(f"Model {m_name} failed: {e}")

            if not response_text:
                raise last_err if last_err else RuntimeError("All models failed to return content.")

            # Clean response text in case markdown tags were wrapped
            response_text_clean = response_text.strip()
            if response_text_clean.startswith("```json"):
                response_text_clean = response_text_clean[7:]
            if response_text_clean.endswith("```"):
                response_text_clean = response_text_clean[:-3]
            response_text_clean = response_text_clean.strip()

            # Parse
            ai_report = json.loads(response_text_clean)
        except Exception as e:
            print(f"Warning: OpenRouter AI analysis failed: {e}")
            if ctx is not None:
                ctx.report_status(f"Warning: AI analysis failed: {e}")

    # 7. Compile Markdown Report
    report_lines = []
    report_lines.append("# Astro-Spectra Physical Analysis Report")
    report_lines.append("")
    report_lines.append("## Observation Metadata")
    report_lines.append("| Parameter | Value |")
    report_lines.append("| :--- | :--- |")
    for k, v in meta.items():
        report_lines.append(f"| {k.upper()} | {v} |")
    report_lines.append(f"| WAVELENGTH UNITS | {units_wavelength} |")
    report_lines.append(f"| FLUX UNITS | {units_flux} |")
    report_lines.append("")

    if ai_report:
        report_lines.append("## AI Astrophysical Classification")
        report_lines.append(f"**Object Classification:** {ai_report.get('object_classification', 'Unknown')}")
        if used_model:
            report_lines.append(f"**Model Used:** `{used_model}`")
        report_lines.append("")
        report_lines.append("### Velocity & Redshift Metrics")
        report_lines.append(f"* **Estimated Redshift (z):** `{ai_report.get('estimated_redshift', 0.0):.6f}`")
        report_lines.append(f"* **Radial Velocity:** `{ai_report.get('radial_velocity_km_s', 0.0):.2f} km/s` (z * c)")
        report_lines.append("")
        report_lines.append("## Chemical Element Mapping")
        report_lines.append("| Identified Element/Ion | Rest Wavelength | Observed Wavelength | Match Confidence |")
        report_lines.append("| :--- | :---: | :---: | :---: |")
        for el in ai_report.get("elements_detected", []):
            conf = el.get("confidence", 1.0)
            conf_str = f"{conf:.1%}" if isinstance(conf, (int, float)) else str(conf)
            report_lines.append(f"| {el.get('element_name')} | {el.get('rest_wavelength')} Å | {el.get('observed_wavelength')} Å | {conf_str} |")
        report_lines.append("")
        report_lines.append("## Scientific Narrative Summary")
        report_lines.append(ai_report.get("summary", "No summary provided."))
    else:
        report_lines.append("## Line Features (Numerical Extraction)")
        report_lines.append("AI analysis was skipped or failed. Below are the line centroids detected by the baseline fitting loop:")
        report_lines.append("")
        report_lines.append("| Wavelength | Feature Type | Peak Significance |")
        report_lines.append("| :---: | :---: | :---: |")
        for line in detected_lines:
            report_lines.append(f"| {line['wavelength']:.2f} Å | {line['type']} | {line['significance']:.2f}σ |")
        report_lines.append("")
        report_lines.append("> [!WARNING]")
        report_lines.append("> AI reasoning was not executed. Make sure `OPENROUTER_API_KEY` is set in the environment variables.")

    markdown_report = "\n".join(report_lines)

    # Prepare response payload
    result = {
        "wavelength": x.tolist(),
        "flux": y.tolist(),
        "continuum": final_continuum.tolist(),
        "normalized_flux": final_normalized.tolist(),
        "units_wavelength": str(units_wavelength),
        "units_flux": str(units_flux),
        "detected_lines": detected_lines,
        "ai_analysis": ai_report
    }

    if ctx is not None:
        ctx.report_status("Spectral analysis complete!")

    # Return dual output artifacts
    return {
        "artifacts": [
            {
                "data": json.dumps(result, indent=2),
                "mimeType": "application/json",
                "fileName": "spectrum-data.json"
            },
            {
                "data": markdown_report,
                "mimeType": "text/markdown",
                "fileName": "physical-analysis-report.md"
            }
        ]
    }
