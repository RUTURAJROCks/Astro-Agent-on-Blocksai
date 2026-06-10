# Astro-Spectra Agent on Blocks.ai 🚀

An intelligent AI Agent built on the [Blocks.ai](https://blocks.ai/) platform to automate the ingestion, baseline normalization, spectral line identification, and physical profiling of raw astronomical spectra (such as those from HST, JWST, or SDSS).

---

## 🌟 Key Features

1. **Adaptive Auto-Parser**: 
   * Scans FITS binary extension HDUs.
   * Dynamically maps wavelength/coordinate and flux headers (ignoring variations in telescope casing: `FLUX`, `wavelength`, `WAVE`, `loglam`, etc.).
   * Flattens multidimensional segments (e.g., HST multi-order spectra) and sorts them into a continuous 1D array.

2. **Continuum Reflection Loop**:
   * Numerically fits a baseline polynomial to the raw spectrum.
   * Iteratively masks out absorption/emission line outliers using residual standard deviations until baseline convergence is achieved.
   * Returns a normalized spectrum (dividing raw flux by the fitted baseline).

3. **AI Astrophysical Reasoning (OpenRouter)**:
   * Extracts telescope metadata (target name, instrument, exposure time) from the FITS primary headers.
   * Uses OpenRouter (`openai/gpt-oss-20b:free` as default for speed, with automatic self-correcting fallbacks to `google/gemma-4-31b-it:free` and `meta-llama/llama-3.3-70b-instruct:free` to handle transient rate limits).
   * Identifies chemical elements, estimates cosmological redshift ($z$) and radial velocity, and generates a narrative summary.

4. **Dual Output Artifacts**:
   * **`spectrum-data.json`**: Standard JSON payload containing all the numerical arrays, units, and raw AI JSON response.
   * **`physical-analysis-report.md`**: A beautifully formatted Markdown report rendering a metrics card, matched transitions table, and the scientific narrative summary directly in the Blocks.ai dashboard.

---

## 📂 Repository Structure

* [handler.py](handler.py): The main agent handler containing parsing, baseline fitting, line detection, and OpenRouter AI logic.
* [agent-card.json](agent-card.json): Agent configuration, tag examples, and input/output JSON schemas.
* [DOCS.md](DOCS.md): Detailed integration and developer documentation.
* [pyproject.toml](pyproject.toml): Declared package dependencies (`blocks-network`, `astropy`, `specutils`, `openai`, `httpx`).
* [test_local.py](test_local.py): Local integration test script using mock task data.
* [trigger.py](trigger.py): Programmatic task creation script.
* [inspect_fits.py](inspect_fits.py): Quick helper utility to examine FITS file structures.
* [.gitignore](.gitignore): Git ignore configuration (ignoring `.env` and `__pycache__`).

---

## 🛠️ Local Development & Testing

1. Clone this repository.
2. Install the package dependencies in a Python virtual environment:
   ```bash
   uv pip install -e .
   ```
3. Set your keys in a local `.env` file:
   ```bash
   BLOCKS_API_KEY=your_blocks_key
   OPENROUTER_API_KEY=your_openrouter_key
   ```
4. Run the local integration test:
   ```bash
   python test_local.py
   ```
