#!/usr/bin/env python
#import time
#ost = time.time()
# ---PROFILER START to profile imports
#import hotshot
#importprof = hotshot.Profile("hotshot_edi_stats")
#------------------------------------------------------------------------------ 

from astrodata.adutils import terminal
from astrodata.adutils.terminal import TerminalController, ProgressBar 
import sys
# start color printing filter for xgtermc
REALSTDOUT = sys.stdout
REALSTDERR = sys.stderr
#filteredstdout = terminal.FilteredStdout()
#filteredstdout.addFilter( terminal.ColorFilter())
irafstdout = terminal.IrafStdout() #fout = filteredstdout)
#sys.stdout = filteredstdout
# sys.stderr = terminal.ColorStdout(REALSTDERR, term)
import commands
from datetime import datetime
import glob
from optparse import OptionParser
import os
#st = time.time()
if False:
    try:
        import pyraf
        from pyraf import iraf
    except:
        print "reduce: didn't find pyraf"
#et = time.time()
#print 'IRAF TIME', (et-st)
import subprocess
import sys
import time
import re
#------------------------------------------------------------------------------ 
a = datetime.now()

import astrodata
from astrodata import RecipeManager
from astrodata import Errors
from astrodata.AstroData import AstroData
from astrodata.AstroDataType import get_classification_library
from astrodata.RecipeManager import ReductionContext
from astrodata.RecipeManager import RecipeLibrary
from astrodata.RecipeManager import RecipeExcept
from astrodata.StackKeeper import StackKeeper
from astrodata.ReductionObjectRequests import CalibrationRequest,\
        UpdateStackableRequest, GetStackableRequest, DisplayRequest,\
        ImageQualityRequest
from astrodata import gdpgutil
# from astrodata.LocalCalibrationService import CalibrationService
# from astrodata.adutils.future import gemDisplay
from astrodata.adutils import paramutil
from astrodata.adutils.gemutil import gemdate

from astrodata import Proxies

#------------------------------------------------------------------------------ 
from astrodata.adutils import gemLog
#-----------------------------------------------------------------------------


#oet = time.time()
#print 'TIME:', (oet -ost)
b = datetime.now()


# GLOBAL/CONSTANTS (could be exported to config file)
cachedirs = [".reducecache",
             ".reducecache/storedcals",
             ".reducecache/storedcals/storedbiases",
             ".reducecache/storedcals/storeddarks",
             ".reducecache/storedcals/storedflats",
             ".reducecache/storedcals/storedfringes",
             ".reducecache/storedcals/retrievedbiases",
             ".reducecache/storedcals/retrieveddarks",
             ".reducecache/storedcals/retrievedflats",
             ".reducecache/storedcals/retrievedfringes",
             ".reducecache/retrievedcals"
             ]
CALDIR = ".reducecache/storedcals"
cachedict = {} # constructed below             
for cachedir in cachedirs:
    if not os.path.exists(cachedir):                        
        os.mkdir(cachedir)
    cachename = os.path.basename(cachedir)
    if cachename[0] == ".":
        cachename = cachename[1:]
    cachedict.update({cachename:cachedir})

############################################################
# this script was developed to exercise the GeminiDataType class
# but now serves a general purpose in addition to that and as
# a demo for GeminiData... see options documentation.

# parsing the command line
parser = OptionParser()
# parser.add_option("-r", "--reduce", dest="twdir", default =".",
#        help="Recursively walk given directory and put type information to stdout.")
version = '1_0'
parser.set_description( 
"""The standalone recipe processor from Gemini. Created by Craig Allen (callen@gemini.edu)."""
 )
parser.set_usage( parser.get_usage()[:-1] + " file.fits\n" )
# Testing
import pyfits as pf
parser.add_option("-r", "--recipe", dest="recipename", default=None,
                  help="Specify which recipe to run by name.")
parser.add_option("-p", "--param", dest="userparam", default = None,
                    help="""Set a parameter from the command line.\
The form '-p paramname=val' sets the param in the reduction
context such that all primitives will 'see' it.  The 
form '-p ASTROTYPE:primitivename:paramname=val' sets the
parameter such that it applies only when
the current reduction type (type of current reference image)
is 'ASTROTYPE' and the primitive is 'primitivename'.
Multiple settings can appear separated by commas, but
no whitespace in the setting, i.e. 'param=val,param2=val2',
not 'param=val, param2=val2'.""")
parser.add_option("-c", "--paramfile", dest = "paramfile", default = None,
                    help="Specify a parameter file.")
