# This parameter file contains the parameters related to the primitives located
# in the primitives_GMOS_IMAGE.py file, in alphabetical order.
{"makeFringe":{
    "subtract_median_image":{
        "default"       : None,
        "type"          : "bool",
        "recipeOverride": True,
        "userOverride"  : True,
        "uiLevel"       : "UIBASIC",
        },
    },
 "makeFringeFrame":{
    "suffix":{
        "default"       : "_fringe",
        "type"          : "str",
        "recipeOverride": True,
        "userOverride"  : True,
        "uiLevel"       : "UIBASIC",
        },
    "operation":{
        "default"       : "median",
        "type"          : "str",
        "recipeOverride": True,
        "userOverride"  : True,
        "uiLevel"       : "UIBASIC",
        },
    "reject_method":{
        "default"       : "avsigclip",
        "type"          : "str",
        "recipeOverride": True,
        "userOverride"  : True,
        "uiLevel"       : "UIBASIC",
        },
    "subtract_median_image":{
        "default"       : True,
        "type"          : "bool",
        "recipeOverride": True,
        "userOverride"  : True,
        "uiLevel"       : "UIBASIC",
        },
    },
 "normalizeFlat":{
    "suffix":{
        "default"       : "_normalized",
        "type"          : "str",
        "recipeOverride": True,
        "userOverride"  : True,
        "uiLevel"       : "UIBASIC",
        },
    },
 "removeFringe":{
    "suffix":{
        "default"       : "_fringeCorrected",
        "type"          : "str",
        "recipeOverride": True,
        "userOverride"  : True,
        "uiLevel"       : "UIBASIC",
        },
    "fringe":{
        # No type defined here so that user can pass
        # a string (eg. from command line) or an astrodata
        # instance (eg. from a script)
        "default"       : None,
        "recipeOverride": True,
        "userOverride"  : True,
        "uiLevel"       : "UIBASIC",
        },
    "stats_scale":{
        "default"       : False,
        "type"          : "bool",
        "recipeOverride": True,
        "userOverride"  : True,
        "uiLevel"       : "UIBASIC",
        },
    },
 "scaleByIntensity":{
    "suffix":{
        "default"       : "_scaled",
        "type"          : "str",
        "recipeOverride": True,
        "userOverride"  : True,
        "uiLevel"       : "UIBASIC",
        },
    },
 "stackFlats":{
    "suffix":{
        "default"       : "_stack",
        "type"          : "str",
        "recipeOverride": True,
        "userOverride"  : True,
        "uiLevel"       : "UIBASIC",
        },
    "mask":{
        "default"       : True,
        "type"          : "bool",
        "recipeOverride": True,
        "userOverride"  : True,
        "uiLevel"       : "UIBASIC",
        }, 
    "operation":{
        "default"       : "median",
        "type"          : "str",
        "recipeOverride": True,
        "userOverride"  : True,
        "uiLevel"       : "UIBASIC",
        },
    "reject_method":{
        "default"       : "minmax",
        "type"          : "str",
        "recipeOverride": True,
        "userOverride"  : True,
        "uiLevel"       : "UIBASIC",
        },
    },
# The standardizeStructure primitive is actually located in the
# primtives_GMOS.py file, but the attach_mdf parameter should be set to False
# as default for data with an AstroData Type of IMAGE.
 "standardizeStructure":{
    "suffix":{
        "default"       : "_structureStandardized",
        "type"          : "str",
        "recipeOverride": True,
        "userOverride"  : True,
        "uiLevel"       : "UIBASIC",
        },
    "attach_mdf":{
        "default"       : False,
        "type"          : "bool",
        "recipeOverride": True,
        "userOverride"  : True,
        "uiLevel"       : "UIBASIC",
        },
    },
 "storeProcessedFringe":{
    "suffix":{
        "default"       : "_fringe",
        "type"          : "str",
        "recipeOverride": True,
        "userOverride"  : True,
        "uiLevel"       : "UIBASIC",
        },
    }, 
}
