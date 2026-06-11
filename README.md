# Astro-Spectra Agent on Blocks.ai

Astro-Spectra is a professional hybrid numerical-AI agent deployed on the Blocks.ai network. It is designed to automate the extraction, baseline normalization, spectral feature mapping, and physical profiling of raw 1D astronomical spectra. The agent supports input spectra from major space- and ground-based observatories, including the Hubble Space Telescope (HST), the James Webb Space Telescope (JWST), and the Sloan Digital Sky Survey (SDSS).

By partitioning the workload between fast, local scientific computation (using NumPy and Astropy) and high-level artificial intelligence reasoning (via OpenRouter), the agent bridges the gap between raw observational data and physical astrophysical interpretation. It outputs both structured data in JSON format and a formatted scientific analysis report in Markdown.

---

## Technical Overview for Developers

The Astro-Spectra agent is designed for high performance, efficiency, and reliability within the serverless environment of the Blocks.ai network.

### 1. Hybrid Numerical-AI Architecture
A major challenge in processing astronomical spectra using large language models is the sheer size of the raw data. A single 1D spectrum can contain tens of thousands of floating-point values representing wavelength and flux. Transmitting this raw array to an LLM would:
* Exceed the model's context window.
* Incur extreme API token costs.
* Introduce significant latency.
* Result in poor performance, as LLMs are not optimized for numerical regression or peak finding.

To solve this, Astro-Spectra implements a hybrid model:
* **Numerical Layer**: Standard FITS parsing, baseline fitting, continuum normalization, and line detection are executed locally in Python. This reduces the raw data to a minimal set of observation metadata and detected line centroids (typically 3 to 10 lines).
* **AI Layer**: The extracted metadata and detected line peaks are packaged into a structured prompt of under 300 tokens. The LLM is used strictly for symbolic reasoning, such as identifying the chemical elements matching the observed line wavelengths, estimating redshift, and compiling a scientific narrative.

### 2. Resilient API Failover Chain
To ensure reliable execution, the agent implements a self-correcting fallback chain when querying OpenRouter. If the preferred model fails or encounters rate limits, the agent automatically falls back to secondary and tertiary models in the following order:
1. **Primary**: `openai/gpt-oss-20b:free` (Configurable via `OPENROUTER_MODEL`, chosen for speed and high availability)
2. **Secondary Fallback**: `google/gemma-4-31b-it:free`
3. **Tertiary Fallback**: `meta-llama/llama-3.3-70b-instruct:free`

### 3. Dual-Artifact Output System
Every execution of the agent generates two distinct outputs to support both programmatic workflows and human review:
1. **`spectrum-data.json`** (`application/json`): A machine-readable payload containing the aligned `wavelength`, `flux`, `continuum`, and `normalized_flux` arrays. It also includes the list of detected line peaks (wavelength, type, significance) and the raw JSON response from the LLM, making it easy to integrate into larger astronomical data pipelines.
2. **`physical-analysis-report.md`** (`text/markdown`): A human-readable scientific report that displays as a tab on the Blocks.ai user interface. It contains a metadata block, a velocity metrics card, a chemical transition table, and an astrophysical summary narrative.

---

## Scientific Processing Pipeline for Astronomers

Astro-Spectra automates the repetitive and manual steps of spectroscopic data reduction and line identification through a three-stage pipeline.

### 1. Adaptive FITS Auto-Parsing
Astronomical datasets from different archives utilize different file formats, structures, and header keywords. The parser dynamically inspects the FITS file extensions to locate the spectral data:
* **Binary Tables**: Used by instruments on JWST, HST (e.g., COS, STIS), and SDSS. The parser searches for known flux and wavelength column names (handling case variations and synonyms like `flux`, `FLUX`, `spec`, `wave`, `wavelength`, `loglam`).
* **1D/2D Image Arrays**: Used by older spectrographs. The parser extracts the start wavelength (`CRVAL1`), dispersion step (`CDELT1` or `CD1_1`), reference pixel (`CRPIX1`), and number of pixels (`NAXIS1`) to reconstruct the linear or log-linear wavelength grid.
* **Data Conditioning**: Multi-dimensional echelle orders or multi-segment data are flattened into a single 1D array. Wavelengths are sorted, and fluxes are aligned. Logarithmic wavelength grids (e.g., from SDSS) are converted back to linear Angstrom scales.

### 2. Continuum Reflection Loop (Sigma-Clipping Fitting)
To normalize the spectrum, the agent must fit a polynomial baseline to the continuum. However, strong emission or absorption lines can distort the fit. To resolve this, Astro-Spectra uses an iterative continuum reflection loop:
* Fits a polynomial of degree $N$ (default is 5) to the spectrum.
* Calculates the residuals ($R = \text{flux} - \text{continuum}$).
* Identifies line features (outliers) that deviate from the continuum by more than $2.5\sigma$.
* Excludes these outlier regions and re-fits the polynomial to the remaining continuum points.
* Iterates up to 10 times or until the polynomial coefficients converge.
* Divides the raw flux by the final continuum fit to produce a normalized spectrum ($F_{\text{norm}} = F / F_{\text{continuum}}$).

