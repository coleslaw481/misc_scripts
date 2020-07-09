#!/usr/bin/env python

import os
import sys
import random
import argparse
import logging
from collections import deque

from PIL import Image
from PIL import ImageEnhance

from tqdm import tqdm

logger = logging.getLogger(__name__)


LOG_FORMAT = "%(asctime)-15s %(levelname)s %(relativeCreated)dms " \
             "%(filename)s::%(funcName)s():%(lineno)d %(message)s"


class Formatter(argparse.ArgumentDefaultsHelpFormatter,
                argparse.RawDescriptionHelpFormatter):
    pass


def _parse_arguments(desc, args):
    """
    Parses command line arguments
    :param desc:
    :param args:
    :return:
    """
    parser = argparse.ArgumentParser(description=desc,
                                     formatter_class=Formatter)
    parser.add_argument('imagedir',
                        help='Directory containing tiles')
    parser.add_argument('outdir',
                        help='Output directory')
    parser.add_argument('--duration', type=int, default=400,
                        help='Milliseconds between switching frames')
    parser.add_argument('--numupdators', type=int, default=30,
                        help='Number of concurrent tile updators')
    parser.add_argument('--prefill', action='store_true',
                        help='If set, randomly fill image first')
    parser.add_argument('--numframes', type=int, default=500,
                        help='Number of frames to generate')
    parser.add_argument('--colsep', type=int, default=4,
                        help='Number pixels between each column')
    parser.add_argument('--rowsep', type=int, default=2,
                        help='Number pixels between each row')
    parser.add_argument('--width', type=int, default=800,
                        help='Width of output image')
    parser.add_argument('--height', type=int, default=600,
                        help='Height of output image')
    parser.add_argument('--logconf', default=None,
                        help='Path to python logging configuration file in '
                             'this format: https://docs.python.org/3/library/'
                             'logging.config.html#logging-config-fileformat '
                             'Setting this overrides -v parameter which uses '
                             ' default logger.')
    parser.add_argument('--verbose', '-v', action='count', default=0,
                        help='Increases verbosity of logger to standard '
                             'error for log messages in this module '
                             '. Messages are '
                             'output at these python logging levels '
                             '-v = ERROR, -vv = WARNING, -vvv = INFO, '
                             '-vvvv = DEBUG, -vvvvv = NOTSET')

    return parser.parse_args(args)


def _setup_logging(args):
    """
    Sets up logging based on parsed command line arguments.
    If args.logconf is set use that configuration otherwise look
    at args.verbose and set logging for this module
    :param args: parsed command line arguments from argparse
    :raises AttributeError: If args is None or args.logconf is None
    :return: None
    """

    if args.logconf is None:
        level = (50 - (10 * args.verbose))
        logging.basicConfig(format=LOG_FORMAT,
                            level=level)
        logger.setLevel(level)
        return

    # logconf was set use that file
    logging.config.fileConfig(args.logconf,
                              disable_existing_loggers=False)


class TileDropper(object):
    """
    Drops new tiles in vertical pattern
    """
    def __init__(self, thecols=None, therows=None, colsep=4, rowsep=2,
                 tile_list=None, img=None):
        """
        Constructor
        :param startloc:
        :param colsep:
        :param rowsep:
        :param tile_list:
        :param img:
        """
        self._colsep = colsep
        self._rowsep = rowsep
        self._tile_list = tile_list
        self._img = img
        self._curloc = None
        self._thecols = thecols
        self._therows = therows
        self._brightness = [1.0, 0.8, 0.6, 0.4, 0.2]
        self._prev_tiles = deque(maxlen=5)

    def update_location(self):
        """

        :return:
        """
        self._prev_tiles.clear()
        self._curloc = (random.choice(self._thecols), random.choice(self._therows))

    def drop_tile(self):
        """
        Drops a tile and updates brightness of previously
        dropped tiles
        :return: location of dropped tile as tuple
        """
        if self._curloc is None:
            self.update_location()

        a_tile = random.choice(self._tile_list)
        self._prev_tiles.appendleft(a_tile)

        counter = 0
        for entry in self._prev_tiles:
            ypos = self._curloc[1]-(counter*(entry.size[1]+self._rowsep))

            self._img.paste(ImageEnhance.Brightness(entry).enhance(self._brightness[counter]),
                            box=(self._curloc[0], ypos))
            counter += 1
        self._curloc = (self._curloc[0], self._curloc[1]+a_tile.size[1]+self._rowsep)
        if self._curloc[1] > (self._img.size[1] + ((a_tile.size[1]+self._rowsep)*len(self._brightness))):
            self._curloc = None

