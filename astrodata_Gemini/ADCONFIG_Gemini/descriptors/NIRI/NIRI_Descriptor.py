import math

from astrodata import Descriptors
from astrodata import Errors
from astrodata import Lookups
from astrodata.Calculator import Calculator
from gempy import string
import GemCalcUtil 

from StandardDescriptorKeyDict import globalStdkeyDict
from StandardNIRIKeyDict import stdkeyDictNIRI
from GEMINI_Descriptor import GEMINI_DescriptorCalc

class NIRI_DescriptorCalc(GEMINI_DescriptorCalc):
    # Updating the global key dictionary with the local key dictionary
    # associated with this descriptor class
    globalStdkeyDict.update(stdkeyDictNIRI)
    
    niriFilternameMapConfig = None
    niriFilternameMap = {}
    niriSpecDict = None
    
    def __init__(self):
        self.niriSpecDict = \
            Lookups.getLookupTable('Gemini/NIRI/NIRISpecDict',
                                   'niriSpecDict')
        self.niriFilternameMapConfig = \
            Lookups.getLookupTable('Gemini/NIRI/NIRIFilterMap',
                                   'niriFilternameMapConfig')
        self.makeFilternameMap()
        
        self.nsappwave = \
            Lookups.getLookupTable('Gemini/IR/nsappwavepp.fits', 1)
    
    def central_wavelength(self, dataset, asMicrometers=False, \
        asNanometers=False, asAngstroms=False, **args):
        # Currently for NIRI data, the central wavelength is recorded in
        # angstroms
        input_units = 'angstroms'
        # Determine the output units to use
        unit_arg_list = [asMicrometers, asNanometers, asAngstroms]
        if unit_arg_list.count(True) == 1:
            # Just one of the unit arguments was set to True. Return the
            # central wavelength in these units
            if asMicrometers:
                output_units = 'micrometers'
            if asNanometers:
                output_units = 'nanometers'
            if asAngstroms:
                output_units = 'angstroms'
        else:
            # Either none of the unit arguments were set to True or more than
            # one of the unit arguments was set to True. In either case,
            # return the central wavelength in the default units of meters
            output_units = 'meters'
        # The central_wavelength from nsappwave can only be obtained from data
        # that does not have an AstroData Type of IMAGE
        if 'IMAGE' not in dataset.types:
            # Get the focal plane mask and disperser values using the
            # appropriate descriptors
            focal_plane_mask = str(dataset.focal_plane_mask())
            disperser = str(dataset.disperser(stripID=True))
            if focal_plane_mask is None or disperser is None:
                # The descriptor functions return None if a value cannot be
                # found and stores the exception info. Re-raise the exception.
                # It will be dealt with by the CalculatorInterface.
                if hasattr(dataset, 'exception_info'):
                    raise dataset.exception_info
            # Get the central wavelength value from the nsappwave lookup
            # table
            count = 0
            for row in self.nsappwave.data:
                if focal_plane_mask == row.field('MASK') and \
                    disperser == row.field('GRATING'):
                    count += 1
                    if row.field('LAMBDA'):
                        raw_central_wavelength = float(row.field('LAMBDA'))
                    else:
                        raise Errors.TableValueError()
            if count == 0:
                raise Errors.TableKeyError()
            # Use the utilities function convert_units to convert the central
            # wavelength value from the input units to the output units
            ret_central_wavelength = \
                GemCalcUtil.convert_units(input_units=input_units, \
                input_value=float(raw_central_wavelength), \
                output_units=output_units)
        else:
            raise Errors.DescriptorTypeError()
        
        return ret_central_wavelength
    
    def data_section(self, dataset, pretty=False, **args):
        # Since this descriptor function accesses keywords in the headers of
        # the pixel data extensions, always return a dictionary where the key
        # of the dictionary is an (EXTNAME, EXTVER) tuple.
        ret_data_section = {}
        # Loop over the science extensions in the dataset
        for ext in dataset['SCI']:
            # Get the region of interest from the header of each pixel data
            # extension. The region of interest keywords are defined in the
            # local key dictionary (stdkeyDictNIRI) but is read from the
            # updated global key dictionary (globalStdkeyDict). The values
            # from the header use 0-based indexing.
            x_start = ext.getKeyValue(globalStdkeyDict['key_lowrow'])
            x_end = ext.getKeyValue(globalStdkeyDict['key_hirow'])
            y_start = ext.getKeyValue(globalStdkeyDict['key_lowcol'])
            y_end = ext.getKeyValue(globalStdkeyDict['key_hicol'])
            if x_start is None or x_end is None or y_start is None or \
                y_end is None:
                # The getKeyValue() function returns None if a value cannot be
                # found and stores the exception info. Re-raise the exception.
                # It will be dealt with by the CalculatorInterface.
                if hasattr(ext, 'exception_info'):
                    raise ext.exception_info
            if pretty:
                # Return a dictionary with the data section string that uses
                # 1-based indexing as the value. 
                data_section = '[%d:%d,%d:%d]' % (x_start + 1, x_end + 1, \
                    y_start + 1, y_end + 1)
                ret_data_section.update({(ext.extname(), \
                    ext.extver()):str(data_section)})
            else:
                # Return a dictionary with the data section tuple that uses
                # 0-based indexing as the value
                data_section = (x_start, x_end, y_start, y_end)
                ret_data_section.update({(ext.extname(), \
                    ext.extver()):data_section})
        
        return ret_data_section
    
    def disperser(self, dataset, stripID=False, pretty=False, **args):
        if pretty:
            stripID = True
        # Disperser can only ever be in key_filter3 because the other two
        # wheels are in an uncollimated beam. Get the key_filter3 filter name
        # value from the header of the PHU. The filter name keyword is defined
        # in the local key dictionary (stdkeyDictNIRI) but is read from the
        # updated global key dictionary (globalStdkeyDict)
        filter3 = dataset.phuGetKeyValue(globalStdkeyDict['key_filter3'])
        if filter3 is None:
            # The phuGetKeyValue() function returns None if a value cannot be
            # found and stores the exception info. Re-raise the exception. It
            # will be dealt with by the CalculatorInterface.
            if hasattr(dataset, 'exception_info'):
                raise dataset.exception_info
        # Check if the filter name contains the string 'grism'. If it does, set
        # the disperser to the filter name value
        if 'grism' in filter3:
            disperser = filter3
        else:
            # If the filter name value does not contain the string 'grism',
            # return MIRROR like GMOS
            disperser = 'MIRROR'
        if stripID and disperser is not 'MIRROR':
            # Return the disperser string with the component ID stripped
            ret_disperser = string.removeComponentID(disperser)
        else:
            # Return the disperser string
            ret_disperser = str(disperser)
        
        return ret_disperser
    
    def filter_name(self, dataset, stripID=False, pretty=False, **args):
        if pretty:
            # To match against the lookup table to get the pretty name, we
            # need the component IDs attached
            stripID = False
        # Get the three filter name values from the header of the PHU. The
        # three filter name keywords are defined in the local key dictionary
        # (stdkeyDictNIRI) but is read from the updated global key dictionary
        # (globalStdkeyDict)
        filter1 = dataset.phuGetKeyValue(globalStdkeyDict['key_filter1'])
        filter2 = dataset.phuGetKeyValue(globalStdkeyDict['key_filter2'])
        filter3 = dataset.phuGetKeyValue(globalStdkeyDict['key_filter3'])
        if filter1 is None or filter2 is None or filter3 is None:
            # The phuGetKeyValue() function returns None if a value cannot be
            # found and stores the exception info. Re-raise the exception. It
            # will be dealt with by the CalculatorInterface.
            if hasattr(dataset, 'exception_info'):
                raise dataset.exception_info
        if stripID:
            filter1 = string.removeComponentID(filter1)
            filter2 = string.removeComponentID(filter2)
            filter3 = string.removeComponentID(filter3)
        ##### Should this return a dictionary like GMOS?
        # Create list of filter values
        filters = [filter1, filter2, filter3]
        if pretty:
            # To match against the lookup table, the filter list must be sorted
            filters.sort()
            filter_name = self.filternameFrom(filters)
            if filter_name in self.niriFilternameMap:
                ret_filter_name = str(self.niriFilternameMap[filter_name])
            else:
                ret_filter_name = str(filter_name)
        else:
            ret_filter_name = str(self.filternameFrom(filters))
        
        return ret_filter_name
    
    def gain(self, dataset, **args):
        # Get the gain value from the lookup table
        if 'gain' in getattr(self, 'niriSpecDict'):
            gain = self.niriSpecDict['gain']
        else:
            raise Errors.TableKeyError()
        # Return the gain float
        ret_gain = float(gain)
        
        return ret_gain
    
    niriSpecDict = None
    
    def non_linear_level(self, dataset, **args):
        # Get the saturation level using the appropriate descriptor
        saturation_level = dataset.saturation_level()
        if saturation_level is None:
            # The descriptor functions return None if a value cannot be found 
            # and stores the exception info. Re-raise the exception. It will be
            # dealt with by the CalculatorInterface.
            if hasattr(dataset, 'exception_info'):
                raise dataset.exception_info
        # The array is non-linear at some fraction of the saturation level.
        # Get this fraction from the lookup table
        if 'linearlimit' in getattr(self, 'niriSpecDict'):
            linearlimit = self.niriSpecDict['linearlimit']
        else:
            raise Errors.TableKeyError()
        # Return the non linear level integer
        ret_non_linear_level = int(saturation_level * linearlimit)
        
        return ret_non_linear_level
    
    niriSpecDict = None
    
    def pixel_scale(self, dataset, **args):
        # Get the WCS matrix elements from the header of the PHU. The WCS
        # matrix elements keywords are defined in the local key dictionary
        # (stdkeyDictNIRI) but are read from the updated global key dictionary
        # (globalStdkeyDict)
        cd11 = dataset.phuGetKeyValue(globalStdkeyDict['key_cd11'])
        cd12 = dataset.phuGetKeyValue(globalStdkeyDict['key_cd12'])
        cd21 = dataset.phuGetKeyValue(globalStdkeyDict['key_cd21'])
        cd22 = dataset.phuGetKeyValue(globalStdkeyDict['key_cd22'])
        if cd11 is None or cd12 is None or cd21 is None or cd22 is None:
            # The phuGetKeyValue() function returns None if a value cannot be
            # found and stores the exception info. Re-raise the exception. It
            # will be dealt with by the CalculatorInterface.
            if hasattr(dataset, 'exception_info'):
                raise dataset.exception_info
        # Calculate the pixel scale using the WCS matrix elements
        pixel_scale = 3600 * \
            (math.sqrt(math.pow(cd11, 2) + math.pow(cd12, 2)) + \
            math.sqrt(math.pow(cd21, 2) + math.pow(cd22, 2))) / 2
        # Return the pixel scale float
        ret_pixel_scale = float(pixel_scale)
        
        return ret_pixel_scale
    
    def pupil_mask(self, dataset, stripID=False, pretty=False, **args):
        if pretty:
            stripID = True
        # Get the key_filter3 filter name value from the header of the PHU.
        # The filter name keyword is defined in the local key dictionary
        # (stdkeyDictNIRI) but is read from the updated global key dictionary
        # (globalStdkeyDict)
        filter3 = dataset.phuGetKeyValue(globalStdkeyDict['key_filter3'])
        if filter3 is None:
            # The phuGetKeyValue() function returns None if a value cannot be
            # found and stores the exception info. Re-raise the exception. It
            # will be dealt with by the CalculatorInterface.
            if hasattr(dataset, 'exception_info'):
                raise dataset.exception_info
        # Check if the filter name contains the string 'grism'. If it does, set
        # the disperser to the filter name value
        if filter3.startswith('pup'):
            pupil_mask = filter3
        else:
            # If the filter name value does not contain the string 'grism',
            # return MIRROR like GMOS
            pupil_mask = 'MIRROR'
        if stripID and pupil_mask is not 'MIRROR':
            # Return the pupil mask string with the component ID stripped
            ret_pupil_mask = string.removeComponentID(pupil_mask)
        else:
            # Return the pupil_mask string
            ret_pupil_mask = str(pupil_mask)
        
        return ret_pupil_mask
    
    def read_mode(self, dataset, **args):
        # Get the number of non-destructive read pairs (lnrs) and the number
        # of digital averages (ndavgs) from the header of the PHU. The lnrs and
        # ndavgs keywords are defined in the local key dictionary
        # (stdkeyDictNIRI) but are read from the updated global key dictionary
        # (globalStdkeyDict)
        lnrs = dataset.phuGetKeyValue(globalStdkeyDict['key_lnrs'])
        ndavgs = dataset.phuGetKeyValue(globalStdkeyDict['key_ndavgs'])
        if lnrs is None or ndavgs is None:
            # The phuGetKeyValue() function returns None if a value cannot be
            # found and stores the exception info. Re-raise the exception. It
            # will be dealt with by the CalculatorInterface.
            if hasattr(dataset, 'exception_info'):
                raise dataset.exception_info
        if lnrs == 16 and ndavgs == 16:
            read_mode = 'Low Background'
        elif lnrs == 1 and ndavgs == 16:
            read_mode = 'Medium Background'
        elif lnrs == 1 and ndavgs == 1:
            read_mode = 'High Background'
        else:
            read_mode = 'Invalid'
        ret_read_mode = str(read_mode)
        
        return ret_read_mode
    
    def read_noise(self, dataset, **args):
        # Get the read mode and the number of coadds using the appropriate
        # descriptors
        read_mode = dataset.read_mode()
        coadds = dataset.coadds()
        if read_mode is None or coadds is None:
            # The descriptor functions return None if a value cannot be found
            # and stores the exception info. Re-raise the exception. It will be
            # dealt with by the CalculatorInterface.
            if hasattr(dataset, 'exception_info'):
                raise dataset.exception_info
        # Use the value of the read mode to get the read noise from the lookup
        # table
        if read_mode == 'Low Background':
            key = 'lowreadnoise'
        if read_mode == 'High Background':
            key = 'readnoise'
        else:
            key = 'medreadnoise'
        if key in getattr(self, 'niriSpecDict'):
            read_noise = self.niriSpecDict[key]
        else:
            raise Errors.TableKeyError()
        # Return the read noise float
        ret_read_noise = float(read_noise * math.sqrt(coadds))
        
        return ret_read_noise
    
    niriSpecDict = None
    
    def saturation_level(self, dataset, **args):
        # Get the number of coadds, the gain and the well depth setting values
        # using the appropriate descriptors
        coadds = dataset.coadds()
        gain = dataset.gain()
        well_depth_setting = str(dataset.well_depth_setting())
        if coadds is None or gain is None or well_depth_setting is None:
            # The descriptor functions return None if a value cannot be found 
            # and stores the exception info. Re-raise the exception. It will be
            # dealt with by the CalculatorInterface.
            if hasattr(dataset, 'exception_info'):
                raise dataset.exception_info
        # Use the value of the well depth setting to get the well depth from
        # the lookup table
        if well_depth_setting == 'Shallow':
            key = 'shallowwell'
        if well_depth_setting == 'Deep':
            key = 'deepwell'
        if key in getattr(self, 'niriSpecDict'):
            well = self.niriSpecDict[key]
        else:
            raise Errors.TableKeyError()
        # Return the saturation level integer
        ret_saturation_level = int(well * coadds / gain)
        
        return ret_saturation_level
    
    niriSpecDict = None
    
    def well_depth_setting(self, dataset, **args):
        # Get the VDDUC and VDETCOM detector bias voltage post exposure
        # (avdduc and avdet, respectively) from the header of the PHU. The
        # avdduc and avdet keywords are defined in the local key dictionary
        # (stdkeyDictNIRI) but are read from the updated global key dictionary
        # (globalStdkeyDict)
        avdduc = dataset.phuGetKeyValue(globalStdkeyDict['key_avdduc'])
        avdet = dataset.phuGetKeyValue(globalStdkeyDict['key_avdet'])
        if avdduc is None or avdet is None:
            # The phuGetKeyValue() function returns None if a value cannot be
            # found and stores the exception info. Re-raise the exception. It
            # will be dealt with by the CalculatorInterface.
            if hasattr(dataset, 'exception_info'):
                raise dataset.exception_info
        biasvolt = avdduc - avdet
        shallowbias = self.niriSpecDict['shallowbias']
        deepbias = self.niriSpecDict['deepbias']
        if abs(biasvolt - shallowbias) < 0.05:
            well_depth_setting = 'Shallow'
        elif abs(biasvolt - deepbias) < 0.05:
            well_depth_setting = 'Deep'
        else:
            well_depth_setting = 'Invalid'
        # Return the well depth setting string
        ret_well_depth_setting = str(well_depth_setting)
        
        return ret_well_depth_setting
    
    ## UTILITY MEMBER FUNCTIONS (NOT DESCRIPTORS)
    
    def filternameFrom(self, filters, **args):
        
        # reject 'open' 'grism' and 'pupil'
        filters2 = []
        for filt in filters:
            filtlow = filt.lower()
            if 'open' in filtlow or 'grism' in filtlow or 'pupil' in filtlow:
                pass
            else:
                filters2.append(filt)
        
        filters = filters2
        
        # blank means an opaque mask was in place, which of course
        # blocks any other in place filters
        
        if 'blank' in filters:
            filtername = 'blank'
        elif len(filters) == 0:
            filtername = 'open'
        else:
            filters.sort()
            filtername = str('&'.join(filters))
        
        return filtername
    
    def makeFilternameMap(self, **args):
        filternamemap = {}
        for line in self.niriFilternameMapConfig:
            linefiltername = self.filternameFrom([line[1], line[2], line[3]])
            filternamemap.update({linefiltername:line[0]})
        self.niriFilternameMap = filternamemap
