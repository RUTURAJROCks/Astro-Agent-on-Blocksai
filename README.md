# Astro-Spectra Agent on Blocks.ai

Astro-Spectra is a hybrid numerical-AI agent deployed on the Blocks.ai network. It automates the extraction, baseline normalization, spectral feature mapping, and physical profiling of raw 1D astronomical spectra (such as those from Hubble, JWST, or SDSS). 

By combining local scientific computation (NumPy and Astropy) with LLM reasoning (OpenRouter), the agent bridges the gap between raw data and physical interpretation, outputting both structured JSON data and formatted markdown reports.

---

## Scientific Processing Pipeline (For Astronomers)

Spectroscopic data reduction involves repetitive script writing to handle varying telescope schemas, flat-field baselines, and line identifications. Astro-Spectra automates these tasks in three distinct phases:

### 1. Adaptive FITS Auto-Parsing
Observational data packages spectra in different formats depending on the instrument (e.g., binary tables for JWST/COS, or 1D/2D image arrays for older spectrographs). This parser:
* Dynamically scans FITS headers and extension structures.
* Maps coordinate/wavelength and flux headers automatically, resolving discrepancies (such as `flux`, `FLUX`, `wavelength`, `WAVE`, `loglam`).
* Flattens multi-dimensional segment data (common in multi-order echelle spectra) into a single, sorted 1D array.
* Standardizes units to ensure physical compatibility during downstream analysis.

### 2. Continuum Reflection Loop
Fitting a flat-field baseline polynomial to a spectrum is often distorted by strong emission or absorption lines. To address this, the agent runs an iterative sigma-clipping fitting loop:
* Fits a polynomial of degree $N$ (user-customizable) to the raw spectrum.
* Computes the residuals between the raw flux and the baseline.
* Identifies line features (outliers) exceeding a $2.5\sigma$ threshold.
* Automatically masks out these lines and re-fits the polynomial to the remaining continuum points.
* Iterates until the baseline converges, then divides the raw flux by the fitted continuum to return a normalized spectrum.

### 3. Astro-Physical Profiling
Once line centroids are numerically extracted, the agent uses AI reasoning to translate these coordinates into physical properties:
* Maps observed line wavelengths to standard rest-frame transitions (such as Hydrogen Balmer H-alpha/H-beta, Helium He II, Magnesium Mg II, Iron multiplets, and Calcium H&K).
* Calculates the cosmological redshift ($z = (\lambda_{\text{obs}} / \lambda_{\text{rest}}) - 1$) and radial velocity ($v = z \cdot c$, where $c$ is the speed of light).
* Generates an observation summary that classifies the object (e.g., White Dwarf, Quasar, Star, Galaxy) and describes the physical state of the source.

---

## Technical Architecture (For Developers)

The agent is designed to run efficiently on the Blocks.ai runtime, emphasizing tight token management and resilience:

### 1. Hybrid Numerical-AI Execution
Instead of passing raw, multi-megabyte spectral data arrays (which contain thousands of floating-point values) to the LLM—which would result in high latency, extreme token costs, and context window limits—the agent processes the data locally in native Python. Only the extracted observation metadata (telescope, instrument, target) and the small table of detected line centroids (typically 2 to 10 coordinates) are sent to the LLM. This keeps the prompt payload under 300 tokens, maximizing efficiency and minimizing costs.

### 2. Resilient API Failover Chain
To handle transient rate limits or spend limits on free OpenRouter API endpoints, the agent implements a self-correcting model chain. If the preferred model fails to respond, it automatically tries fallback models in sequence:
1. `openai/gpt-oss-20b:free` (Primary default for speed and stability)
2. `google/gemma-4-31b-it:free`
3. `meta-llama/llama-3.3-70b-instruct:free`

### 3. Dual-Artifact Output System
Upon execution, the handler returns two distinct output files:
* `spectrum-data.json` (application/json): Programmatic output containing the raw wavelength, flux, continuum, and normalized arrays, plus the raw AI analysis JSON block, suitable for ingestion by external pipelines.
* `physical-analysis-report.md` (text/markdown): Human-readable report containing a metrics card, a formatted element mapping table, and the narrative summary, which renders as a visual tab on the Blocks dashboard.

---

## Repository Structure

* `handler.py`: Core agent execution handler including FITS parsing, baseline fitting, line detection, and OpenRouter API logic.
* `agent-card.json`: Blocks.ai agent configuration, tags, and input/output JSON schemas.
* `DOCS.md`: Developer integration documentation and Python SDK example.
* `pyproject.toml`: Declared package dependencies (Astropy, NumPy, SciPy, Specutils, OpenAI, HTTPX).
* `test_local.py`: Local integration test script using mock task data.
* `trigger.py`: Programmatic task creation trigger.
* `inspect_fits.py`: Helper utility to inspect FITS file structures.
* `.gitignore`: Git ignore configuration (ignoring `.env` and `__pycache__`).

---

## Installation and Quickstart

### Prerequisites
Ensure you have Python 3.12+ and the global `blocks` CLI installed.

### Setup
1. Clone the repository.
2. Install dependencies in your virtual environment:
   ```bash
   uv pip install -e .
   ```
3. Set your API credentials in a local `.env` file in the root of the project:
   ```bash
   BLOCKS_API_KEY=your_blocks_api_key
   OPENROUTER_API_KEY=your_openrouter_api_key
   ```

### Running Local Tests
Execute the local integration test script to download a Hubble spectrum of the white dwarf `GD71` from NASA's MAST archive and run the parser, loop, and AI model:
```bash
python test_local.py
```

---

## Effective Usage Guidelines

* **Polynomial Order**: For relatively flat spectra (such as white dwarfs or hot stars), a lower degree polynomial (order 3 to 5) works best. For spectra with complex instrumental tilt, higher orders (6 to 8) may be needed.
* **Manual Masking**: If a spectrum contains extremely wide absorption features (such as Lyman-alpha profiles) that the automated loop fails to mask completely, use the `mask_regions` parameter to define manual wavelength ranges (e.g., `1200-1230`) to exclude.
* **Model Configuration**: You can override the default LLM by setting the `OPENROUTER_MODEL` environment variable to any supported OpenRouter model ID.
