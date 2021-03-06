#
#                                                                  gemini_python
#
#                                                        primitives_visualize.py
# ------------------------------------------------------------------------------
import numpy as np
from copy import deepcopy
from os.path import splitext

try:
    from stsci import numdisplay as nd
except ImportError:
    import numdisplay as nd

from gempy.utils import logutils
from gempy.gemini import gemini_tools as gt

from gempy.mosaic.mosaicAD import MosaicAD
from gempy.mosaic.gemMosaicFunction import gemini_mosaic_function

from geminidr.gemini.lookups import DQ_definitions as DQ
from gemini_instruments.gmos.pixel_functions import get_bias_level

from geminidr import PrimitivesBASE
from .parameters_visualize import ParametersVisualize

from recipe_system.utils.decorators import parameter_override
# ------------------------------------------------------------------------------
@parameter_override
class Visualize(PrimitivesBASE):
    """
    This is the class containing the visualization primitives.
    """
    tagset = None

    def __init__(self, adinputs, **kwargs):
        super(Visualize, self).__init__(adinputs, **kwargs)
        self.parameters = ParametersVisualize

    def display(self, adinputs=None, **params):
        """
        Displays an image on the ds9 display, using multiple frames if
        there are multiple extensions. Saturated pixels can be displayed
        in red, and overlays can also be shown.

        Parameters
        ----------
        extname: str
            'SCI', 'VAR', or 'DQ': plane to display
        frame: int
            starting frame for display
        ignore: bool
            setting to True turns off the display
        remove_bias: bool
            attempt to subtract bias before displaying?
        threshold: str='auto'/float
            level above which to flag pixels as saturated
        tile: bool
            attempt to tile arrays before displaying?
        zscale: bool
            use zscale algorithm?
        overlay: list
            list of overlays for the display
        """
        log = self.log
        log.debug(gt.log_message("primitive", self.myself(), "starting"))

        # No-op if ignore=True
        if params["ignore"]:
            log.warning("display turned off per user request")
            return

        threshold = params['threshold']
        remove_bias = params['remove_bias']
        extname = params['extname']
        tile = params['tile']
        zscale = params['zscale']
        overlays = params['overlay']
        frame = params['frame'] if params['frame'] else 1
        overlay_index = 0
        lnd = _localNumDisplay()

        for ad in adinputs:
            # Allows elegant break from nested loops
            if frame > 16:
                log.warning("Too many images; only the first 16 are displayed")
                break

            # Threshold and bias make sense only for SCI extension
            if extname != 'SCI':
                threshold = None
                remove_bias = False
            elif threshold == 'None':
                threshold = None
            elif threshold == 'auto':
                mosaicked = ((ad.phu.get(self.timestamp_keys["mosaicDetectors"])
                              is not None) or
                             (ad.phu.get(self.timestamp_keys["tileArrays"])
                              is not None))
                has_dq = all([ext.mask is not None for ext in ad])
                if not has_dq:
                    if mosaicked:
                        log.warning("Cannot add DQ to mosaicked data; no "
                                    "threshold mask will be applied to "
                                    "{}".format(ad.filename))
                        threshold = None
                    else:
                        # addDQ operates in place so deepcopy to preserve input
                        ad = self.addDQ([deepcopy(ad)])[0]

            if remove_bias:
                if (ad.phu.get('BIASIM') or ad.phu.get('DARKIM') or
                    any(ad.hdr.get('OVERSCAN'))):
                    log.fullinfo("Bias level has already been removed from "
                                 "data; no approximate correction will be "
                                 "performed")
                else:
                    try:
                        bias_level = get_bias_level(ad)
                    except NotImplementedError:
                        # For non-GMOS instruments
                        bias_level = None

                    if bias_level is not None:
                        ad = deepcopy(ad)  # Leave original untouched!
                        log.stdinfo("Subtracting approximate bias level from "
                                    "{} for display".format(ad.filename))
                        log.fullinfo("Bias levels used: {}".format(str(bias_level)))
                        for ext, bias in zip(ad, bias_level):
                            ext.subtract(np.float32(bias) if bias is not None
                                         else 0)
                    else:
                        log.warning("Bias level not found for {}; approximate "
                                    "bias will not be removed".format(ad.filename))

            # Check whether data needs to be tiled before displaying
            # Otherwise, flatten all desired extensions into a single list
            if tile and len(ad) > 1:
                log.fullinfo("Tiling extensions together before displaying")
                ad = self.tileArrays([ad], tile_all=True)[0]

            # Each extension is an individual display item (if the data have been
            # tiled, then there'll only be one extension per AD, of course)
            for ext in ad:
                if frame > 16:
                    break

                # Squeeze the data to remove any empty dimensions (eg, raw F2 data)
                ext.operate(np.squeeze)

                # Get the data we're going to display. TODO Replace extname with attr?
                data = getattr(ext, {'SCI':'data', 'DQ':'mask',
                                    'VAR':'variance'}[extname], None)
                dqdata = ext.mask
                if data is None:
                    log.warning("No data to display in {}[{}]".format(ext.filename,
                                                                      extname))
                    continue

                # One-dimensional data (ie, extracted spectra)
                if len(data.shape) == 1:
                    continue

                # Make threshold mask if desired
                masks = []
                mask_colors = []
                if threshold is not None:
                    if threshold != 'auto':
                        satmask = data > float(threshold)
                    else:
                        if dqdata is None:
                            log.warning("No DQ plane found; cannot make "
                                        "threshold mask")
                            satmask = None
                        else:
                            satmask = (dqdata & (DQ.non_linear | DQ.saturated)) > 0
                    if satmask is not None:
                        masks.append(satmask)
                        mask_colors.append(204)

                if overlays:
                    # Could be single overlay, or list. Replicate behaviour of
                    # gt.make_lists (which we can't use because we haven't
                    # made a complete list of displayed extensions at the start
                    # in order to avoid memory bloat)
                    try:
                        overlay = overlays[overlay_index]
                    except TypeError:
                        overlay = overlays
                    except IndexError:
                        if len(overlays) == 1:
                            overlay = overlays[0]
                    masks.append(overlay)
                    mask_colors.append(206)

                # Define the display name
                if tile and extname=='SCI':
                    name = ext.filename
                elif tile:
                    name = '{}({})'.format(ext.filename, extname)
                else:
                    name = '{}({},{})'.format(ext.filename, extname,
                                              ext.hdr['EXTVER'])

                try:
                    lnd.display(data, name=name, frame=frame, zscale=zscale,
                                bpm=None if extname=='DQ' else dqdata,
                                quiet=True, masks=masks, mask_colors=mask_colors)
                except IOError:
                    log.warning("ds9 not found; cannot display input")

                frame += 1

                # Print from statistics for flats
                if extname=='SCI' and {'GMOS', 'IMAGE', 'FLAT'}.issubset(ext.tags):
                    good_data = data[dqdata==0] if dqdata is not None else data
                    mean = np.mean(good_data)
                    median = np.median(good_data)
                    log.stdinfo("Twilight flat counts for {}:".format(ext.filename))
                    log.stdinfo("    Mean value:   {:.0f}".format(mean))
                    log.stdinfo("    Median value: {:.0f}".format(median))

        return adinputs

    def mosaicDetectors(self, adinputs=None, **params):
        return adinputs

    def mosaicADdetectors(self, adinputs=None, **params):
        """
        This primitive will use the gempy MosaicAD class to mosaic the frames
        of the input images.

        Parameters
        ----------
        suffix: str
            suffix to be added to output files. Default is '_mosaicAD'
        tile: bool
            tile images instead of a proper mosaic. Default is False.
        doimg: bool
            mosaic only SCI image data. Default is False
        interpolator: <str>
            type of interpolation to use across chip gaps
            ('linear', 'nearest', 'poly3', 'poly5', 'spline3', 'sinc')

        """
        def _compat(tlist):
            item = None
            if "GMOS" in tlist and "IMAGE" in tlist:
                item = 'GMOS IMAGE'
            elif "GSAOI" in tlist and "IMAGE" in tlist:
                item = 'GSAOI IMAGE'
            if not item:
                raise TypeError("File is not a supported type.")
            return item

        log = self.log
        log.debug(gt.log_message("primitive", self.myself(), "starting"))
        timestamp_key = self.timestamp_keys[self.myself()]
        do_img = params['doimg']
        suffix = params['suffix']
        tile = params['tile']

        adoutputs = []
        for ad in adinputs:
            log.stdinfo("\tMosaicAD Working on {}".format(_compat(ad.tags)))
            log.stdinfo("\tConstructing MosaicAD instance ...")

            mos = MosaicAD(ad, mosaic_ad_function=gemini_mosaic_function)

            log.stdinfo("\tMaking mosaic, converting data ...")

            ad_out = mos.as_astrodata(tile=tile, doimg=do_img)

            gt.mark_history(ad_out, primname=self.myself(), keyword=timestamp_key)
            ad_out.update_filename(suffix=suffix, strip=True)
            adoutputs.append(ad_out)

        return adoutputs


    def tileArrays(self, adinputs=None, **params):
        return adinputs

