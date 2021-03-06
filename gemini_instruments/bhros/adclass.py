from astrodata import astro_data_tag, astro_data_descriptor, returns_list, TagSet
from ..gemini import AstroDataGemini
from .. import gmu

class AstroDataBhros(AstroDataGemini):

    __keyword_dict = dict(array_section = 'CCDSEC',
                          central_wavelength = 'WAVELENG',
                          overscan_section = 'BIASSEC')

    @staticmethod
    def _matches_data(data_provider):
        return data_provider.phu.get('INSTRUME', '').upper() == 'BHROS'

    @astro_data_tag
    def _tag_instrument(self):
        return TagSet(set(['BHROS', 'SPECT']), ())

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

        # The central_wavelength keyword is in Angstroms
        keyword = self._keyword_for('central_wavelength')
        wave_in_angstroms = self.phu.get(keyword, -1)
        if wave_in_angstroms < 0:
            return None
        return gmu.convert_units('angstroms', wave_in_angstroms,
                                 output_units)

    @astro_data_descriptor
    def dec(self):
        """
        Returns the Declination of the target, using the target_dec
        descriptor since the WCS is not sky coords

        Returns
        -------
        float
            right ascension in degrees
        """
        return self.target_dec(offset=True, icrs=True)

    @astro_data_descriptor
    def disperser(self, stripID=False, pretty=False):
        """
        Returns the name of the disperser. This is always 'bHROS'

        Parameters
        ----------
        stripID : bool
            Does nothing
        pretty : bool
            Does nothing

        Returns
        -------
        str
            The name of the disperser
        """
        return 'bHROS'

    @astro_data_descriptor
    def ra(self):
        """
        Returns the Right ascensionion of the target, using the target_ra
        descriptor since the WCS is not sky coords

        Returns
        -------
        float
            right ascension in degrees
        """
        return self.target_dec(offset=True, icrs=True)