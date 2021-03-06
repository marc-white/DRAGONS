import math
import re
from datetime import date

from astrodata import astro_data_tag, astro_data_descriptor, returns_list, TagSet
from .pixel_functions import get_bias_level
from . import lookup
from .. import gmu
from ..gemini import AstroDataGemini

class AstroDataGmos(AstroDataGemini):

    __keyword_dict = dict(array_name = 'AMPNAME',
                          array_section = 'CCDSEC',
                          camera = 'INSTRUME',
                          overscan_section = 'BIASSEC',
                          wavelength_reference_pixel = 'CRPIX1',
                          )

    @staticmethod
    def _matches_data(data_provider):
        return data_provider.phu.get('INSTRUME', '').upper() in ('GMOS-N', 'GMOS-S')

    @astro_data_tag
    def _tag_instrument(self):
        # tags = ['GMOS', self.instrument().upper().replace('-', '_')]
        return TagSet(['GMOS'])

    @astro_data_tag
    def _tag_dark(self):
        if self.phu.get('OBSTYPE') == 'DARK':
            return TagSet(['DARK'], blocks=['IMAGE', 'SPECT'])

    @astro_data_tag
    def _tag_arc(self):
        if self.phu.get('OBSTYPE') == 'ARC':
            return TagSet(['ARC', 'CAL'])

    @astro_data_tag
    def _tag_bias(self):
        if self.phu.get('OBSTYPE') == 'BIAS':
            return TagSet(['BIAS', 'CAL'], blocks=['IMAGE', 'SPECT'])

    @astro_data_tag
    def _tag_flat(self):
        if self.phu.get('OBSTYPE') == 'FLAT':
            if self.phu.get('GRATING') == 'MIRROR':
                f1, f2 = self.phu['FILTER1'], self.phu['FILTER2']
                # This kind of filter prevents imaging to be classified as FLAT
                if any(('Hartmann' in f) for f in (f1, f2)):
                    return

            return TagSet(['GCALFLAT', 'FLAT', 'CAL'])

    @astro_data_tag
    def _tag_twilight(self):
        if self.phu.get('OBJECT').upper() == 'TWILIGHT':
            # Twilight flats are of OBSTYPE == OBJECT, meaning that the generic
            # FLAT tag won't be triggered. Add it explicitly
            return TagSet(['TWILIGHT', 'CAL', 'FLAT'])

    def _tag_is_spect(self):
        pairs = (
            ('MASKTYP', 0),
            ('MASKNAME', 'None'),
            ('GRATING', 'MIRROR')
        )

        matches = (self.phu.get(kw) == value for (kw, value) in pairs)
        if any(matches):
            return False
        return True

    @astro_data_tag
    def _tag_ifu(self):
        if not self._tag_is_spect():
            return

        mapping = {
            'IFU-B': 'ONESLIT_BLUE',
            'IFU-B-NS': 'ONESLIT_BLUE',
            'b': 'ONESLIT_BLUE',
            'IFU-R': 'ONESLIT_RED',
            'IFU-R-NS': 'ONESLIT_RED',
            'r': 'ONESLIT_RED',
            'IFU-2': 'TWOSLIT',
            'IFU-NS-2': 'TWOSLIT',
            's': 'TWOSLIT'
        }

        names = set(key for key in mapping.keys() if key.startswith('IFU'))

        mskt, mskn = self.phu.get('MASKTYP'), self.phu.get('MASKNAME')
        if mskt == -1 and (mskn in names or re.match('g[ns]ifu_slit[rbs]_mdf', mskn)):
            if mskn not in names:
                mskn = re.match('g.ifu_slit(.)_mdf', mskn).groups()[0]

            return TagSet(['SPECT', 'IFU', mapping[mskn]])

    @astro_data_tag
    def _tag_mask(self):
        spg = self.phu.get
        if spg('GRATING') == 'MIRROR' and spg('MASKTYP') != 0:
            return TagSet(['MASK'])

    @astro_data_tag
    def _tag_image(self):
        if self.phu.get('GRATING') == 'MIRROR':
            return TagSet(['IMAGE'])

    @astro_data_tag
    def _tag_ls(self):
        if not self._tag_is_spect():
            return

        if self.phu.get('MASKTYP') == 1 and self.phu.get('MASKNAME', '').endswith('arcsec'):
            return TagSet(['SPECT', 'LS'])

    @astro_data_tag
    def _tag_mos(self):
        if not self._tag_is_spect():
            return

        mskt = self.phu.get('MASKTYP')
        mskn = self.phu.get('MASKNAME', '')
        if mskt == 1 and not (mskn.startswith('IFU') or mskn.startswith('focus') or mskn.endswith('arcsec')):
            return TagSet(['SPECT', 'MOS'])

    @astro_data_tag
    def _tag_nodandshuffle(self):
        if 'NODPIX' in self.phu:
            return TagSet(['NODANDSHUFFLE'])

    @astro_data_descriptor
    def amp_read_area(self):
        """
        Returns a list of amplifier read areas, one per extension, made by
        combining the amplifier name and detector section. Or returns a
        string if called on a single-extension slice.

        Returns
        -------
        list/str
            read_area of each extension
        """
        ampname = self.array_name()
        detsec = self.detector_section(pretty=True)
        # Combine the amp name(s) and detector section(s)
        if self.is_single:
            return "'{}':{}".format(ampname,
                        detsec) if ampname and detsec else None
        else:
            return ["'{}':{}".format(a,d) if a and d else None
                    for a,d in zip(ampname, detsec)]

    @astro_data_descriptor
    def array_name(self):
        """
        Returns a list of the names of the arrays of the extensions, or
        a string if called on a single-extension slice

        Returns
        -------
        list/str
            names of the arrays
        """
        return self.hdr.get('AMPNAME')

    @astro_data_descriptor
    def central_wavelength(self, asMicrometers=False, asNanometers=False, asAngstroms=False):
        """
        Returns the central wavelength in meters or specified units

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
        # Keywords should be the same, but CENTWAVE was only added post-2007
        try:
            central_wavelength = self.phu['CENTWAVE']
        except KeyError:
            central_wavelength = self.phu.get('GRWLEN', -1)

        if central_wavelength < 0.0:
            return None
        else:
            return gmu.convert_units('nanometers', central_wavelength,
                                     output_units)

    @astro_data_descriptor
    def detector_name(self, pretty=False):
        """
        Returns the name(s) of the detector(s), from the PHU DETID keyword.
        Calling with pretty=True will provide a single descriptive string.

        Parameters
        ----------
        pretty : bool
            If True, return a single descriptive string

        Returns
        -------
        str
            detector name
        """
        if pretty:
            pretty_detname_dict = {
                "SDSU II CCD": "EEV",
                "SDSU II e2v DD CCD42-90": "e2vDD",
                "S10892": "Hamamatsu-S",
                "S10892-N": "Hamamatsu-N"
                }
            return pretty_detname_dict.get(self.phu.get('DETTYPE'))
        else:
            return self.phu.get('DETID')

    @astro_data_descriptor
    def detector_rois_requested(self):
        """
        Returns a list of ROIs, as tuples in a 1-based inclusive (IRAF-like)
        format (x1, x2, y1, y2), in physical (unbinned) pixels.

        Returns
        -------
            list of tuples, one per ROI
        """
        roi_list = []
        for roi in range(1, 10):
            x1 = self.phu.get('DETRO{}X'.format(roi))
            xs = self.phu.get('DETRO{}XS'.format(roi))
            y1 = self.phu.get('DETRO{}Y'.format(roi))
            ys = self.phu.get('DETRO{}YS'.format(roi))
            if x1 and xs and y1 and ys:
                xs *= self.detector_x_bin()
                ys *= self.detector_y_bin()
                roi_list.append((x1, x1+xs-1, y1, y1+ys-1))
            else:
                break
        return roi_list

    @astro_data_descriptor
    def detector_roi_setting(self):
        """
        Looks at the first ROI and returns a descriptive string describing it
        These are more or less the options in the OT

        Returns
        -------
        str
            Name of the ROI setting used or
            "Custom" if the ROI doesn't match
            "Undefined" if there's no ROI in the header
        """
        roi_dict = lookup.gmosRoiSettings
        rois = self.detector_rois_requested()
        if rois:
            roi_setting = 'Custom'
            for s in roi_dict:
                if rois[0] in roi_dict[s]:
                    roi_setting = s
        else:
            roi_setting = 'Undefined'
        return roi_setting

    @astro_data_descriptor
    def detector_x_bin(self):
        """
        Returns the detector binning in the x-direction

        Returns
        -------
        int
            The detector binning
        """
        def _get_xbin(b):
            try:
                return int(b.split()[0])
            except (AttributeError, ValueError):
                return None

        binning = self.hdr.get('CCDSUM')
        if self.is_single:
            return _get_xbin(binning)
        else:
            xbin_list = [_get_xbin(b) for b in binning]
            # Check list is single-valued
            return xbin_list[0] if xbin_list == xbin_list[::-1] else None

    @astro_data_descriptor
    def detector_y_bin(self):
        """
        Returns the detector binning in the y-direction

        Returns
        -------
        int
            The detector binning
        """
        def _get_ybin(b):
            try:
                return int(b.split()[1])
            except (AttributeError, ValueError, IndexError):
                return None

        binning = self.hdr.get('CCDSUM')
        if self.is_single:
            return _get_ybin(binning)
        else:
            ybin_list = [_get_ybin(b) for b in binning]
            # Check list is single-valued
            return ybin_list[0] if ybin_list == ybin_list[::-1] else None

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
            offset = self.phu.get('POFFSET') / self.pixel_scale()
        except TypeError:  # either is None
            return None
        # Flipped for GMOS-N if on bottom port
        return -offset if (self.phu.get('INPORT')==1 and
                           self.instrument()=='GMOS-N') else offset

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
            offset = self.phu.get('QOFFSET') / self.pixel_scale()
        except TypeError:  # either is None
            return None
        # Flipped for GMOS-S if on bottom port
        return -offset if (self.phu.get('INPORT')==1 and
                           self.instrument()=='GMOS-S') else offset

    @astro_data_descriptor
    def disperser(self, stripID=False, pretty=False):
        """
        Returns the name of the grating used for the observation

        Parameters
        ----------
        stripID : bool
            If True, removes the component ID and returns only the name of
            the disperser.
        pretty : bool, also removed the trailing '+'
            If True,
        Returns
        -------
        str
            name of the grating
        """
        stripID |= pretty
        disperser = self.phu.get('GRATING')
        if stripID:
            disperser = gmu.removeComponentID(disperser)
            if pretty:
                try:
                    disperser = disperser.strip('+')
                except AttributeError:
                    pass

        return disperser

    @astro_data_descriptor
    def dispersion(self, asMicrometers=False, asNanometers=False, asAngstroms=False):
        """
        Returns the dispersion (wavelength units per pixel) in meters
        or specified units, as a list (one value per extension) or a
        float if used on a single-extension slice.

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
        list/float
            The dispersion(s)
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
        cd11 = self.hdr.get('CD1_1')
        try:
            dispersion = [gmu.convert_units('meters', d, output_units)
                          for d in cd11]
        except TypeError:
            dispersion = gmu.convert_units('meters', cd11, output_units)
        return dispersion

    @returns_list
    @astro_data_descriptor
    def dispersion_axis(self):
        """
        Returns the axis along which the light is dispersed.

        Returns
        -------
        (list of) int (1)
            Dispersion axis.
       """
        return 1 if 'SPECT' in self.tags else None

    @astro_data_descriptor
    def exposure_time(self):
        """
        Returns the exposure time in seconds.

        Returns
        -------
        float
            Exposure time.

        """
        exp_time = self.phu.get(self._keyword_for('exposure_time'), -1)
        return None if exp_time < 0 or exp_time > 10000 else exp_time

    @astro_data_descriptor
    def focal_plane_mask(self, stripID=False, pretty=False):
        """
        Returns the name of the focal plane mask.

        Parameters
        ----------
        stripID : bool
            Doesn't actually do anything.
        pretty : bool
            Same as for stripID

        Returns
        -------
        str
            The name of the focal plane mask
        """
        mask = self.phu.get('MASKNAME')
        return 'Imaging' if mask == 'None' else mask

    @returns_list
    @astro_data_descriptor
    def gain(self):
        """
        Returns the gain (electrons/ADU) for each extension

        Returns
        -------
        list/float
            Gains used for the observation

        """
        # If the file has been prepared, we trust the header keywords
        if 'PREPARED' in self.tags:
            return self.hdr.get(self._keyword_for('gain'))

        # Get the correct dict of gain values
        ut_date = self.ut_date()
        if ut_date is None:
            return None  # converted to list by decorator if needed

        if ut_date >= date(2017, 2, 24):
            gain_dict = lookup.gmosampsGain
        elif ut_date >= date(2015, 8, 26):
            gain_dict = lookup.gmosampsGainBefore20170224
        elif ut_date >= date(2006, 8, 31):
            gain_dict = lookup.gmosampsGainBefore20150826
        else:
            gain_dict = lookup.gmosampsGainBefore20060831

        read_speed_setting = self.read_speed_setting()
        gain_setting = self.gain_setting()
        # This may be a list
        ampname = self.array_name()

        # Return appropriate object
        if self.is_single:
            return gain_dict.get((read_speed_setting, gain_setting, ampname))
        else:
            return [gain_dict.get((read_speed_setting, gain_setting, a))
                    for a in ampname]

    @astro_data_descriptor
    def gain_setting(self):
        """
        Returns the gain settings of the extensions. These could be different
        but the old system couldn't handle that so we'll return a string but
        check that they're all the same

        Returns
        -------
        str
            Gain setting
        """
        def _get_setting(g):
            if g is None:
                return None
            else:
                return 'low' if g < 3.0 else 'high'

        # This seems to rely on obtaining the original GAIN header keyword
        gain_settings = None
        if 'PREPARED' not in self.tags:
            # Use the (incorrect) GAIN header keywords to determine the setting
            gain = self.hdr.get('GAIN')
        else:
            # For prepared data, we use the value of the gain_setting keyword
            try:
                gain_settings = self.hdr[self._keyword_for('gain_setting')]
            except KeyError:
                # This code deals with data that haven't been processed with
                # gemini_python (no GAINSET keyword), but have a PREPARED tag
                try:
                    gain = self.hdr['GAINORIG']
                    # If GAINORIG is 1 in all the extensions, then the original
                    # gain is actually in GAINMULT(!?)
                    if gain == 1 or gain == [1] * len(self):
                        gain = self.hdr['GAINMULT']
                except KeyError:
                    # Use the gain() descriptor as a last resort
                    gain = self.gain()

        # Convert gain to gain_settings if we only got the gain
        if gain_settings is None:
            if self.is_single:
                gain_settings = _get_setting(gain)
            else:
                gain_settings = [_get_setting(g) for g in gain]

        # Check that all gain settings are the same if multiple extensions
        if isinstance(gain_settings, list):
            if gain_settings != gain_settings[::-1]:
                return None
            return gain_settings[0]
        else:
            return gain_settings

    @astro_data_descriptor
    def group_id(self):
        """
        Returns a string representing a group of data that are compatible
        with each other.  This is used when stacking, for example.  Each
        instrument and mode of observation will have its own rules.

        GMOS uses the detector binning, amp_read_area, gain_setting, and
        read_speed_setting. Flats and twilights have the pretty version of
        the filter name included. Science data have the pretty filter name
        and observation_id as well. And spectroscopic data have the grating.
        Got all that?

        Returns
        -------
        str
            A group ID for compatible data.
        """
        tags = self.tags

        # Things needed for all observations
        unique_id_descriptor_list_all = ['detector_x_bin', 'detector_y_bin',
                                             'read_mode', 'amp_read_area']
        if 'SPECT' in tags:
            unique_id_descriptor_list_all.append('disperser')

        # List to format descriptor calls using 'pretty=True' parameter
        call_pretty_version_list = ['filter_name', 'disperser']

        # Force this to be a list
        force_list = ['amp_read_area']

        if 'BIAS' in tags:
            id_descriptor_list = []
        elif 'DARK' in tags:
            id_descriptor_list = ['exposure_time']
        elif 'IMAGE' in tags and ('FLAT' in tags or 'TWILIGHT' in tags):
            id_descriptor_list = ['filter_name']
        else:
            id_descriptor_list = ['observation_id', 'filter_name']

        # Add in all of the common descriptors required
        id_descriptor_list.extend(unique_id_descriptor_list_all)

        # Form the group_id
        descriptor_object_string_list = []
        for descriptor in id_descriptor_list:
            kw = {}
            if descriptor in call_pretty_version_list:
                kw['pretty'] = True
            descriptor_object = getattr(self, descriptor)(**kw)

            # Ensure we get a list, even if only looking at one extension
            if (descriptor in force_list and
                    not isinstance(descriptor_object, list)):
                descriptor_object = [descriptor_object]

            # Convert descriptor to a string and store
            descriptor_object_string_list.append(str(descriptor_object))

        # Create and return the final group_id string
        return '_'.join(descriptor_object_string_list)

    @astro_data_descriptor
    def nod_count(self):
        """
        Returns a tuple with the number of integrations made in each
        of the nod-and-shuffle positions

        Returns
        -------
        tuple
            number of integrations in the A and B positions
        """
        try:
            return (int(self.phu['ANODCNT']), int(self.phu['BNODCNT']))
        except KeyError:
            return None

    @astro_data_descriptor
    def nod_offsets(self):
        """
        Returns a tuple with the offsets from the default telescope position
        of the A and B nod-and-shuffle positions (in arcseconds)

        Returns
        -------
        tuple
            offsets in arcseconds
        """
        # Cope with two possible situations
        try:
            ayoff = self.phu['NODAYOFF']
            byoff = self.phu['NODBYOFF']
        except KeyError:
            ayoff = 0.0
            try:
                byoff = self.phu['NODYOFF']
            except KeyError:
                return None
        return (ayoff, byoff)

    @astro_data_descriptor
    def nod_pixels(self):
        """
        Returns the number of rows that the charge has been shuffled, in
        nod-and-shuffle data

        Returns
        -------
        int
            The number of rows by which the charge is shuffled
        """
        return self.phu.get('NODPIX') if 'NODANDSHUFFLE' in self.tags else None

    @astro_data_descriptor
    def nominal_photometric_zeropoint(self):
        """
        Returns the nominal zeropoints (i.e., the magnitude corresponding to
        a pixel value of 1) for the extensions in an AD object.

        Returns
        -------
        float/list
            zeropoint values, one per SCI extension
        """
        def _zpt(ccd, filt, gain, bunit):
            zpt = lookup.nominal_zeropoints.get((ccd, filt))
            try:
                return zpt - (2.5 * math.log10(gain) if
                              bunit.lower() == 'adu' else 0)
            except TypeError:
                return None

        gain = self.gain()
        filter_name = self.filter_name(pretty=True)
        ccd_name = self.hdr.get('CCDNAME')
        # Explicit: if BUNIT is missing, assume data are in ADU
        bunit = self.hdr.get('BUNIT', 'adu')

        # Zeropoints in table are for electrons, so subtract 2.5*log10(gain)
        # if the data are in ADU
        if self.is_single:
            return _zpt(ccd_name, filter_name, gain, bunit)
        else:
            return [_zpt(c, filter_name, g, b)
                    for c, g, b in zip(ccd_name, gain, bunit)]

    @returns_list
    @astro_data_descriptor
    def non_linear_level(self):
        """
        Returns the level at which the data become non-linear, in ADU.
        For GMOS, this is just the saturation level.

        Returns
        -------
        float/list
            Value(s) at which the data become non-linear
        """
        return self.saturation_level()

    @astro_data_descriptor
    def overscan_section(self, pretty=False):
        """
        Returns the overscan (or bias) section.  If pretty is False, a
        tuple of 0-based coordinates is returned with format (x1, x2, y1, y2).
        If pretty is True, a keyword value is returned without parsing as a
        string.  In this format, the coordinates are generally 1-based.

        One tuple or string is return per extension/array.  If more than one
        array, the tuples/strings are return in a list.  Otherwise, the
        section is returned as a tuple or a string.

        Parameters
        ----------
        pretty : bool
         If True, return the formatted string found in the header.

        Returns
        -------
        tuple of integers or list of tuples
            Position of the overscan section using Python slice values.

        string or list of strings
            Position of the overscan section using an IRAF section
            format (1-based).
        """
        return self._parse_section('BIASSEC', pretty)

    @astro_data_descriptor
    def pixel_scale(self):
        """
        Returns the image scale in arcsec per pixel, accounting for binning

        Returns
        -------
        float
            pixel scale
        """
        pixscale_dict = lookup.gmosPixelScales

        # Pixel scale dict is keyed by instrument ('GMOS-N' or 'GMOS-S')
        # and detector type
        pixscale_key = (self.instrument(), self.phu.get('DETTYPE'))
        try:
            raw_pixel_scale = pixscale_dict[pixscale_key]
        except KeyError:
            return None
        return raw_pixel_scale * self.detector_y_bin()

    @astro_data_descriptor
    def read_mode(self):
        """
        Returns a string describing the readout mode, which sets the
        gain and readout speed

        Returns
        -------
        str
            read mode used
        """
        # Get the right mapping (detector-dependent)
        det_key = 'Hamamatsu' if \
            self.detector_name(pretty=True).startswith('Hamamatsu') \
            else 'default'
        mode_dict = lookup.read_mode_map.get(det_key)
        mode_key = (self.gain_setting(), self.read_speed_setting())
        return mode_dict.get(mode_key)

    @returns_list
    @astro_data_descriptor
    def read_noise(self):
        """
        Returns the read noise (as a list if multiple extensions, or
        a float if a single-extension slice)

        Returns
        -------
        float/list
            read noise
        """
        if 'PREPARED' in self.tags:
            return self.hdr.get(self._keyword_for('read_noise'))
        else:
            # Get the correct dict of read noise values
            ut_date = self.ut_date()
            if ut_date is None:
                return None  # converted to list by decorator if needed

            if ut_date > date(2017, 2, 24):
                rn_dict = lookup.gmosampsRdnoise
            elif ut_date >= date(2015, 8, 26):
                rn_dict = lookup.gmosampsRdnoiseBefore20170224
            elif ut_date >= date(2006, 8, 31):
                rn_dict = lookup.gmosampsRdnoiseBefore20150826
            else:
                rn_dict = lookup.gmosampsRdnoiseBefore20060831

        read_speed_setting = self.read_speed_setting()
        gain_setting = self.gain_setting()
        # This may be a list
        ampname = self.array_name()

        # Return appropriate object
        # Return appropriate object
        if self.is_single:
            return rn_dict.get((read_speed_setting, gain_setting, ampname))
        else:
            return [rn_dict.get((read_speed_setting, gain_setting, a))
                    for a in ampname]

    @astro_data_descriptor
    def read_speed_setting(self):
        """
        Returns the setting for the readout speed (slow or fast)

        Returns
        -------
        str
            the setting for the readout speed
        """
        try:
            ampinteg = self.phu['AMPINTEG']
        except KeyError:
            return None
        detector = self.detector_name(pretty=True)
        if detector.startswith('Hamamatsu'):
            return 'slow' if ampinteg > 8000 else 'fast'
        else:
            return'slow' if ampinteg > 2000 else 'fast'

    @astro_data_descriptor
    def saturation_level(self):
        """
        Returns the saturation level (in ADU)

        Returns
        -------
        list/float
            saturation level
        """
        def _well_depth(detector, amp, bin, gain, bunit):
            try:
                return lookup.gmosThresholds[detector][amp] * bin / (
                    gain if 'electron' in bunit else 1)
            except KeyError:
                return None

        # We need to know whether the data have been bias-subtracted
        # First, look for keywords in PHU
        bias_subtracted = \
            self.phu.get(self._keyword_for('bias_image')) is not None or \
            self.phu.get(self._keyword_for('dark_image')) is not None

        # OVERSCAN keyword also means data have been bias-subtracted
        overscan_levels = self.hdr.get('OVERSCAN')

        detname = self.detector_name(pretty=True)
        detector = self.header[0]['DETECTOR']  # the only way to distinguish GMOS-S Ham pre/post video board work.
        xbin = self.detector_x_bin()
        ybin = self.detector_y_bin()
        bin_factor = xbin * ybin
        ampname = self.array_name()
        gain = self.gain()
        # Explicit: if BUNIT is missing, assume data are in ADU
        bunits = self.hdr.get('BUNIT', 'adu')

        # Get estimated bias levels from LUT
        bias_levels = get_bias_level(self, estimate=True)
        if bias_levels is None:
            bias_levels = 0.0 if self.is_single else [0.0] * len(self)
        else:
            if not self.is_single:
                bias_levels = [b if b is not None else 0 for b in bias_levels]

        adc_limit = 65535
        # Get the limit that could be processed without hitting the ADC limit
        # Subtracted bias level if data are bias-subtracted, and
        # multiply by gain if data are in electron/electrons
        if self.is_single:
            bias_subtracted |= overscan_levels is not None
            processed_limit = (adc_limit - (bias_levels if bias_subtracted
                              else 0)) * (gain if 'electron' in bunits else 1)
        else:
            bias_subtracted = [bias_subtracted or o is not None
                               for o in overscan_levels]
            processed_limit = [(adc_limit - (blev if bsub else 0))
                              * (g if 'electron' in bunit else 1)
                              for blev, bsub, g, bunit in
                              zip(bias_levels, bias_subtracted, gain, bunits)]


        # For old EEV data, or heavily-binned data, we're ADC-limited
        if detname == 'EEV' or bin_factor > 2:
            return processed_limit
        else:
            # Otherwise, we're limited by the electron well depths
            if self.is_single:
                saturation = _well_depth(detector, ampname, bin_factor, gain, bunits)
                if saturation is None:
                    saturation = processed_limit
                else:
                    saturation += bias_levels if not bias_subtracted else 0
                    if saturation > processed_limit:
                        saturation = processed_limit
            else:
                testlut = _well_depth(detector, ampname[0], bin_factor, gain[0], bunits[0])
                well_limit = [_well_depth(detector, a, bin_factor, g, b)
                              for a, g, b in zip(ampname, gain, bunits)]
                saturation = [None if w is None else
                              min(w + blev if not bsub else 0, p)
                              for w, p, blev, bsub in zip(well_limit,
                                processed_limit, bias_levels, bias_subtracted)]
        return saturation

    @astro_data_descriptor
    def wcs_ra(self):
        """
        Returns the Right Ascension of the center of the field based on the
        WCS rather than the RA keyword. This just uses the CRVAL1 keyword.

        Returns
        -------
        float
            right ascension in degrees
        """
        # Try the first (only if sliced) extension, then the PHU
        try:
            h = self[0].hdr
            crval = h['CRVAL1']
            ctype = h['CTYPE1']
        except (KeyError, IndexError):
            crval = self.phu.get('CRVAL1')
            ctype = self.phu.get('CTYPE1')
        return crval if ctype == 'RA---TAN' else None

    @astro_data_descriptor
    def wcs_dec(self):
        """
        Returns the Declination of the center of the field based on the
        WCS rather than the DEC keyword. This just uses the CRVAL2 keyword.

        Returns
        -------
        float
            declination in degrees
        """
        # Try the first (only if sliced) extension, then the PHU
        try:
            h = self[0].hdr
            crval = h['CRVAL2']
            ctype = h['CTYPE2']
        except (KeyError, IndexError):
            crval = self.phu.get('CRVAL2')
            ctype = self.phu.get('CTYPE2')
        return crval if ctype == 'DEC--TAN' else None
