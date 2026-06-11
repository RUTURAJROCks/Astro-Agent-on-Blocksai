"""Trigger a task on the astro_spectra agent with a real MAST FITS file and print results."""

import json
import base64
import threading
import urllib.request

from dotenv import load_dotenv
load_dotenv()

from blocks_network import SendMessageRequestPart, create_task_client


def main():
    print("Downloading sample Hubble Space Telescope (HST) spectrum from NASA's MAST archive...")
    # This is a public calibrated 1D spectrum of GD71 (white dwarf star calibration source) from the STIS instrument on HST
    url = "https://mast.stsci.edu/api/v0.1/Download/file?uri=mast:HST/product/laad02d9q_x1d.fits"
    
    try:
        req = urllib.request.Request(
            url, 
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        )
        with urllib.request.urlopen(req) as response:
            fits_bytes = response.read()
        print(f"Successfully downloaded FITS file: {len(fits_bytes):,} bytes.")
    except Exception as e:
        print(f"Error downloading FITS from MAST: {e}")
        return

    client = create_task_client()

    parameters = {
        "polynomial_order": 5,
        "mask_regions": ""
    }

    session = client.send_message(
        agent_name="astro_spectra",
        request_parts=[
            SendMessageRequestPart(
                part_id="fits_file",
                data=fits_bytes,
                mime_type="application/octet-stream"
            ),
            SendMessageRequestPart(
                part_id="parameters",
                text=json.dumps(parameters)
            )
        ],
    )

    print(f"Task created: {session.task_id}")

    done = threading.Event()

    def on_progress(event):
        print("[progress]", event.get("message") or event.get("progress") or "")

    def parse_and_print_result(data_bytes):
        try:
            data = json.loads(data_bytes.decode())
            print("\n==============================================")
            print("SPECTRAL ANALYSIS RESULTS (NASA MAST DATA)")
            print("==============================================")
            print(f"Wavelength Units : {data.get('units_wavelength')}")
            print(f"Flux Units       : {data.get('units_flux')}")
            print(f"Spectral Points  : {len(data.get('wavelength', [])):,}")
            
            lines = data.get("detected_lines", [])
            print(f"Detected Lines   : {len(lines)}")
            print("----------------------------------------------")
            if lines:
                print("First 15 detected spectral features:")
                # Sort lines by significance descending
                sorted_lines = sorted(lines, key=lambda l: l.get("significance", 0), reverse=True)
                for line in sorted_lines[:15]:
                    print(f"  - Wavelength: {line['wavelength']:.2f} Å | Type: {line['type']} | Significance: {line.get('significance', 0):.2f}σ")
            else:
                print("No prominent spectral features detected.")
            print("==============================================\n")
        except Exception as e:
            print(f"Failed to parse results JSON: {e}")

    def on_artifact(event):
        ref = event.artifact_ref
        if ref is None:
            return
        if ref.kind == "inline" and ref.data:
            parse_and_print_result(base64.b64decode(ref.data))
        else:
            downloaded = session.download_artifact(ref)
            parse_and_print_result(downloaded.data)

    def on_terminal(event):
        print("[done] Task complete")
        done.set()

    session.on_progress(on_progress)
    session.on_artifact(on_artifact)
    session.on_terminal(on_terminal)

    done.wait(timeout=60)
    session.close()
    client.destroy()


if __name__ == "__main__":
    main()
