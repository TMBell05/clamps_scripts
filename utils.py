"""
Collection of utility functions for processing CLAMPS data
"""
import xarray


def concat_files(files, concat_dim='time'):
    arr = xarray.open_mfdataset(files, autoclose=True, concat_dim=concat_dim, decode_times=False)
    data = {}

    for key in arr.keys():
        data[key] = arr[key].values

    arr.close()

    return data