parser.add_option("-t", "--astrotype", dest = "astrotype", default = None,
                    help="To run a recipe based on astrotype, either to override the default type of the file, or to start a recipe without initial input (i.e. which begin with primitives that acquire dta).")
parser.add_option("-m", "--monitor", dest="bMonitor", action="store_true",
                  default = False,
                  help= "Open TkInter Window to Monitor Progress of" + \
                  "execution. " + \
                  "Note: One window is opened for each recipe which " + \
                  "will run")
parser.add_option("--addcal", dest="add_cal", default=None, type="string",
                  help="'--caltype' Must be specified as well when using this! " + \
                  "Provide the filename for a calibration. This is will overwrite " + \
                  "an existing calibration if in the index. An example of what " + \
                  "this would look like: \n" + \
                  "reduce --addcal=N2009_bias.fits --caltype=bias N20091002S0219.fits" )
parser.add_option("--remcal", dest="rem_cal", default=False, action="store_true",
                  help="'--caltype' Must be specified as well when using this! " + \
                  "This will remove the calibration for that file from cache. An " + \
                  "example of what this would look like: \n" + \
                  "reduce --remcal --caltype=bias N20091002S0219.fits" )
parser.add_option("--clrcal", dest="clr_cal", default=False, action="store_true",
                  help="Remove all calibrations.")
parser.add_option("--caltype", dest="cal_type", default=None, type="string",
                  help="Works in conjunction with '--addcal'. Ignored otherwise. " + \
                  "This should be the type of calibration in lowercase and one word. " + \
                  "For example: 'bias', 'twilight'.")
parser.add_option("--showcolors", dest="show_colors", default=False, action = "store_true",
                    help="""For debugging any color output problems, shows what colors
                    reduce thinks are available based on the terminal setting.""")
##@@FIXME: This next option should not be put into the package
parser.add_option("-x", "--rtf-mode", dest="rtf", default=False, action="store_true",
                  help="Only used for rtf.")
parser.add_option("-i", "--intelligence", dest='intelligence', default=False, action="store_true",
                  help="Give the system some intelligence to perform operations faster and smoother.")
parser.add_option("--force-width", dest = "forceWidth", default=None,
                  help="Use to force width of terminal for output purposes instead of using actual terminal width.")
parser.add_option("--force-height", dest = "forceHeight", default=None,
                  help="Use to force height of terminal for output purposes instead of using actual terminal height.")
parser.add_option("--addprimset", dest = "primsetname", default = None,
                  help="Use to add user supplied primitives to the reduction object.")
parser.add_option("--debug",dest='debug', default=False, action="store_true",
                  help="debug will set verbosity for console and log file to the extremely high developers debug level.")
parser.add_option("--logLevel",dest='logLevel', default=2, type='string',
                  help="logLevel will set the verbosity level for the console; Either the message type or its logLevel "+\
                  "integer equivalent,  0='none'=none, 6='fullinfo'=highest.")
parser.add_option("--logName",dest='logName', default='gemini.log', type='string',
                  help="name of log; default is 'gemini.log'.") 
parser.add_option("--noLogFile",dest='noLogFile', default=False, action="store_true",
                  help="Calling this flag will make it so no log file is created.")
parser.add_option("--logAllOff",dest='logAllOff', default=False, action="store_true",
                  help="Calling this flag will turn the logging completely off, no log file and no messages to the screen.")
parser.add_option("--writeInt",dest='writeInt', default=False, action="store_true",
                  help="writeInt (short for writeIntermediate) will set it so the outputs of" + \
                  "each primitive are written to disk rather than only at the end of the recipe. default=False."+ \
                  "(CURRENTLY THIS DOESN'T WORK)")       
parser.add_option("--invoked", dest="invoked", default=False, action="store_true")
          
(options,  args) = parser.parse_args()

useTK =  options.bMonitor
# ------
#$Id: recipeman.py,v 1.8 2008/08/05 03:28:06 callen Exp $
from astrodata.tkMonitor import *

adatadir = "./recipedata/"
calindfile = "./.reducecache/calindex.pkl"
stkindfile = "./.reducecache/stkindex.pkl"