##############################################################################
# Below are the helper functions for the user level functions in this module #
##############################################################################

class _localNumDisplay(nd.NumDisplay):
    """
    This class overrides the default numdisplay.display function in
    order to implement super-fast overlays.  If this feature can be
    incorporated into numdisplay, this local version should go away.

    mask, if specified, should be a tuple of numpy arrays: the y- and
    x-coordinates of points to be masked.  For example,
    mask = np.where(data>threshold)
    TODO: Can it be an array of booleans, the same size as the data?
    """
    def display(self, pix, name=None, bufname=None, z1=None, z2=None,
                transform=None, bpm=None, zscale=False, contrast=0.25,
                scale=None, masks=None, mask_colors=None,
                offset=None, frame=None, quiet=False):

        """ Displays byte-scaled (UInt8) n to XIMTOOL device.
            This method uses the IIS protocol for displaying the data
            to the image display device, which requires the data to be
            byte-scaled.
            If input is not byte-scaled, it will perform scaling using
            set values/defaults.
        """
        log = logutils.get_logger(__name__)

        #Ensure that the input array 'pix' is a numpy array
        pix = np.array(pix)
        self.z1 = z1
        self.z2 = z2

        # If any of the display parameters are specified here, apply them
        # if z1 or z2 or transform or scale or offset or frame:
        # If zscale=True (like IRAF's display) selected, calculate z1 and z2 from
        # the data, and clear any transform specified in the call
        # Offset and scale are applied to the data and z1,z2,
        # so they have no effect on the display
        if zscale:
            if transform != None:
                if not quiet:
                    log.fullinfo("transform disallowed when zscale=True")
                transform = None
            if bpm is None:
                z1, z2 = nd.zscale.zscale(pix, contrast=contrast)
            else:
                goodpix = pix[bpm==0]
                # Ignore the mask unless a decent number of pixels are "good"
                if len(goodpix) >= 0.01 * np.multiply(*pix.shape):
                    sq_side = int(np.sqrt(len(goodpix)))
                    goodpix = goodpix[:sq_side**2].reshape(sq_side, sq_side)
                    z1, z2 = nd.zscale.zscale(goodpix, contrast=contrast)
                else:
                    z1, z2 = nd.zscale.zscale(pix, contrast=contrast)

        self.set(frame=frame, z1=z1, z2=z2,
                transform=transform, scale=scale, offset=offset)

        # Initialize the display device
        if not self.view._display or self.view.checkDisplay() is False:
            self.open()
        _d = self.view._display
        self.handle = _d.getHandle()

        # If no user specified values are provided, interrogate the array itself
        # for the full range of pixel values
        if self.z1 == None:
            self.z1 = np.minimum.reduce(np.ravel(pix))
        if self.z2 == None:
            self.z2 = np.maximum.reduce(np.ravel(pix))

        # If the user has not selected a specific buffer for the display,
        # select and set the frame buffer size based on input image size.
        if bufname == 'iraf':
            useiraf = True
            bufname = None
        else:
            useiraf = False

        if bufname != None:
            _d.setFBconfig(None,bufname=bufname)
        else:
            _ny,_nx = pix.shape
            _d.selectFB(_nx,_ny,reset=1,useiraf=useiraf)

        # Initialize the specified frame buffer
        _d.setFrame(self.frame)
        _d.eraseFrame()

        # Apply user specified scaling to image, returns original
        # if none are specified.
        bpix = self._transformImage(pix)

        # Recompute the pixel range of (possibly) transformed array
        _z1 = self._transformImage(self.z1)
        _z2 = self._transformImage(self.z2)

        # If there was a problem in the transformation, then restore the original
        # array as the one to be displayed, even though it may not be ideal.
        if _z1 == _z2:
            if not quiet:
                log.warning('Error encountered during transformation. '
                            'No transformation applied...')
            bpix = pix
            self.z1 = np.minimum.reduce(np.ravel(bpix))
            self.z2 = np.maximum.reduce(np.ravel(bpix))
            # Failsafe in case input image is flat:
            if self.z1 == self.z2:
                self.z1 -= 1.
                self.z2 += 1.
        else:
            # Reset z1/z2 values now so that image gets displayed with
            # correct range.  Also, when displaying transformed images
            # this allows the input pixel value to be displayed, rather
            # than the transformed pixel value.
            self.z1 = _z1
            self.z2 = _z2

        _wcsinfo = nd.displaydev.ImageWCS(bpix,z1=self.z1,z2=self.z2,name=name)
        if not quiet:
            log.fullinfo('Image displayed with z1: {} z2: {}'.format(self.z1,
                                                                     self.z2))

        bpix = self._fbclipImage(bpix,_d.fbwidth,_d.fbheight)

        # Change pixel value to specified color if desired
        if masks is not None:
            if not isinstance(masks,list):
                masks = [masks]
            if mask_colors is None:
                # Set to red as default
                mask_colors = [204]*len(masks)
            for i in range(len(masks)):
                if (masks[i][0].size>0 and masks[i][1].size>0):
                    bpix[masks[i]] = mask_colors[i]

        # Update the WCS to match the frame buffer being used.
        _d.syncWCS(_wcsinfo)

        # write out WCS to frame buffer, then erase buffer
        _d.writeWCS(_wcsinfo)

        # Now, send the trimmed image (section) to the display device
        _d.writeImage(bpix,_wcsinfo)
        #displaydev.close()
