#
#                                                        mappers.recipeMapper.py
# ------------------------------------------------------------------------------
import pkgutil

from importlib import import_module

from .baseMapper import Mapper

from ..utils.errors import ModeError
from ..utils.errors import RecipeNotFound

from ..utils.mapper_utils import dotpath
from ..utils.mapper_utils import find_user_recipe
from ..utils.mapper_utils import RECIPEMARKER
# ------------------------------------------------------------------------------
class RecipeMapper(Mapper):
    """
    Retrieve the appropriate recipe for a dataset, using all defined defaults:

    >>> ad = astrodata.open(<fitsfile>)
    >>> adinputs = [ad]
    >>> rm = RecipeMapper(adinputs)
    >>> recipe = rm.get_applicable_recipe()
    >>> recipe.__name__ 
    'qaReduce'

    """
    def get_applicable_recipe(self):
        recipefn = find_user_recipe(self.recipename)
        if recipefn is None:
            tag_match, recipefn = self._retrieve_recipe()

        if recipefn is None:
            raise RecipeNotFound("Recipe '{}' not found.".format(self.recipename))

        return recipefn

    # --------------------------------------------------------------------------
    # Recipe search cascade
    def _retrieve_recipe(self):
        """
        Start of the recipe library search cascade.

        Parameters
        ----------
        <void>

        Returns
        -------
        <tuple> : (set, <function>)
                  A tuple including the best tag set match and the recipe function
                  that best matched.

        """
        matched_set = (set([]), None)
        for rlib in self._get_tagged_recipes():
            if hasattr(rlib, 'recipe_tags'):
                if self.tags.issuperset(rlib.recipe_tags):
                    isect = rlib.recipe_tags
                    l1 = len(isect)
                    l2 = len(matched_set[0])
                    matched_set = (isect, rlib) if l1 > l2 else matched_set
                else:
                    continue
            else:
                continue

        isection, rlib = matched_set
        try:
            recipe_actual = getattr(rlib, self.recipename)
        except AttributeError:
            recipe_actual = None
        return isection, recipe_actual

    def _get_tagged_recipes(self):
        loaded_pkg = import_module(self.dotpackage)
        for rmod, ispkg in self._generate_recipe_modules(loaded_pkg):
            if not ispkg:
                importmod = dotpath(self.dotpackage, rmod)
                yield import_module(importmod)
            else:
                continue

    def _generate_recipe_modules(self, pkg, recipedir=RECIPEMARKER):
        ppath = pkg.__path__[0]
        pkg_importer = pkgutil.ImpImporter(ppath)
        for pkgname, ispkg in pkg_importer.iter_modules():
            if ispkg and pkgname == recipedir:
                break 
            else:
                continue

        loaded_pkg = import_module(dotpath(self.dotpackage, pkgname))
        for mode_pkg, ispkg in self._generate_mode_pkg(loaded_pkg):
            yield dotpath(pkgname, mode_pkg), ispkg

    def _generate_mode_pkg(self, pkg):
        found = False
        ppath = pkg.__path__[0]
        pkg_importer = pkgutil.ImpImporter(ppath)
        for pkgname, ispkg in pkg_importer.iter_modules():
            if ispkg and pkgname in self.mode:
                found = True
                break
            else:
                continue

        if not found:
            cerr = "No recipe mode package matched '{}'"
            raise ModeError(cerr.format(self.mode))

        loaded_pkg = import_module(dotpath(pkg.__name__, pkgname))
        for mod, ispkg in self._generate_mode_libs(loaded_pkg):
            yield dotpath(pkgname, mod), ispkg

    def _generate_mode_libs(self, pkg):
        ppath = pkg.__path__[0]
        pkg_importer = pkgutil.ImpImporter(ppath)
        for pkgname, ispkg in pkg_importer.iter_modules():
            if not ispkg:
                yield pkgname, ispkg
            else:
                continue
