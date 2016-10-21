import argparse
import os
from datetime import datetime
from glob import glob

import matplotlib.pyplot as plt
import netCDF4
import numpy as np

from numpy import sin, cos

import VADAnalysis
from VADAnalysis.core import list_to_masked_array

FILL_VALUE = -9999.
CNR_THRESH = -27.
VEL_LIM = (-30, 30)
HGT_LIM = (0, 1000)
PROFILES_PER_PLOT = 5


# TODO - GET 3D RETRIEVAL WORKING
def calc_vad_3d(az, elev, vel):
    """
    IN DEVELOPMENT DO NOT USE
    :param az:
    :param elev:
    :param vel:
    :return:
    """
    elev = np.deg2rad(elev)
    az = np.deg2rad(az)

    if vel.size > 1:  # If there could be sufficient data points...
        A = sum(vel * sin(az))
        B = sum(sin(az) ** 2) * cos(elev)
        C = sum(cos(az) * sin(az)) * cos(elev)
        G = sum(sin(az)) * sin(elev)

        D = sum(vel * cos(az))
        E = sum(sin(az) * cos(az)) * cos(elev)
        F = sum(cos(az) ** 2) * cos(elev)
        H = sum(cos(az)) * sin(elev)

        W = sum(vel)
        X = sum(sin(az))*cos(elev)
        Y = sum(cos(az))*cos(elev)
        Z = sin(elev)

        # solve A = uB + vC + wG , D = uE + vF + wH and W = uX + vY+ wZ
        y = np.array([[B, E, X], [C, F, Y], [G, H, Z]])
        z = np.array([A, D, W])
        # print y
        # print z
        try:
            sol = np.linalg.solve(y, z)
            # print sol
            u = sol[0]
            v = sol[1]
            w = sol[2]
            print u, v, w
            return u, v, w
        except np.linalg.linalg.LinAlgError:
            return FILL_VALUE, FILL_VALUE, FILL_VALUE
    else:
        return FILL_VALUE, FILL_VALUE, FILL_VALUE


def calc_vad(az, elev, vel):
    elev = np.deg2rad(elev)
    az = np.deg2rad(az)

    if vel.size > 1:  # If there could be sufficient data points...
        A = sum(vel * sin(az))
        B = sum(sin(az) ** 2) * cos(elev)
        C = sum(cos(az) * sin(az)) * cos(elev)

        D = sum(vel * cos(az))
        E = sum(sin(az) * cos(az)) * cos(elev)
        F = sum(cos(az) ** 2) * cos(elev)

        # solve A = uB + vC and D = uE + vF
        y = np.array([[B, E], [C, F]])
        z = np.array([A, D])
        # print y
        # print z
        try:
            sol = np.linalg.solve(y, z)
            # print sol
            u = sol[0]
            v = sol[1]
            return u, v, len(vel)
        except np.linalg.linalg.LinAlgError:
            return FILL_VALUE, FILL_VALUE, FILL_VALUE
    else:
        return FILL_VALUE, FILL_VALUE, FILL_VALUE


def process_file(in_file):

    # Open the netcdf
    nc = netCDF4.Dataset(in_file)
    date = datetime.strptime(nc.start_time, "%Y-%m-%dT%H:%M:%S")

    hgt = []
    u = []
    v = []
    rmse = []

    for i, range in enumerate(nc['range'][:]):

        # Get the required stuff for this range ring
        cnr = nc['cnr'][:, i].transpose()
        vel = nc['radial_wind'][:, i].transpose()
        az = nc['azimuth'][:, i].transpose()
        elev = np.round(np.mean(nc['elevation'][:, i]), 2)

        # Filter out the bad values based on CNR
        az = np.where(cnr <= CNR_THRESH, FILL_VALUE, az)
        vel = np.where(cnr <= CNR_THRESH, FILL_VALUE, vel)

        az = list_to_masked_array(az, FILL_VALUE)
        vel = list_to_masked_array(vel, FILL_VALUE)

        # Calculate the vad and height for this range ring
        tmp_u, tmp_v, gates = calc_vad_3d(az, elev, vel)

        # Calculate the RMSE
        N = float(vel.size)
        tmp_E = vel - (np.sin(np.deg2rad(az)) * tmp_u) - (np.cos(np.deg2rad(az)) * tmp_v)
        tmp_RMSE = np.sqrt(1 / N * np.sum(tmp_E ** 2))

        # Append to the lists for plotting
        u.append(tmp_u)
        v.append(tmp_v)
        hgt.append(VADAnalysis.core.ray_height(range, elev))
        rmse.append(tmp_RMSE)

    # Close the netcdf
    nc.close()

    return u, v, hgt, rmse, date


if __name__=='__main__':
    parser = argparse.ArgumentParser()

    parser.add_argument('-i', dest='in_files', nargs='*')
    parser.add_argument('-O', dest='out_prefix', default='sonde')
    parser.add_argument('-o', dest='out_dir', default=os.getcwd())

    args = parser.parse_args()

    for i, f in enumerate(sorted(args.in_files)):
        print f
        u, v, hgt, rmse, date = process_file(f)

        fig = plt.figure(1, figsize=(15, 7))
        fig.suptitle(date.isoformat())
        plt.subplot(1, 3, 1)
        plt.plot(u, hgt, label=date.strftime("%H:%M"))
        plt.title("U velocity vs Height")
        plt.xlabel('Velocity (m/s)')
        plt.ylabel('Height (m)')
        plt.xlim(VEL_LIM)
        plt.ylim(HGT_LIM)
        plt.legend()

        plt.subplot(1, 3, 2)
        plt.plot(v, hgt)
        plt.title("V velocity vs Height")
        plt.xlabel('Velocity (m/s)')
        plt.ylabel('Height (m)')
        plt.xlim(VEL_LIM)
        plt.ylim(HGT_LIM)

        plt.subplot(1, 3, 3)
        plt.plot(rmse, hgt)
        plt.title("RMS vs Height")
        plt.xlabel('RMS')
        plt.ylabel('Height (m)')
        plt.xlim((0, 10))
        plt.ylim(HGT_LIM)

        # Create profile base on start time of first profile
        if i % PROFILES_PER_PLOT == 0:
            image_name = "{prefix}_{date}.png"
            image_name = image_name.format(prefix=args.out_prefix, date=date.strftime("%Y%m%d_%H%M%S"))
            image_name = os.path.join(args.out_dir, image_name)

        if i % PROFILES_PER_PLOT == PROFILES_PER_PLOT - 1:
            # Save the image
            plt.savefig(image_name)
            plt.clf()
            plt.close()






