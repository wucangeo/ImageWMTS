import sys
import time
from osgeo import gdal
import io
from PIL import Image
import numpy as np

# gdal.UseExceptions()
"""
get_gdal_info: Get information about a GeoTIFF file using the gdalinfo command

Parameters
----------
path_to_geotiff : str
"""


def get_gdal_info(path_to_geotiff: str) -> dict:
    # for documentation, see: http://www.gdal.org/gdalinfo.html
    gdal_info = "gdalinfo -json {}"

    import shlex, subprocess
    from json import loads

    try:
        args = shlex.split(gdal_info.format(path_to_geotiff), posix=False)
        # if sys.platform == 'win32':
        #     args = gdal_info.format(path_to_geotiff)

        return gdal.Info(path_to_geotiff, format="json")

        # process = subprocess.Popen(args, stdout=subprocess.PIPE)
        # output_string = ""
        # while process.poll() is None:
        #     output = process.stdout.readline()
        #     if output:
        #         output_string += output.decode().strip()
        # rc = process.poll()
        # assert rc == 0 or rc is None, "Error! GDAL failed on [{}] with return code {}.".format(path_to_geotiff, rc)
        # return loads(output_string)
    except Exception as e:
        print(e)


"""
tile_file_path: Given x, y and zoom parameters from a WMTS GetTile request, construct an appropriate path

Parameters
----------
xtile : int
ytile : int
zoom : int
temp_dir : tempfile.TemporaryDirectory
geotiff_file : GeoTIFF
"""


def tile_file_path(xtile: int, ytile: int, zoom: int, temp_dir, geotiff_file) -> str:
    from tempfile import TemporaryDirectory

    assert isinstance(temp_dir, TemporaryDirectory)
    from os.path import join

    return join(
        temp_dir.name, "{}_{}_{}_{}.jpeg".format(geotiff_file.name, zoom, xtile, ytile)
    )


"""
make_tile_if_nonexistent: Given x, y and zoom parameters, use the gdal_translate command to create a JPG tile

Parameters
----------
xtile : int
ytile : int
zoom : int
temp_dir : tempfile.TemporaryDirectory
geotiff_file: GeoTIFF
"""


def make_tile_if_nonexistent(
    xtile: int, ytile: int, zoom: int, temp_dir, geotiff_file
) -> str:
    from tempfile import TemporaryDirectory

    assert isinstance(temp_dir, TemporaryDirectory)
    temporary_path = tile_file_path(xtile, ytile, zoom, temp_dir, geotiff_file)

    # for documentation, see: http://www.gdal.org/gdal_translate.html
    gdal_translate = "gdal_translate -of jpeg -projwin {} {} {} {} -projwin_srs WGS84 -q -outsize 50% 0 {} {}"

    from os.path import isfile
    import shlex, subprocess

    if not isfile(temporary_path):
        ul_lat, ul_lon = wmts_to_lat_lng(
            zoom=zoom,
            xtile=xtile,
            ytile=ytile,
        )

        lr_lat, lr_lon = wmts_to_lat_lng(
            zoom=zoom,
            xtile=xtile + 1,
            ytile=ytile + 1,
        )

        # for reference: -projwin ulx uly lrx lry
        args = shlex.split(
            gdal_translate.format(
                ul_lon,
                ul_lat,
                lr_lon,
                lr_lat,
                geotiff_file.path,
                temporary_path,
            ),
            posix=False,
        )
        process = subprocess.Popen(args, stdout=subprocess.PIPE)
        while process.poll() is None:
            output = process.stdout.readline()
        rc = process.poll()

        assert (
            rc == 0 or rc is None
        ), "Error! GDAL failed on [{}] with return code {}.".format(
            geotiff_file.path, rc
        )

    return temporary_path


"""
make_tile_if_nonexistent: Given x, y and zoom parameters, use the gdal_translate command to create a JPG tile

Parameters
----------
xtile : int
ytile : int
zoom : int
temp_dir : tempfile.TemporaryDirectory
geotiff_file: GeoTIFF
"""


def get_tile_by_xyz(xtile: int, ytile: int, zoom: int, geotiff_file) -> str:
    try:
        latlon_start = time.time()
        ul_lat, ul_lon = wmts_to_lat_lng(
            zoom=zoom,
            xtile=xtile,
            ytile=ytile,
        )

        lr_lat, lr_lon = wmts_to_lat_lng(
            zoom=zoom,
            xtile=xtile + 1,
            ytile=ytile + 1,
        )
        latlon_stop = time.time()
        print("经纬度计算：", latlon_stop - latlon_start)

        # GDAL快照转换
        trans_start = time.time()
        gdal_opts = gdal.TranslateOptions(
            format="JPEG",
            projWin=[ul_lon, ul_lat, lr_lon, lr_lat],
            projWinSRS="WGS84",
            noData=0,
            width=256,
            height=256,
        )
        vsipath = "/vsimem/image_path.jpeg"
        # vsipath = "D:/data/tiles/tile_{}_{}_{}.jpg".format(zoom, xtile, ytile)
        out_ds = gdal.Translate(
            vsipath,
            geotiff_file.path,
            options=gdal_opts,
        )
        trans_stop = time.time()
        print("GDAL快照：", trans_stop - trans_start)

        # 数组转换
        arr_start = time.time()
        out_arr = out_ds.ReadAsArray()
        rol_arr = np.rollaxis(out_arr, 0, 3)
        img = Image.fromarray(rol_arr)
        arr_stop = time.time()
        print("数组转换：", arr_stop - arr_start)

        # 转换为图片流
        byte_start = time.time()
        imgByteArr = io.BytesIO()
        img.save(imgByteArr, format="JPEG")
        imgByteArr = imgByteArr.getvalue()
        byte_stop = time.time()
        print("图片流转换：", byte_stop - byte_start)

        return imgByteArr
    except Exception as e:
        print("================???????", e)


"""
wmts_to_lat_lng: Get information about a GeoTIFF file using the gdalinfo command

Parameters
----------
xtile : int
ytile : int
zoom : int
"""


def wmts_to_lat_lng(xtile: int, ytile: int, zoom: int) -> tuple:
    # see: https://wiki.openstreetmap.org/wiki/Slippy_map_tilenames#Lon..2Flat._to_tile_numbers_2
    from math import atan, sinh, pi, degrees

    n = 2.0**zoom
    lon_deg = xtile / n * 360.0 - 180.0
    lat_rad = atan(sinh(pi * (1 - 2 * ytile / n)))
    lat_deg = degrees(lat_rad)
    return lat_deg, lon_deg
