"""
Recipes available to data with tags ['GMOS', 'NODANDSHUFFLE']
Default is "reduce".
"""
recipe_tags = set(['GMOS', 'NODANDSHUFFLE'])
# once we have LS, MOS, and IFU recipes, we might need the following set
# instead to maximize the match.
# recipe_tags = {'GMOS', 'MOS', 'IFU', 'LS', 'NODANDSHUFFLE'}

def reduce(p):
    """
    This recipe does a quick reduction of GMOS nod and shuffle data.
    The data is left in its 2D form, and only a sky correction is done.
    The seeing from the spectra cross-section is measured when possible.

    Parameters
    ----------
    p : PrimitivesCORE object
        A primitive set matching the recipe_tags.
    """
    p.prepare()
    p.addDQ()
    p.addVAR(read_noise=True)
    p.overscanCorrect()
    p.biasCorrect()
    p.ADUToElectrons()
    p.addVAR(poisson_noise=True)
    p.findAcquisitionSlits()
    p.skyCorrectNodAndShuffle()
    p.measureIQ(display=True)
    p.writeOutputs()
    return

default = reduce