terminal.forceWidth = options.forceWidth
terminal.forceHeight = options.forceHeight

if options.recipename == "USER":
    options.logLevel = 6

if options.invoked:
    options.logLevel = 6
    
#---------------------------- INSTANTIATING THE LOGGER FOR ALL TO SEE ----
log = gemLog.createGeminiLog(logName=options.logName,logLevel=options.logLevel, 
                             logType='main', debug=options.debug, 
                          noLogFile=options.noLogFile, allOff=options.logAllOff)
#-------------------------------------------------------------------------

if options.invoked:
    opener = "reduce started in adcc mode (--invoked)"
    log.status("."*len(opener))
    log.status(opener)
    log.status("."*len(opener))
    sys.stdout.flush()

def abortBadParamfile(lines):
    for i in range(0,len(lines)):
        log.error("  %03d:%s" % (i, lines[i]))
    log.error("  %03d:<<stopped parsing due to error>>" % (i+1))
    sys.exit(1)

def command_line():
    '''
    This function is just here so that all the command line oriented parsing is one common location.
    Hopefully, this makes things look a little cleaner.
    '''
    
    # this is done first because command line options can be set in the 
    # config file
    if options.paramfile:
        ups = []
        gparms = {}
        pfile = file(options.paramfile)
        astrotype = None
        primname = None
        cl = get_classification_library()
        
        i = 0
        lines = []
        for line in pfile:
            i += 1
            oline = line
            lines.append(oline)
            # strip comments
            line = re.sub("#.*?$", "", line)
            line = line.strip()
            
            # see if they are command options
            if len(line)>2 and line[:2] == "--":
                #then it's an option
                
                if "=" not in line:
                    opt = line
                    
                    option = parser.get_option(opt)
                    # note, it would do to not assume flags mean a true dest value
                    val = "True"
                else:
                    opt,val = line.split("=")

                # print "r204:",opt, val
                opt = opt.strip()
                val = val.strip()
                    
                if opt == "--files":
                    files = val.split()
                    args.extend(files)
                elif parser.has_option(opt):
                    option = parser.get_option(opt)
                    exec("options.%s=val" % str(option.dest))
            
            elif len(line)>0:
                if "]" in line:
                    # then line is a header
                    name = re.sub("[\[\]]", "", line)
                    name = name.strip()
                    if len(name)== 0:
                        astrotype = None
                        primname = None
                    elif cl.is_name_of_type(name):
                        astrotype = name
                    else:
                        primname = name
                else:
                    # not a section
                    keyval = line.split("=")
                    if len(keyval)<2:
                        log.error("$Badly formatted parameter file (%s)" \
                              "\n  Line #%d: %s""" % (options.paramfile, i, oline))
                        abortBadParamfile(lines)
                        sys.exit(1)
                    key = keyval[0].strip()
                    val = keyval[1].strip()
                    if val[0] == "'" or val[0] == '"':
                        val = val[1:]
                    if val[-1] == "'" or val[-1] == '"':
                        val = val[0:-1]
                    if primname and not astrotype:
                        log.error("Badly formatted parameter file (%s)" \
                              '\n  The primitive name is set to "%s", but the astrotype is not set' \
                              "\n  Line #%d: %s" % (options.paramfile, primname, i, oline[:-1]))
                        
                        abortBadParamfile(lines)
                    if not primname and astrotype:
                        log.error("Badly formatted parameter file (%s)" \
                              '\n  The astrotype is set to "%s", but the primitive name is not set' \
                              "\n  Line #%d: %s" % (options.paramfile, astrotype, i, oline))
                        abortBadParamfile(lines)
                    if not primname and not astrotype:
                        gparms.update({key:val})
                    else:
                        up = RecipeManager.UserParam(astrotype, primname, key, val)
                        ups.append(up)
                        
        # parameter file ups and gparms                                
        pfups = ups
        pfgparms = gparms
        
    if  options.show_colors:
        print dir(filteredstdout.term)
        sys.exit(0)
    infile = None
    
    if options.clr_cal:
        clrFile = None
        
        co = ReductionContext()
        co.restore_cal_index(calindfile)
        co.calibrations = {}
        co.persist_cal_index( calindfile )
        log.status("Calibration cache index cleared")
        import shutil
        
        if os.path.exists(CALDIR):
            shutil.rmtree(CALDIR)
        log.status("Calibration directory removed")
        
        sys.exit(0)
    
    try:
        if len( args ) == 0 and options.astrotype == None:
            raise IndexError()
        infile   = args
    except IndexError:
        log.info("When no filename is given the astrotype must be specified"
                    "(-t or --astrotype). This is needed in order to load"
                    "correct recipes and primitive sets.")
        log.error("NO INPUT FILE or ASTROTYPE specified")
        log.info("type 'reduce -h' for usage information")
        sys.exit(1)
    
    
    input_files = []
    badList = []
    for inf in infile:
        
        #"""
        # checkImageParam allows the argument to be an @list, turns it
        # into a list of filenames as otherwise expected from the command line
        tmpInp = paramutil.checkImageParam( inf )
        if tmpInp == None:
            badList.append(inf)
        else:
            # extend the list of input files with contents of @ list
            input_files.extend( tmpInp )

    if len(badList)>0:
        err = "\n\t".join(badList)
        log.error("Some files not found or can't be loaded:\n\t"+err)
        log.error("Exiting due to missing datasets.")
        if len(input_files ) > 0:
            found = "\n\t".join(input_files)
            log.info("These datasets were found and loaded:\n\t"+found)
        sys.exit(1)

    # print "r161:", input_files
        
    if options.add_cal != None:
        if options.cal_type == None:
            print "Reduce requires a calibration type. Use --caltype. For more " + \
            "information use '-h' or '--help'."
            sys.exit(1)
        elif not os.access( options.add_cal, os.R_OK ):
            print "'" + options.add_cal + "' does not exist or cannot be accessed."
            sys.exit(1)
        
        # @@TODO: Perhaps need a list of valid calibration types.
        # @@TODO: Need testing if passed in calibration type is valid.
        
        co = ReductionContext()
        co.restore_cal_index(calindfile)
        for arg in infile:

            co.add_cal( AstroData(arg), options.cal_type, os.path.abspath(options.add_cal) )
        co.persist_cal_index( calindfile )
        print "'" + options.add_cal + "' was successfully added for '" + str(input_files) + "'."
        #sys.exit(0)
        
    elif options.rem_cal:
        if options.cal_type == None:
            print "Reduce requires a calibration type. Use --caltype. For more " + \
            "information use '-h' or '--help'."
            sys.exit(1)
        
        # @@TODO: Perhaps need a list of valid calibration types.
        # @@TODO: Need testing if passed in calibration type is valid.

        co = ReductionContext()
        co.restore_cal_index(calindfile)
        for arg in infile:
            try:
                co.rm_cal( arg, options.cal_type )
            except:
                print arg + ' had no ' + options.cal_type
        print "'" + options.cal_type + "' was removed from '" + str(input_files) + "'."
        co.persist_cal_index( calindfile )
        sys.exit(0)
        
    # parameters from command line and/or parameter file
    clups = []
    clgparms = {}
    pfups = []
    pfgparms = {}
    
    if options.userparam:
        ups = []
        gparms = {}
        allupstr = options.userparam
        allparams = allupstr.split(",")
        for upstr in allparams:
            tmp = upstr.split("=")
            spec = tmp[0].strip()
            # @@TODO: check and convert to correct type
            val = tmp[1].strip()
            
            if ":" in spec:
                typ,prim,param = spec.split(":")
                up = RecipeManager.UserParam(typ, prim, param, val)
                ups.append(up)
            else:
                gparms.update({spec:val})
        # command line ups and gparms
        clups = ups
        clgparms = gparms
        
    fups = RecipeManager.UserParams()
    for up in clups:
        fups.add_user_param(up)
    for up in pfups:
        fups.add_user_param(up)
    options.user_params = fups
    options.globalParams = {}
    options.globalParams.update(clgparms)
    options.globalParams.update(pfgparms)
    
    return input_files