def get_tiles(imagedir):
    """
    Gets images from image dir
    :param imagedir:
    :return:
    """
    abs_img_dir = os.path.abspath(imagedir)
    img_list = []
    for entry in tqdm(os.listdir(abs_img_dir)):
        fp = os.path.join(abs_img_dir, entry)
        if not os.path.isfile(fp):
            continue
        if not entry.endswith('.png'):
            continue
        t_img = Image.open(fp)
        img_list.append(t_img)
        img_list.append(t_img.rotate(90))
        img_list.append(t_img.rotate(180))
        img_list.append(t_img.rotate(270))
    return img_list


def randomly_fill_image(theargs, img, tile_list):
    """

    :param theargs:
    :param img:
    :param tile_list:
    :return:
    """
    all_tiles = []
    for x in range(0, theargs.width, theargs.colsep+16):
        for y in range(0, theargs.height, theargs.rowsep+16):
            all_tiles.append((x, y))

    glowing_tiles = random.choices(all_tiles, k=24)

    for x in range(0, theargs.width, theargs.colsep+16):
        for y in range(0, theargs.height, theargs.rowsep+16):
            a_tile = random.choice(tile_list)
            brightness_value = 0.2
            if (x, y) in glowing_tiles:
                brightness_value = 1.0
            img.paste(ImageEnhance.Brightness(a_tile).enhance(brightness_value), box=(x, y))
    return img


def run(theargs):
    """
    Main flow of processing

    :param theargs:
    :return:
    """
    tile_list = get_tiles(theargs.imagedir)
    logger.info('Got ' + str(len(tile_list)) + ' image tiles')

    abs_outdir = os.path.abspath(theargs.outdir)
    if not os.path.isdir(abs_outdir):
        os.makedirs(abs_outdir, mode=0o755)

    img = Image.new('RGB', (theargs.width, theargs.height))

    if theargs.prefill is True:
        randomly_fill_image(theargs, img, tile_list)

    colwidth = tile_list[0].size[0]+theargs.colsep
    thecols = []
    for x in range(0, img.size[0], colwidth):
        thecols.append(x)

    rowwidth = tile_list[0].size[1]+theargs.rowsep
    therows = []
    for y in range(0, img.size[1] - (5*rowwidth), rowwidth):
        therows.append(y)

    d_list = []
    for tds in range(0, theargs.numupdators):
        dropper = TileDropper(thecols=thecols, therows=therows,
                              colsep=theargs.colsep, rowsep=theargs.rowsep,
                              tile_list=tile_list, img=img)
        d_list.append(dropper)

    img_list = []

    for x in tqdm(range(0, theargs.numframes)):
        logger.debug('Step ' + str(x))
        for dropper in d_list:
            dropper.drop_tile()
        # img.save(os.path.join(abs_outdir, str(x) + '.png'))
        img_list.append(img.copy())
    img_list[0].save(os.path.join(abs_outdir, 'out.gif'),
                     save_all=True, append_images=img_list[1:], loop=0, duration=theargs.duration)
    return 0


def main(args):
    """
    Main entry point for program
    :param args:
    :return:
    """
    desc = """
    
    Patrix image generator
    

    """
    theargs = _parse_arguments(desc, args[1:])
    theargs.program = args[0]

    try:
        _setup_logging(theargs)
        return run(theargs)
    except Exception as e:
        logger.exception('Caught exception')
        return 2
    finally:
        logging.shutdown()


if __name__ == '__main__':  # pragma: no cover
    sys.exit(main(sys.argv))
