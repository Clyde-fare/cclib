# This file is part of cclib (http://cclib.github.io), a library for parsing
# and interpreting the results of computational chemistry packages.
#
# Copyright (C) 2006-2014, the cclib development team
#
# The library is free software, distributed under the terms of
# the GNU Lesser General Public version 2.1 or later. You should have
# received a copy of the license along with cclib. You can also access
# the full license online at http://www.gnu.org/copyleft/lgpl.html.

"""Fragment analysis based on parsed ADF data."""

import random

import numpy
numpy.inv = numpy.linalg.inv

from .calculationmethod import *


class FragmentAnalysis(Method):
    """Convert a molecule's basis functions from atomic-based to fragment MO-based"""
    def __init__(self, data, progress=None, loglevel=logging.INFO,
                 logname="FragmentAnalysis of"):

        # Call the __init__ method of the superclass.
        super(FragmentAnalysis, self).__init__(data, progress, loglevel, logname)
        self.parsed = False
        
    def __str__(self):
        """Return a string representation of the object."""
        return "Fragment molecule basis of %s" % (self.data)

    def __repr__(self):
        """Return a representation of the object."""
        return 'Fragment molecular basis("%s")' % (self.data)

    def calculate(self, fragments, cupdate=0.05):

        nFragBasis = 0
        nFragAlpha = 0
        nFragBeta = 0
        self.fonames = []

        unrestricted = ( len(self.data.mocoeffs) == 2 )

        self.logger.info("Creating attribute fonames[]")

        # Collect basis info on the fragments.
        for j in range(len(fragments)):
            nFragBasis += fragments[j].nbasis
            nFragAlpha += fragments[j].homos[0] + 1
            if unrestricted and len(fragments[j].homos) == 1:
                nFragBeta += fragments[j].homos[0] + 1 #assume restricted fragment
            elif unrestricted and len(fragments[j].homos) == 2:
                nFragBeta += fragments[j].homos[1] + 1 #assume unrestricted fragment
             
            #assign fonames based on fragment name and MO number
            for i in range(fragments[j].nbasis):
                if hasattr(fragments[j],"name"):
                    self.fonames.append("%s_%i"%(fragments[j].name,i+1))
                else:
                    self.fonames.append("noname%i_%i"%(j,i+1))

        nBasis = self.data.nbasis
        nAlpha = self.data.homos[0] + 1
        if unrestricted:
            nBeta = self.data.homos[1] + 1

        # Check to make sure calcs have the right properties.
        if nBasis != nFragBasis:
            self.logger.error("Basis functions don't match")
            return False

        if nAlpha != nFragAlpha:
            self.logger.error("Alpha electrons don't match")
            return False

        if unrestricted and nBeta != nFragBeta:
            self.logger.error("Beta electrons don't match")
            return False

        if len(self.data.atomcoords) != 1:
            self.logger.warning("Molecule calc appears to be an optimization")

        for frag in fragments:
            if len(frag.atomcoords) != 1:
                msg = "One or more fragment appears to be an optimization"
                self.logger.warning(msg)
                break

        last = 0
        for frag in fragments:
            size = frag.natom
            if self.data.atomcoords[0][last:last+size].tolist() != \
                    frag.atomcoords[0].tolist():
                self.logger.error("Atom coordinates aren't aligned")
                return False
            if self.data.atomnos[last:last+size].tolist() != \
                    frag.atomnos.tolist():
                self.logger.error("Elements don't match")
                return False

            last += size

        # And let's begin!
        self.mocoeffs = []
        self.logger.info("Creating mocoeffs in new fragment MO basis: mocoeffs[]")

        for spin in range(len(self.data.mocoeffs)):
            blockMatrix = numpy.zeros((nBasis,nBasis), "d")
            pos = 0

            # Build up block-diagonal matrix from fragment mocoeffs.
            # Need to switch ordering from [mo,ao] to [ao,mo].
            for i in range(len(fragments)):
                size = fragments[i].nbasis
                if len(fragments[i].mocoeffs) == 1:
                    temp = numpy.transpose(fragments[i].mocoeffs[0])
                    blockMatrix[pos:pos+size, pos:pos+size] = temp
                else:
                    temp = numpy.transpose(fragments[i].mocoeffs[spin])
                    blockMatrix[pos:pos+size, pos:pos+size] = temp
                pos += size
            
            # Invert and mutliply to result in fragment MOs as basis.
            iBlockMatrix = numpy.inv(blockMatrix) 
            temp = numpy.transpose(self.data.mocoeffs[spin])
            results = numpy.transpose(numpy.dot(iBlockMatrix, temp))

            self.mocoeffs.append(results)
            
            if hasattr(self.data, "aooverlaps"):
                tempMatrix = numpy.dot(self.data.aooverlaps, blockMatrix)
                tBlockMatrix = numpy.transpose(blockMatrix)
                if spin == 0:
                    self.fooverlaps = numpy.dot(tBlockMatrix, tempMatrix)
                    self.logger.info("Creating fooverlaps: array[x,y]")
                elif spin == 1:
                    self.fooverlaps2 = numpy.dot(tBlockMatrix, tempMatrix)
                    self.logger.info("Creating fooverlaps (beta): array[x,y]")
            else:
                self.logger.warning("Overlap matrix missing")

        self.parsed = True
        self.nbasis = nBasis
        self.homos = self.data.homos

        return True