from astrodata import Proxies
# I think it best to start the adcc always, since it wants the reduceServer I prefer not
# to provide to every component that wants to use the adcc as an active-library
adccpid = Proxies.start_adcc()
  
# launch xmlrpc interface for control and communication
reduceServer = Proxies.ReduceServer()
prs = Proxies.PRSProxy.get_adcc(reduce_server=reduceServer)

usePRS = True

# print "r395: usePRS=", usePRS

# called once per substep (every yeild in any primitive when struck)
# registered with the reduction object
# !!!! we import this from ReductionObjects.py now
from astrodata.ReductionObjects import command_clause

######################
######################
######################
# END MODULE FUNCTIONS
# START SCRIPT
######################
######################
######################

# get RecipeLibrary
rl = RecipeLibrary()

try:
    allinputs = command_line()
except:
    print "command_line() parsing failed."
    reduceServer.finished=True
    sys.stdout.flush()
    sys.stderr.flush()
    raise

generate_pycallgraphs = False
if (generate_pycallgraphs):
    import pycallgraph
    pycallgraph.start_trace()

if options.intelligence:
    typeIndex = gdpgutil.cluster_types( allinputs )
    # If there was super intelligence, it would determine ordering. For now, it will 
    # run recipes in simple ordering, (i.e. the order values() is returned in).
    allinputs = typeIndex.values()
