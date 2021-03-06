import re
import math

from astrodata import astro_data_tag, TagSet, astro_data_descriptor, returns_list
from ..gemini import AstroDataGemini
from .lookup import array_properties, nominal_zeropoints
from astropy.wcs import WCS, FITSFixedWarning
import warnings

from ..common import section_to_tuple, build_group_id
from .. import gmu

class AstroDataF2(AstroDataGemini):

    __keyword_dict = dict(camera = 'LYOT',
                          central_wavelength = 'GRWLEN',
                          disperser = 'GRISM',
                          focal_plane_mask = 'MOSPOS',
                          lyot_stop = 'LYOT',
                          )

    @staticmethod
    def _matches_data(data_provider):
        return data_provider.phu.get('INSTRUME', '').upper() in ('F2', 'FLAM')

    @astro_data_tag
    def _tag_instrument(self):
        return TagSet(['F2'])

    @astro_data_tag
    def _tag_dark(self):
        ot = self.phu.get('OBSTYPE')
        dkflt = False
        for f in (self.phu.get('FILTER1', ''), self.phu.get('FILTER2', '')):
            if re.match('DK.?', f):
                dkflt = True
                break

        if dkflt or ot == 'DARK':
            return TagSet(['DARK', 'CAL'], blocks=['IMAGE', 'SPECT'])

    @astro_data_tag
    def _tag_image(self):
        if self.phu.get('GRISM') == 'Open' or self.phu.get('GRISMPOS') == 'Open':
            return TagSet(['IMAGE'])

    # Do not tag this as astro_data_tag. It's a helper function
    def _tag_is_spect(self):
        grism = self.phu.get('GRISM', '')
        grpos = self.phu.get('GRISMPOS', '')

        for pattern in ("JH.?", "HK.?", "R3K.?"):
            if re.match(pattern, grism) or re.match(pattern, grpos):
                return True

        return False

    @astro_data_tag
    def _tag_is_ls(self):
        if not self._tag_is_spect():
            return

        decker = self.phu.get('DECKER') == 'Long_slit' or self.phu.get('DCKERPOS') == 'Long_slit'

        if decker or re.match(".?pix-slit", self.phu.get('MOSPOS', '')):
            return TagSet(['LS', 'SPECT'])

    @astro_data_tag
    def _tag_is_mos(self):
        if not self._tag_is_spect():
            return

        decker = self.phu.get('DECKER') == 'mos' or self.phu.get('DCKERPOS') == 'mos'

        if decker or re.match("mos.?", self.phu.get('MOSPOS', '')):
            return TagSet(['MOS', 'SPECT'])

    @astro_data_tag
    def _tag_arc(self):
        if self.phu.get('OBSTYPE') == 'ARC':
            return TagSet(['ARC', 'CAL'])

    @astro_data_tag
    def _tag_flat(self):
        if self.phu.get('OBSTYPE') == 'FLAT':
            return TagSet(['FLAT', 'CAL'])

    @astro_data_tag
    def _tag_twilight(self):
        if self.phu.get('OBJECT').upper() == 'TWILIGHT':
            rej = set(['FLAT']) if self.phu.get('GRISM') != 'Open' else set()
            return TagSet(['TWILIGHT', 'CAL'], blocks=rej)

    @astro_data_tag
    def _tag_disperser(self):
        disp = self.phu.get('DISPERSR', '')
        if disp.startswith('DISP_WOLLASTON'):
            return TagSet(['POL'])
        elif disp.startswith('DISP_PRISM'):
            return TagSet(['SPECT', 'IFU'])

    @returns_list
    @astro_data_descriptor
    def array_section(self, pretty=False):
        """
        Returns the rectangular section that includes the pixels that would be
        exposed to light.  If pretty is False, a tuple of 0-based coordinates
        is returned with format (x1, x2, y1, y2).  If pretty is True, a keyword
        value is returned without parsing as a string.  In this format, the
        coordinates are generally 1-based.

        One tuple or string is return per extension/array, in a list. If the
        method is called on a single slice, the section is returned as a tuple
        or a string.

        Parameters
        ----------
        pretty : bool
         If True, return the formatted string found in the header.

        Returns
        -------
        tuple of integers or list of tuples
            Location of the pixels exposed to light using Python slice values.

        string or list of strings
            Location of the pixels exposed to light using an IRAF section
            format (1-based).
        """
        value_filter = (str if pretty else section_to_tuple)
        # TODO: discover reason why this is hardcoded, rather than from keyword
        return value_filter('[1:2048,1:2048]')

    # TODO: sort out the unit-handling here
    @astro_data_descriptor
    def central_wavelength(self, asMicrometers=False, asNanometers=False,
                           asAngstroms=False):
        """
        Returns the central wavelength in meters or the specified units

        Parameters
        ----------
        asMicrometers : bool
            If True, return the wavelength in microns
        asNanometers : bool
            If True, return the wavelength in nanometers
        asAngstroms : bool
            If True, return the wavelength in Angstroms

        Returns
        -------
        float
            The central wavelength setting

        """
        unit_arg_list = [asMicrometers, asNanometers, asAngstroms]
        if unit_arg_list.count(True) == 1:
            # Just one of the unit arguments was set to True. Return the
            # central wavelength in these units
            if asMicrometers:
                output_units = "micrometers"
            if asNanometers:
                output_units = "nanometers"
            if asAngstroms:
                output_units = "angstroms"
        else:
            # Either none of the unit arguments were set to True or more than
            # one of the unit arguments was set to True. In either case,
            # return the central wavelength in the default units of meters.
            output_units = "meters"

        central_wavelength = float(self.phu['GRWLEN'])
        if self.phu['FILTER1'] == 'K-long-G0812':
                central_wavelength = 2.2

        if central_wavelength < 0.0:
            return None
        else:
            return gmu.convert_units('micrometers', central_wavelength,
                                     output_units)

    @astro_data_descriptor
    def data_section(self, pretty=False):
        """
        Returns the rectangular section that includes the pixels that would be
        exposed to light.  If pretty is False, a tuple of 0-based coordinates
        is returned with format (x1, x2, y1, y2).  If pretty is True, a keyword
        value is returned without parsing as a string.  In this format, the
        coordinates are generally 1-based.

        One tuple or string is return per extension/array, in a list. If the
        method is called on a single slice, the section is returned as a tuple
        or a string.

        Parameters
        ----------
        pretty : bool
         If True, return the formatted string found in the header.

        Returns
        -------
        tuple of integers or list of tuples
            Location of the pixels exposed to light using Python slice values.

        string or list of strings
            Location of the pixels exposed to light using an IRAF section
            format (1-based).

        """
        return self.array_section(pretty=pretty)

    @astro_data_descriptor
    def detector_section(self, pretty=False):
        """
        Returns the section covered by the detector relative to the whole
        mosaic of detectors.  If pretty is False, a tuple of 0-based coordinates
        is returned with format (x1, x2, y1, y2).  If pretty is True, a keyword
        value is returned without parsing as a string.  In this format, the
        coordinates are generally 1-based.

        One tuple or string is return per extension/array, in a list. If the
        method is called on a single slice, the section is returned as a tuple
        or a string.

        Parameters
        ----------
        pretty : bool
         If True, return the formatted string found in the header.

        Returns
        -------
        tuple of integers or list of tuples
            Position of the detector using Python slice values.

        string or list of strings
            Position of the detector using an IRAF section format (1-based).

        """
        return self.array_section(pretty=pretty)

    @returns_list
    @astro_data_descriptor
    def dispersion_axis(self):
        """
        Returns the axis along which the light is dispersed.

        Returns
        -------
        (list of) int (2)
            Dispersion axis.
        """
        return 2 if 'SPECT' in self.tags else None

    @astro_data_descriptor
    def detector_x_offset(self):
        """
        Returns the offset from the reference position in pixels along
        the positive x-direction of the detector

        Returns
        -------
        float
            The offset in pixels
        """
        try:
            return -self.phu.get('QOFFSET') / self.pixel_scale()
        except TypeError:  # either is None
            return None

    @astro_data_descriptor
    def detector_y_offset(self):
        """
        Returns the offset from the reference position in pixels along
        the positive y-direction of the detector

        Returns
        -------
        float
            The offset in pixels
        """
        try:
            offset = -self.phu.get('POFFSET') / self.pixel_scale()
        except TypeError:  # either is None
            return None
        # Bottom port flip
        return -offset if self.phu.get('INPORT')==1 else offset

    @astro_data_descriptor
    def filter_name(self, stripID=False, pretty=False):
        """
        Returns the name of the filter(s) used.  The component ID can be
        removed with either 'stripID' or 'pretty'.  If a combination of filters
        is used, the filter names will be join into a unique string with '&' as
        separator.  If 'pretty' is True, filter positions such as 'Open',
        'Dark', 'blank', and others are removed leaving only the relevant
        filters in the string.

        Parameters
        ----------
        stripID : bool
            If True, removes the component ID and returns only the name of
            the filter.
        pretty : bool
            Parses the combination of filters to return a single string value
            wi the "effective" filter.

        Returns
        -------
        str
            The name of the filter combination with or without the component ID.

        """
        try:
            filter1 = self.phu['FILTER1']
            filter2 = self.phu['FILTER2']
        except KeyError:
            try:
                # Old (pre-20100301) keyword names
                filter1 = self.phu['FILT1POS']
                filter2 = self.phu['FILT2POS']
            except KeyError:
                return None

        if stripID or pretty:
            filter1 = gmu.removeComponentID(filter1)
            filter2 = gmu.removeComponentID(filter2)

        filter = [filter1, filter2]
        if pretty:
            # Remove filters with the name 'open'
            if 'open' in filter2 or 'Open' in filter2:
                del filter[1]
            if 'open' in filter1 or 'Open' in filter1:
                del filter[0]

            if ('Block' in filter1 or 'Block' in filter2 or 'Dark' in filter1
                or 'Dark' in filter2):
                filter = ['blank']
            if 'DK' in filter1 or 'DK' in filter2:
                filter = ['dark']

            if len(filter) == 0:
                filter = ['open']

        # Return &-concatenated names if we still have two filter names
        return '&'.join(filter[:2])

    @returns_list
    @astro_data_descriptor
    def gain(self):
        """
        Returns the gain used for the observation.  This is read from a
        lookup table using the read_mode and the well_depth.

        Returns
        -------
        float
            Gain used for the observation

        """
        lnrs = self.phu.get('LNRS')
        gain = getattr(array_properties.get(self.read_mode()), 'gain', None)
        # F2 adds the reads (in ADU), so the electron-to-ADU conversion
        # needs to be divided by the number of reads
        return gain / lnrs if gain and lnrs else None

    @astro_data_descriptor
    def group_id(self):
        """
        Returns a string representing a group of data that are compatible
        with each other.  This is used when stacking, for example.  Each
        instrument and mode of observation will have its own rules. F2's
        is quite a mouthful.

        Returns
        -------
        str
            A group ID for compatible data.
        """
        # essentially a copy of the NIRI group_id descriptor,
        # adapted for F2.
        tags = self.tags

        # Descriptors required for each frame type
        dark_id = ["exposure_time", "coadds"]
        flat_id = ["filter_name", "camera", "exposure_time", "observation_id"]
        flat_twilight_id = ["filter_name", "camera"]
        science_id = ["observation_id", "filter_name", "camera", "exposure_time"]
        ## !!! KL: added exposure_time to science_id for QAP.  The sky subtraction
        ## !!! seems unable to deal with difference exposure time circa Sep 2015.
        ## !!! The on-target dither sky-sub falls over completely.
        ## !!! Also, we do not have a fully tested scale by exposure routine.

        # This is used for imaging flats and twilights to distinguish between
        # the two types
        additional_item = None

        # Update the list of descriptors to be used depending on image type
        ## This requires updating to cover all spectral types
        ## Possible updates to the classification system will make this usable
        ## at the Gemini level
        if "DARK" in tags:
            id_descriptor_list = dark_id
        elif 'IMAGE' in tags and 'FLAT' in tags:
            id_descriptor_list = flat_id
            additional_item = "F2_IMAGE_FLAT"
        elif 'IMAGE' in tags and 'TWILIGHT' in tags:
            id_descriptor_list = flat_twilight_id
            additional_item = "F2_IMAGE_TWILIGHT"
        else:
            id_descriptor_list = science_id

        # Add in all of the common descriptors required
        id_descriptor_list.extend(["read_mode", "detector_section"])
        if "SPECT" in tags:
            id_descriptor_list.extend(["disperser", "focal_plane_mask"])

        return build_group_id(self, id_descriptor_list,
                              prettify=["filter_name", "disperser", "focal_plane_mask"],
                              additional=additional_item)

    # @astro_data_descriptor
    # def instrument(self):
    #     """
    #     Returns the name of the instrument, coping with the fact that early
    #     data apparently had the keyword INSTRUME='Flam'

    #     Returns
    #     -------
    #     str
    #         The name of the instrument, namely 'F2'
    #     """
    #     return 'F2'

    @returns_list
    @astro_data_descriptor
    def nominal_photometric_zeropoint(self):
        """
        Returns the nominal zeropoints (i.e., the magnitude corresponding to
        a pixel value of 1) for the extensions in an AD object.

        Returns
        -------
        list/float
            zeropoint values, one per SCI extension
        """
        gain = self.gain()
        filter_name = self.filter_name(pretty=True)
        camera = self.camera(pretty=True)
        # Explicit: if BUNIT is missing, assume data are in ADU
        bunit = self.hdr.get('BUNIT', 'adu')
        zpt = nominal_zeropoints.get((filter_name, camera))

        # Zeropoints in table are for electrons, so subtract 2.5*log10(gain)
        # if the data are in ADU
        if self.is_single:
            try:
                return zpt - (
                    2.5 * math.log10(gain) if bunit.lower() == 'adu' else 0)
            except TypeError:
                return None
        else:
            return [zpt - (2.5 * math.log10(g) if b.lower() == 'adu' else 0)
                   if zpt and g else None
                   for g, b in zip(gain, bunit)]

    @astro_data_descriptor
    def nonlinearity_coeffs(self):
        return getattr(array_properties.get(self.read_mode()), 'coeffs', None)

    @returns_list
    @astro_data_descriptor
    def non_linear_level(self):
        """
        Returns the level at which the data become non-linear, in ADU.

        Returns
        -------
        int
            Value at which the data become non-linear
        """
        # Element [3] gives the fraction of the saturation level at which
        # the data become non-linear
        fraction = getattr(array_properties.get(self.read_mode()),
                           'linlimit', None)
        sat_level = self.saturation_level()
        # Saturation level might be an element or a list
        if self.is_single:
            try:
                return int(fraction * sat_level)
            except TypeError:
                return None
        else:
            return [int(fraction * s) if fraction and s else None
                    for s in sat_level]

    # TODO: is 'F2_DARK' still a tag?
    @astro_data_descriptor
    def observation_type(self):
        """
        Returns the observation type (OBJECT, DARK, BIAS, etc.)

        Returns
        -------
        str
            Observation type
        """
        return 'DARK' if 'F2_DARK' in self.tags else self.phu.get('OBSTYPE')

    @astro_data_descriptor
    def pixel_scale(self):
        """
        Returns the image scale in arcseconds per pixel

        Returns
        -------
        float
            pixel scale
        """
        # Try to use the Gemini-level helper method
        try:
            return self._get_wcs_pixel_scale()
        except KeyError:
            return self.phu.get('PIXSCALE')

    @astro_data_descriptor
    def read_mode(self):
        """
        Returns the read mode (i.e., the number of non-destructive read pairs)

        Returns
        -------
        str
            readout mode
        """
        lnrs = self.phu.get('LNRS')
        return None if lnrs is None else str(lnrs)

    @returns_list
    @astro_data_descriptor
    def read_noise(self):
        """
        Returns the read noise in electrons

        Returns
        -------
        float
            read noise
        """
        # Element [0] gives the read noise
        return getattr(array_properties.get(self.read_mode(), None),
                       'readnoise', None)

    @returns_list
    @astro_data_descriptor
    def saturation_level(self):
        """
        Returns the saturation level (in ADU)

        Returns
        -------
        float/list
            saturation level
        """
        well_depth = getattr(array_properties.get(self.read_mode(), None),
                       'welldepth', None)
        gain = self.gain()
        if self.is_single:
            try:
                return int(well_depth / gain)
            except TypeError:
                return None
        else:
            saturation_adu = [int(well_depth / g) if well_depth and g else None
                              for g in gain]
        return saturation_adu

    # TODO: document why these are reversed
    @astro_data_descriptor
    def telescope_x_offset(self):
        """
        Returns the x offset from origin of this image

        Returns
        -------
        float
            x offset
        """
        try:
            return -self.phu['YOFFSET']
        except KeyError:
            return None

    @astro_data_descriptor
    def telescope_y_offset(self):
        """
        Returns the y offset from origin of this image

        Returns
        -------
        float
            y offset
        """
        try:
            return -self.phu['XOFFSET']
        except KeyError:
            return None

    def _get_wcs_coords(self):
        """
        Returns the RA and dec of the middle of the data array

        Returns
        -------
        tuple
            (right ascension, declination)
        """
        # Cass rotator centre (according to Andy Stephens from gacq)
        x, y = 1034, 1054
        with warnings.catch_warnings():
            warnings.filterwarnings('ignore', category=FITSFixedWarning)
            # header[0] is PHU, header[1] is first (and only) extension HDU
            wcs = WCS(self.header[1])
            result = wcs.wcs_pix2world(x,y,1, 1) if wcs.naxis==3 \
                else wcs.wcs_pix2world(x,y, 1)
        ra, dec = float(result[0]), float(result[1])

        if 'NON_SIDEREAL' in self.tags:
            ra, dec = gmu.toicrs('APPT', ra, dec, ut_datetime=self.ut_datetime())

        return (ra, dec)