### 3. Astrophysical Profiling and Line Mapping
Once the continuum is subtracted, the agent runs a $3.0\sigma$ peak finder to identify the centroids of the remaining emission or absorption lines. These coordinates are passed to the AI layer, which performs the following tasks:
* **Line Identification**: Compares the observed wavelengths with a database of rest-frame transitions, including the Hydrogen Balmer series (H-alpha [6563 Angstroms], H-beta [4861 Angstroms], H-gamma [4340 Angstroms]), forbidden lines (e.g., [O III] [5007 Angstroms]), and stellar absorption lines (e.g., Ca H&K [3968/3934 Angstroms], Mg II [2798 Angstroms], Lyman-alpha [1216 Angstroms]).
* **Redshift and Radial Velocity**: Computes the cosmological redshift:
  $$z = \frac{\lambda_{\text{obs}}}{\lambda_{\text{rest}}} - 1$$
  and the corresponding radial velocity:
  $$v = z \cdot c$$
  where $c$ is the speed of light ($299,792.458$ km/s).
* **Astrophysical Classification**: Summarizes the physical properties of the target and classifies the object (e.g., Main Sequence Star, White Dwarf, Active Galactic Nucleus, Quasar, Starburst Galaxy).

---

## Installation and Setup

### Prerequisites
* Python 3.12 or higher.
* The Blocks CLI tool installed globally.

### Local Installation
1. Clone the repository to your local machine:
   ```bash
   git clone https://github.com/RUTURAJROCks/Astro-Agent-on-Blocksai.git
   cd Astro-Agent-on-Blocksai
   ```
2. Create and activate a virtual environment, then install the package and its dependencies:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -e .
   ```

3. Create a `.env` file in the root of the project directory to store your API credentials:
   ```env
   BLOCKS_API_KEY=your_blocks_api_key
   OPENROUTER_API_KEY=your_openrouter_api_key
   ```

---

## How to Use Effectively

### 1. Input Parameters
The agent accepts a JSON parameters block alongside the FITS file:
* **`polynomial_order`** (Integer, default `5`): The degree of the polynomial used to fit the continuum.
  * For flat spectra with simple shapes (e.g., hot white dwarfs), use a lower order (`3` to `5`).
  * For spectra with complex instrumental response curves or strong tilts, use a higher order (`6` to `8`).
* **`mask_regions`** (String, default `""`): Comma-separated wavelength ranges to exclude from the baseline fitting (e.g., `"1200-1230, 6500-6600"`). Use this if the spectrum contains extremely broad features (like Lyman-alpha absorption wings or broad AGN emission profiles) that the automated sigma-clipping loop might fail to mask completely.

### 2. Testing Locally
You can test the agent locally using the provided `test_local.py` script. This script automatically downloads a real HST/COS spectrum of the white dwarf standard star `GD71` from NASA's MAST archive, runs the FITS parser, fits the continuum, calls the OpenRouter API, and prints the resulting JSON and Markdown outputs:
```bash
python test_local.py
```

### 3. Demo and Pre-populated Cache
A sample calibrated 1D FITS spectrum from the Hubble Space Telescope (`laad02d9q_x1d.fits`) is included in the root of the repository. You can use this file for testing or demo purposes. 

Since the agent implements a file-based result cache (`.astro_cache.json`), submitting this file (with default parameters) will instantly return the cached physical analysis report and JSON output in under 1 second without querying the OpenRouter LLM API. To force a live LLM call and bypass the cache for this file, simply change the `polynomial_order` parameter to a different value (e.g., `4` or `6`) or change the `mask_regions` parameter.

### 4. Deploying to Blocks.ai
To publish the agent to the Blocks.ai network:
1. Verify the project configuration:
   ```bash
   blocks check
   ```
2. Publish the agent:
   ```bash
   blocks publish --billing-mode free --listing public --accept-terms
   ```
3. Start the local listener to route tasks:
   ```bash
   python -m blocks_network
   ```

---

## Repository Contents

* **`handler.py`**: The core execution entrypoint that handles the FITS parsing, continuum fitting, line detection, and OpenRouter API communication.
* **`agent-card.json`**: The Blocks.ai agent configuration, declaring the inputs, outputs, schemas, and runtime metadata.
* **`DOCS.md`**: Technical documentation detailing integration patterns and SDK examples.
* **`pyproject.toml`**: Declares package metadata and python dependencies (`numpy`, `astropy`, `scipy`, `specutils`, `openai`, `httpx`).
* **`test_local.py`**: Integration script to run the pipeline locally with real Mast data.
* **`trigger.py`**: Helper script to programmatically trigger a task on the Blocks.ai network.
* **`inspect_fits.py`**: Diagnostic script to print the headers and structure of a local FITS file.
* **`laad02d9q_x1d.fits`**: Sample calibrated 1D Hubble Space Telescope FITS spectrum used for demos and tests.
