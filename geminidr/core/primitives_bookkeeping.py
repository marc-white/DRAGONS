#
#                                                                  gemini_python
#
#                                                      primitives_bookkeeping.py
# ------------------------------------------------------------------------------
import astrodata
import gemini_instruments

from gempy.gemini import gemini_tools as gt

from geminidr import PrimitivesBASE
from geminidr import save_cache, stkindfile

from .parameters_bookkeeping import ParametersBookkeeping

from recipe_system.utils.decorators import parameter_override

# ------------------------------------------------------------------------------
@parameter_override
class Bookkeeping(PrimitivesBASE):
    """
    This is the class containing all of the preprocessing primitives
    for the Bookkeeping level of the type hierarchy tree. It inherits all
    the primitives from the level above
    """
    tagset = None

    def __init__(self, adinputs, **kwargs):
        super(Bookkeeping, self).__init__(adinputs, **kwargs)
        self.parameters = ParametersBookkeeping

    def addToList(self, adinputs=None, purpose=None, **params):
        """
        This primitive will update the lists of files to be stacked
        that have the same observationID with the current inputs.
        This file is cached between calls to reduce, thus allowing
        for one-file-at-a-time processing.

        Parameters
        ----------
        purpose: str (None => "list")
            purpose/name of this list, used as suffix for files
        """
        log = self.log
        if purpose is None:
            purpose = ''
        suffix = '_{}'.format(purpose) if purpose else '_list'

        # Update file names and write the files to disk to ensure the right
        # version is stored before adding it to the list.
        for ad in adinputs:
            ad.update_filename(suffix=suffix, strip=True)
            log.stdinfo("Writing {} to disk".format(ad.filename))
            # Need to specify 'ad.filename' here so writes to current dir
            ad.write(ad.filename, clobber=True)
            try:
                if ad.filename not in self.stacks[_stackid(purpose, ad)]:
                    self.stacks[_stackid(purpose, ad)].append(ad.filename)
            except KeyError:
                # Stack doesn't exist yet, so start it off...
                self.stacks[_stackid(purpose, ad)] = [ad.filename]

        save_cache(self.stacks, stkindfile)
        return adinputs

    def clearAllStreams(self, adinputs=None, **params):
        """
        This primitive clears all streams (except "main") by setting them
        to empty lists.
        """
        log = self.log
        for stream in self.streams.keys():
            if stream != 'main':
                log.fullinfo('Clearing stream {}'.format(stream))
                self.streams[stream] = []
        return adinputs

    def clearStream(self, adinputs=None, **params):
        """
        This primitive clears a stream by returning an empty list, which the
        decorator then pushes into the stream.
        """
        log = self.log
        log.fullinfo('Clearing stream {}'.format(params.get('stream', 'main')))
        return []

    def getList(self, adinputs=None, **params):
        """
        This primitive will check the files in the stack lists are on disk,
        and then update the inputs list to include all members that belong
        to the same stack(s) as the input(s).

        Parameters
        ----------
        purpose: str
            purpose/name of list to access
        max_frames: int
            maximum number of frames to return
        """
        log = self.log
        purpose = params["purpose"]
        if purpose is None:
                purpose = ''
        # Make comparison checks easier if there's no limit
        max_frames = params['max_frames'] or 1000000

        # Since adinputs takes priority over cached files, can exit now
        # if we already have enough/too many files.
        if len(adinputs) >= max_frames:
            del adinputs[max_frames:]
            log.stdinfo("Input list is longer than/equal to max_frames. "
                        "Returning the following files:")
            for ad in adinputs:
                log.stdinfo("   {}".format(ad.filename))
            return adinputs

        # Get ID for all inputs; want to preserve order of stacking lists
        sid_list = []
        for ad in adinputs:
            sid = _stackid(purpose, ad)
            if sid not in sid_list:
                sid_list.append(sid)

        # Import inputs from all lists
        for sid in sid_list:
            stacklist = self.stacks[sid]
            log.stdinfo("List for stack id {}(...):".format(sid[:35]))
            # Add each file to adinputs if not already there and there's room
            for f in stacklist:
                if f not in [ad.filename for ad in adinputs]:
                    if len(adinputs) < max_frames:
                        try:
                            adinputs.append(astrodata.open(f))
                            log.stdinfo("   {}".format(f))
                        except IOError:
                            log.stdinfo("   {} NOT FOUND".format(f))
                else:
                    log.stdinfo("   {}".format(f))
        return adinputs

    def selectFromInputs(self, adinputs=None, **params):
        """
        Selects frames whose tags match any one of a list of supplied tags.
        The user is likely to want to redirect the output list.

        Parameters
        ----------
        tags: str/list
            Tags which frames must match to be selected
        """
        required_tags = params.get("tags") or []
        if isinstance(required_tags, str):
            required_tags = required_tags.split(',')

        # This selects AD that match *all* the tags. While possibly the most
        # natural, one can achieve this by a series of matches to each tag
        # individually. There is, however, no way to combine lists produced
        # this way to create one as if produced by matching *any* of the tags.
        # Hence a match to *any* tag makes more sense as the implementation.
        #adoutputs = [ad for ad in adinputs
        #             if set(required_tags).issubset(ad.tags)]
        adoutputs = [ad for ad in adinputs if set(required_tags) & ad.tags]
        return adoutputs

    def showInputs(self, adinputs=None, **params):
        """
        A simple primitive to show the filenames for the current inputs to
        this primitive.
        
        Parameters
        ----------
        purpose: str
            Brief description for output
        """
        log = self.log
        purpose = params["purpose"] or "primitive"
        log.stdinfo("Inputs for {}".format(purpose))
        for ad in adinputs:
            log.stdinfo("  {}".format(ad.filename))
        return adinputs

    showFiles = showInputs

    def showList(self, adinputs=None, purpose=None, **params):
        """
        This primitive will log the list of files in the stacking list matching
        the current inputs and 'purpose' value.

        Parameters
        ----------
        purpose: str
            purpose/name of list
        """
        log = self.log
        sidset = set()
        if purpose == 'all':
            [sidset.add(sid) for sid in self.stacks]
        else:
            if purpose is None:
                purpose = ''
            [sidset.add(_stackid(purpose, ad)) for ad in adinputs]
        for sid in sidset:
            stacklist = self.stacks.get(sid, [])
            log.status("List for stack id={}".format(sid))
            if len(stacklist) > 0:
                for f in stacklist:
                    log.status("   {}".format(f))
            else:
                log.status("No datasets in list")
        return adinputs

    def transferAttribute(self, adinputs=None, source=None, attribute=None):
        """
        This primitive takes an attribute (e.g., "mask", or "OBJCAT") from
        the AD(s) in another ("source") stream and applies it to the ADs in
        this stream. There must be either the same number of ADs in each
        stream, or only 1 in the source stream.
        
        Parameters
        ----------
        source: str
            name of stream containing ADs whose attributes you want
        attribute: str
            attribute to transfer from ADs in other stream
        """
        log = self.log

        if source is None:
            log.info("No source stream specified so nothing to transfer")
            return adinputs

        if attribute is None:
            log.info("No attribute specified so nothing to transfer")
            return adinputs

        if source not in self.streams.keys():
            log.info("Stream {} does not exist so nothing to transfer".format(source))
            return adinputs

        source_length = len(self.streams[source])
        if not (source_length == 1 or source_length == len(adinputs)):
            log.warning("Incompatible stream lengths: {} and {}".
                        format(len(adinputs), source_length))
            return adinputs

        # Keep track of whether we find anything to transfer, as failing to
        # do so might indicate a problem and we should warn the user
        found = False
        for ad1, ad2 in zip(*gt.make_lists(adinputs, self.streams[source])):
            # Attribute could be top-level or extension-level
            if hasattr(ad2, attribute):
                try:
                    setattr(ad1, attribute, getattr(ad2, attribute))
                except ValueError:  # data, mask, are gettable not settable
                    pass
                else:
                    found = True
                    continue
            for ext1, ext2 in zip(ad1, ad2):
                if hasattr(ext2, attribute):
                    setattr(ext1, attribute, getattr(ext2, attribute))
                    found = True

        if not found:
            log.warning("Did not find any {} attributes to transfer".format(attribute))

        return adinputs

    def writeOutputs(self, adinputs=None, **params):
        """
        A primitive that may be called by a recipe at any stage to
        write the outputs to disk.
        If suffix is set during the call to writeOutputs, any previous
        suffixes will be striped and replaced by the one provided.
        examples:
        writeOutputs(suffix= '_string'), writeOutputs(prefix= '_string')
        or if you have a full file name in mind for a SINGLE file being
        ran through Reduce you may use writeOutputs(outfilename='name.fits').

        Parameters
        ----------
        strip: bool
            strip the previous suffix off file name?
        clobber: bool
            overwrite existing files?
        suffix: str
            new suffix to append to output files
        prefix: str
            new prefix to prepend to output files
        outfilename: str
            new filename (applicable only if there's one file to be written)
        """
        log = self.log
        sfx = params['suffix']
        pfx = params['prefix']
        log.fullinfo("suffix = {}".format(sfx))
        log.fullinfo("prefix = {}".format(pfx))

        for ad in adinputs:
            if sfx or pfx:
                ad.update_filename(prefix=pfx, suffix=sfx, strip=params["strip"])
                log.fullinfo("File name updated to {}".format(ad.filename))
                outfilename = ad.filename
            elif params['outfilename']:
                # Check that there is not more than one file to be written
                # to this file name, if so throw exception
                if len(adinputs) > 1:
                    message = "More than one file was requested to be " \
                              "written to the same name {}".format(
                        params['outfilename'])
                    log.critical(message)
                    raise IOError(message)
                else:
                    outfilename = params['outfilename']
            else:
                # If no changes to file names are requested then write inputs
                # to their current file names
                outfilename = ad.filename
                log.fullinfo("not changing the file name to be written "
                             "from its current name")

            # Finally, write the file to the name that was decided upon
            log.stdinfo("Writing to file {}".format(outfilename))
            ad.write(outfilename, clobber=params["clobber"])
        return adinputs

# Helper function to make a stackid, without the IDFactory nonsense
def _stackid(purpose, ad):
    return (purpose + ad.group_id()).replace(' ', '_')
