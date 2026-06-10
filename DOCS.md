# Astro-Spectra Agent Documentation

`astro_spectra` is an intelligent AI agent designed to automate the parsing, baseline fitting, line detection, and physical analysis of astronomical spectra. It combines fast local numerical computation (numpy/astropy) with deep AI reasoning (OpenRouter) to provide both raw spectral data and a formatted astrophysical report.

---

## How It Works

1. **Adaptive Auto-Parser**:
   * Inspects the FITS file's extensions (HDUs).
   * Automatically identifies columns corresponding to wavelength/coordinate axes and flux arrays, handling variations in casing and name formats (e.g. `flux`, `FLUX`, `wavelength`, `WAVE`, `loglam`).
   * Extracts unit definitions and flattens multi-dimensional segment data into a sorted 1D array.

2. **Continuum Reflection Loop**:
   * Fits an initial $N$-th order Chebyshev/standard polynomial to the raw spectrum.
   * Calculates the standard deviation of the residuals.
   * Identifies and masks outlier peaks that lie above a threshold (default 2.5$\sigma$ or below for absorption lines).
   * Re-fits the polynomial to the remaining data iteratively until the baseline converges.
   * Divides the original spectrum by the final fitted continuum to return a normalized spectrum.

3. **AI Astrophysical Reasoning (OpenRouter)**:
   * Extracts telescope metadata (target name, instrument, exposure time) from the FITS file.
   * Passes the extracted metadata and the list of numerically detected line peaks to OpenRouter (defaulting to `openai/gpt-oss-20b:free` for speed and stability, with automatic self-correcting fallbacks to `google/gemma-4-31b-it:free` and `meta-llama/llama-3.3-70b-instruct:free`).
   * Classifies the object, maps wavelengths to rest chemical transitions (e.g. H-alpha, He II, Mg II, Fe II), estimates cosmological redshift ($z$), calculates radial velocity ($v = z \cdot c$), and generates a narrative summary.

---

## Inputs

* `fits_file` (file part, required): The raw FITS file containing the 1D spectrum.
* `parameters` (json part, required):
  * `polynomial_order` (int, default 5): Degree of the polynomial used for fitting the baseline.
  * `mask_regions` (string, optional): Comma-separated wavelength ranges to manually mask out (e.g., `"6500-6600, 4800-4900"`).

---

## Outputs

The agent returns two distinct output artifacts:

1. **`spectrum-data.json` (`application/json`)**:
   * Contains the complete data arrays (`wavelength`, `flux`, `continuum`, `normalized_flux`), unit strings, the list of numerically detected line peaks, and the raw `ai_analysis` JSON block returned by the LLM.
2. **`physical-analysis-report.md` (`text/markdown`)**:
   * A beautifully formatted Markdown report rendering a metrics card, matched transitions table, and the scientific narrative summary directly in the Blocks.ai dashboard.

---

## Integration Example (Python SDK)

```python
import base64
import json
from blocks_network import SendMessageRequestPart, create_task_client

client = create_task_client()

# Prepare request parts
with open("laad02d9q_x1d.fits", "rb") as f:
    fits_data = f.read()

parameters = {
    "polynomial_order": 5,
    "mask_regions": ""
}

# Send message to the agent
session = client.send_message(
    agent_name="astro_spectra",
    request_parts=[
        SendMessageRequestPart(
            part_id="fits_file",
            data=fits_data,
            mime_type="application/octet-stream"
        ),
        SendMessageRequestPart(
            part_id="parameters",
            text=json.dumps(parameters)
        )
    ]
)

print(f"Task created: {session.task_id}")

# Wait for completion and download artifacts
# ... (standard PubNub task polling / event handling)

# Once finished, you can retrieve both artifacts:
# 1. JSON Data
json_artifact = session.download_artifact(session.artifacts[0])
data = json.loads(json_artifact.data.decode())
print(f"Spectral Points: {len(data['wavelength'])}")

# 2. Markdown Report
md_artifact = session.download_artifact(session.artifacts[1])
print("\n--- Astrophysical Report ---\n")
print(md_artifact.data.decode())
```