else:
    nl = []
    for inp in allinputs:
        try:
            ad = AstroData(inp, mode="update")
            nl.append(ad)
        except:
            # note: should we raise an exception here?
            err = "Can't Load Dataset: %s" % inp
            log.warning(err)
            
    # note: this clause might be best placed elsewhere (earlier)
    if len(nl) == 0:
        log.warning("No files...")
        allinputs = [None]
    else:
        allinputs = [nl]
    

#===============================================================================
# Local PRS Components
#===============================================================================
# Local Calibration Service Setup
# cs = CalibrationService() # is this used anymore, don't think so...

# Local Display Service Setup
# ds = gemDisplay.getDisplayService()

numReductions = len(allinputs)
i = 1
for infiles in allinputs: #for dealing with multiple sets of files.
    #print "r232: profiling end"
    #prof.close()
    #raise "over"

    log.info("Starting Reduction #%d of %d" % (i, numReductions))
    if infiles:
        for infile in infiles:
            log.info("    %s" % (infile.filename))
    currentReductionNum = i
    i += 1
    
    # get ReductionObject for this dataset
    #ro = rl.retrieve_reduction_object(astrotype="GMOS_IMAGE") 
    # can be done by filename
    #@@REFERENCEIMAGE: used to retrieve/build correct reduction object
    try:
        if (options.astrotype == None):
            ro = rl.retrieve_reduction_object(infiles[0]) 
        else:
            ro = rl.retrieve_reduction_object(astrotype = options.astrotype)
    except:
        reduceServer.finished=True
        try:
            prs.unregister()
        except:
            log.warning("Trouble unregistering from adcc shared services.")
        raise

    # add command clause
    ro.register_command_clause(command_clause)
    if options.recipename == None:
        if options.astrotype == None:
            reclist = rl.get_applicable_recipes(infiles[0]) #**
            recdict = rl.get_applicable_recipes(infiles[0], collate=True) #**
        else:
            reclist = rl.get_applicable_recipes(astrotype = options.astrotype)
            recdict = rl.get_applicable_recipes(astrotype = options.astrotype, collate = True)
    else:
        #force recipe
        reclist = [options.recipename]
        recdict = {"all": [options.recipename]}
    
    # @@REFERENCEIMAGE
    # first file in group is used as reference
    # for the types that are used to load the recipe and primitives
    
    if (options.astrotype == None):
        types = infiles[0].get_types()
    else:
        types = [options.astrotype]
            
    infilenames = []
    if infiles:
        for infs in infiles:
            if type(infs) == AstroData:
                infilenames.append( infs.filename )
            else:
                # I don't think this can happen now
                # where the input files are still strings at this point
                infilenames.append( infs )
                raise "not expected to happen"

    numi = len(infilenames) 

    if numi < 1:
        title = "  No Datasets  "
    elif numi == 1:        
        title = "  Processing dataset: %s  " % (str(infilenames[0])) #**
    else:
        title = "  Processing datasets:"
        for infiln in infilenames:
            title += "\n    %s" % infiln
    tl = len(title)
    tb = " " * tl
    log.info(tb)
    log.info(title)
    log.info(tb)
    if options.recipename == None:
        if len(recdict) == 0:
            log.error("No recipes found")
            sys.exit(1)
        else:
            log.info("Recipe(s) found by dataset type:")
    else:
        log.info("A recipe was specified:")

    for typ in recdict.keys():
        recs = recdict[typ]
        log.info("  for type: %s" % typ)
        for rec in recs:
            log.info("    %s" % rec)
    
    bReportHistory = False
    cwlist = []
    if (useTK and currentReductionNum == 1):
        cw = TkRecipeControl(recipes = reclist)
        cw.start()
        
    if "USER" in reclist:
        interactiveMode = True
        import readline
        readline.set_history_length(100)
    else:
        interactiveMode = False

    # counts user given command for interactive mode
    cmdnum = 0 # @@INTERACTIVE
    co = None
    while True: # THIS IS A LOOP FOR INTERACTIVE USE! @@INTERACTIVE
        for rec in reclist:
            if rec == "USER":
                try:
                    rec = raw_input("reduce: ")
                    rec = rec.strip()
                    if rec == "exit":
                        interactiveMode = False
                        break
                    if rec.strip() == "":
                        continue
                    cmdnum += 1
                    rawrec = True
                    if rec == "reset":
                        co = None
                        continue
                except:
                    interactiveMode = False
                    break
            else:
                rawrec = False
                
            try:
                if co == None or not interactiveMode:
                    #then we want to keep the 
                    # create fresh context object
                    # @@TODO:possible: see if deepcopy can do this better 
                    co = ReductionContext()
                    if options.rtf:
                        co.update({"rtf":True})
                    #print "r739:stack index file", stkindfile
                    # @@NAME: stackIndexFile, location for persistent stack list cache
                    co.set_cache_file("stackIndexFile", stkindfile)
                    co.ro = ro
                    # @@DOC: put cachedirs in context
                    for cachename in cachedict:
                        co.update({cachename:cachedict[cachename]})
                    co.update({"cachedict":cachedict})
                    # rc.["storedcals"] will be the proper directory

                    co.restore_cal_index(calindfile)
                    # old local stack stuff co.restore_stk_index( stkindfile )

                    # add input files
                    if infiles:
                        #co.add_input(infiles)
                        co.populate_stream(infiles)
                    co.set_iraf_stdout(irafstdout)
                    co.set_iraf_stderr(irafstdout)

                   # odl way rl.retrieve_parameters(infile[0], co, rec)
                    if hasattr(options, "user_params"):
                        co.user_params = options.user_params
                    if hasattr(options, "globalParams"):
                        for pkey in options.globalParams.keys():
                            co.update({pkey:options.globalParams[pkey]})

                if (options.writeInt == True):       #$$$$$ to be removed after writeIntermediate thing works correctly
                        co.update({"writeInt":True})  #$$$$$ to be removed after writeIntermediate thing works correctly
                        
                 
                # Putting the log level and log name set with the --logLevel 
                # and --logName parser options into the global dict
                # for use throughout the primitives.
                co.update({'logLevel':options.logLevel}) #$$$$$$$$$ right place to do this??    
                co.update({'logName':options.logName}) #$$$$$$$$$ right place to do this??      
                co.update({'logType':'main'})        #$$$$$$$$$ right place to do this?? SHould we make this param more global?
                # print "r352:", repr(co.user_params.user_param_dict)
                if (useTK):
                    while cw.bReady == False:
                        # this is hopefully not really needed
                        # did it to give the tk thread a chance to get running
                        time.sleep(.1)
                    cw.new_control_window(rec,co)
                    cw.mainWindow.protocol("WM_DELETE_WINDOW", co.finish) 


                # @@TODO:evaluate use of init for each recipe vs. for all recipes
                ro.init(co)
                if options.primsetname != None:
                    dr = os.path.abspath(os.path.dirname(options.primsetname))
                    # print "r349:", dr
                    sys.path.append(dr)
                    # print "r351:", sys.path

                    exec ("import "+ os.path.basename(options.primsetname)[:-3] + " as newmodule")
                    userPrimSet = newmodule.userPrimSet

                    userPrimSet.astrotype = ro.curPrimType
                    ro.add_prim_set(userPrimSet)


                if rawrec == False:
                    log.info( "running recipe: '%s'\n" % rec)
                    
                # logic to handle:
                #  * recipes in config path somewhere
                #  * filenames
                #  * which need compiling due to arguments
                if (os.path.exists(rec)):
                    if "recipe." not in rec:
                        raise "Recipe files must be named 'recipe.RECIPENAME'"
                    else:
                        rname = re.sub("recipe.", "", os.path.basename(rec))
                    rf = open(rec)
                    rsrc = rf.read()
                    prec = rl.compose_recipe(rname, rsrc)
                    rfunc = rl.compile_recipe(rname, prec)
                    ro = rl.bind_recipe(ro, rname, rfunc)
                    rec = rname
                elif "(" in rec:
                    # print "r819:", rec
                    rsrc = rec
                    rname = "userCommand%d" % cmdnum
                    prec = rl.compose_recipe(rname, rsrc)
                    # log.debug(prec)
                    rfunc = rl.compile_recipe(rname, prec)
                    ro = rl.bind_recipe(ro, rname, rfunc)
                    rec = rname
                else:
                    if options.astrotype:
                        rl.load_and_bind_recipe(ro, rec, astrotype=options.astrotype)
                    else:
                        rl.load_and_bind_recipe(ro,rec, dataset=infile[0])
                if (useTK):
                    cw.running(rec)

                controlLoopCounter = 1
                ################
                # CONTROL LOOP #
                ################
                #print str(dir(TerminalController))
                #@@COLOR primfilter = terminal.PrimitiveFilter()
                primfilter = None
                #@@COLOR filteredstdout.addFilter(primfilter)
                frameForDisplay = 1
                #######
                #######
                #######
                #######
                ####### COMMAND LOOP
                #######
                #######
                #######
                # not this only works because we install a stdout filter right away with this
                # member function
                if (True): # try:
                    ro.run(rec, co)
                    #for coi in ro.substeps(rec, co):
                    #    ro.execute_command_clause()
                        # filteredstdout.addFilter(primfilter)
                    # filteredstdout.removeFilter(primfilter)
                #######
                #######
                #######
                #######
                #######
                #######
            except KeyboardInterrupt:
                co.is_finished(True)
                if (useTK):
                    cw.quit()
                co.persist_cal_index(calindfile)
                print "Ctrl-C Exit"
                prs.unregister()
                sys.exit(0)
            except astrodata.ReductionObjects.ReductionExcept, e:
                log.error("FATAL:" + str(e))
                prs.unregister()
                sys.exit()
            except:
                log.fullinfo("CONTEXT AFTER FATAL ERROR")
                log.fullinfo("-------------------------")
                log.debug(co.report(showall=True))
                if reduceServer:
                    #print "r855:", str(id(Proxies.reduceServer)), repr(Proxies.reduceServer.finished)
                    Proxies.reduceServer.finished=True
                co.persist_cal_index(calindfile)
                if (bReportHistory):
                    co.report_history()
                    rl.report_history()
                co.is_finished(True)
                if (useTK):
                    cw.killed = True
                    cw.quit()
                co.persist_cal_index(calindfile)
                
                # RAISE THE EXCEPTION AGAIN
                if interactiveMode != True:
                    # note, I expect this raise to produce
                    # an exit and print of stack to user!
                    # which is why I unregister... interactive mode
                    # does not want to unregister while still
                    # looping
                    prs.unregister()
                    raise
                else:
                    import traceback
                    traceback.print_exc()
                    print "\n Type 'exit' to exit."
                    
            co.persist_cal_index(calindfile)

            if (bReportHistory):

                log.error( "CONTEXT HISTORY")
                log.error( "---------------")

                co.report_history()
                rl.report_history()

            co.is_finished(True)
        if interactiveMode == True:
            reclist = ["USER"]
        else:
            break
        
        
    if useTK and currentReductionNum == numReductions:
        try:
            cw.done()
            cw.mainWindow.after_cancel(cw.pcqid)
            if True: #cw.killed == True:
                raw_input("Press Enter to Close Monitor Windows:")
            # After ID print cw.pcqid
            cw.mainWindow.quit()
        except:
            cw.mainWindow.quit()    
            raise
            
    if (generate_pycallgraphs):
        pycallgraph.make_dot_graph("recipman-callgraph.png")
    
    from time import sleep
    while (False):
        for th in threading.enumerate():
            print str(th)
        sleep(5.)
    # print co.report_history()
    # main()
    # don't leave the terminal in another color/mode, that's rude
    
reduceServer.finished=True
try:
    prs.unregister()
except:
    log.warning("Trouble unregistering from adcc shared services.")
    raise
