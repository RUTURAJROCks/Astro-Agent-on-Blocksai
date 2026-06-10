import urllib.request
from astropy.io import fits
import numpy as np

url = "https://mast.stsci.edu/api/v0.1/Download/file?uri=mast:HST/product/laad02d9q_x1d.fits"
req = urllib.request.Request(
    url, 
    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
)
with urllib.request.urlopen(req) as response:
    fits_bytes = response.read()

with open("temp_inspect.fits", "wb") as f:
    f.write(fits_bytes)

with fits.open("temp_inspect.fits") as hdul:
    hdul.info()
    for i, hdu in enumerate(hdul):
        print(f"\n--- HDU {i} ---")
        if hdu.data is not None:
            print("Shape:", hdu.data.shape)
            if hasattr(hdu.data, "names"):
                print("Columns:", hdu.data.names)
                for name in hdu.data.names[:5]:
                    col_data = hdu.data[name]
                    print(f"  Column '{name}' type: {type(col_data)}, shape: {col_data.shape}")
                    if len(col_data.shape) > 0:
                        print(f"    First element type: {type(col_data[0])}")
                        if hasattr(col_data[0], "shape"):
                            print(f"    First element shape: {col_data[0].shape}")
