# This parameter file contains the parameters related to the primitives located
# in the primitives_gemini.py file, in alphabetical order.

from geminidr.core.parameters_bookkeeping import ParametersBookkeeping
from geminidr.core.parameters_preprocess import ParametersPreprocess
from geminidr.core.parameters_standardize import ParametersStandardize
from geminidr.core.parameters_visualize import ParametersVisualize
from geminidr.core.parameters_stack import ParametersStack
from .parameters_qa import ParametersQA

class ParametersGemini(ParametersBookkeeping, ParametersPreprocess,
                       ParametersStandardize, ParametersVisualize,
                       ParametersStack, ParametersQA):
    pass