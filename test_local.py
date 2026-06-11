"""Test the astro_spectra handler function locally using mock request parts and MAST data."""

import json
import urllib.request
from handler import handler


class MockPart:
    def __init__(self, part_id, data=None, text=None):
        self.part_id = part_id
        self.data = data
        self.text = text


class MockTask:
    def __init__(self, request_parts):
        self.request_parts = request_parts


def main():
    print("Downloading sample Hubble Space Telescope (HST) spectrum from NASA's MAST archive...")
    url = "https://mast.stsci.edu/api/v0.1/Download/file?uri=mast:HST/product/laad02d9q_x1d.fits"
    
    try:
        req = urllib.request.Request(
            url, 
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        )
        with urllib.request.urlopen(req) as response:
            fits_bytes = response.read()
        print(f"Downloaded FITS file: {len(fits_bytes):,} bytes.")
    except Exception as e:
        print(f"Error downloading FITS: {e}")
        return

    # Prepare inputs
    parameters = {
        "polynomial_order": 5,
        "mask_regions": ""
    }
    
    task = MockTask([
        MockPart(part_id="fits_file", data=fits_bytes),
        MockPart(part_id="parameters", text=json.dumps(parameters))
    ])

    print("Running handler locally...")
    response = handler(task, ctx=None)
    
    # Parse the artifact JSON
    result_json = response["artifacts"][0]["data"]
    result = json.loads(result_json)
    
    # Extract the Markdown report
    markdown_report = response["artifacts"][1]["data"]
    
    print("\n==============================================")
    print("LOCAL INTEGRATION TEST COMPLETE")
    print("==============================================")
    print(f"Wavelength Units : {result.get('units_wavelength')}")
    print(f"Flux Units       : {result.get('units_flux')}")
    print(f"Spectral Points  : {len(result.get('wavelength', [])):,}")
    print(f"Detected Lines   : {len(result.get('detected_lines', []))}")
    print("==============================================\n")
    
    print("==============================================")
    print("RENDERED MARKDOWN REPORT ARTIFACT")
    print("==============================================")
    print(markdown_report)
    print("==============================================\n")


if __name__ == "__main__":
    main()
