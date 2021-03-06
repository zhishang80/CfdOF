# ***************************************************************************
# *                                                                         *
# *   Copyright (c) 2015 - Qingfeng Xia <qingfeng.xia()eng.ox.ac.uk>        *
# *   Copyright (c) 2017 - Alfred Bogaers (CSIR) <abogaers@csir.co.za>      *
# *   Copyright (c) 2017 - Oliver Oxtoby (CSIR) <ooxtoby@csir.co.za>        *
# *   Copyright (c) 2017 - Johan Heyns (CSIR) <jheyns@csir.co.za>           *
# *                                                                         *
# *   This program is free software; you can redistribute it and/or modify  *
# *   it under the terms of the GNU Lesser General Public License (LGPL)    *
# *   as published by the Free Software Foundation; either version 2 of     *
# *   the License, or (at your option) any later version.                   *
# *   for detail see the LICENCE text file.                                 *
# *                                                                         *
# *   This program is distributed in the hope that it will be useful,       *
# *   but WITHOUT ANY WARRANTY; without even the implied warranty of        *
# *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the         *
# *   GNU Library General Public License for more details.                  *
# *                                                                         *
# *   You should have received a copy of the GNU Library General Public     *
# *   License along with this program; if not, write to the Free Software   *
# *   Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  *
# *   USA                                                                   *
# *                                                                         *
# ***************************************************************************

from __future__ import print_function

__title__ = "Classes for New CFD solver"
__author__ = "Qingfeng Xia"
__url__ = "http://www.freecadweb.org"

import os
import os.path

from numpy import *

import FreeCAD

import CfdCaseWriterFoam
import CfdTools
from PySide.QtCore import QObject, Signal, QThread
from CfdResidualPlot import ResidualPlot
from collections import OrderedDict


class CfdRunnable(QObject, object):
    def __init__(self, analysis=None, solver=None):
        super(CfdRunnable, self).__init__()
        if analysis and analysis.isDerivedFrom("Fem::FemAnalysisPython"):
            ## @var analysis
            #  FEM analysis - the core object. Has to be present.
            #  It's set to analysis passed in "__init__" or set to current active analysis by default if nothing has been passed to "__init__"
            self.analysis = analysis
        else:
            if FreeCAD.GuiUp:
                import FemGui
                self.analysis = FemGui.getActiveAnalysis()

        self.solver = None
        if solver and solver.isDerivedFrom("Fem::FemSolverObjectPython"):
            ## @var solver
            #  solver of the analysis. Used to store the active solver and analysis parameters
            self.solver = solver
        else:
            if analysis:
                self.solver = CfdTools.getSolver(self.analysis)
            if self.solver == None:
                FreeCAD.Console.printMessage("FemSolver object is missing from Analysis Object")

        if self.analysis:
            self.results_present = False
            self.result_object = None
        else:
            raise Exception('FEM: No active analysis found!')

    def check_prerequisites(self):
        return "" #CfdTools.check_prerequisites()


class CfdRunnableFoam(CfdRunnable):
    update_residual_signal = Signal(list, list, list, list)

    def __init__(self, analysis=None, solver=None):
        super(CfdRunnableFoam, self).__init__(analysis, solver)

        self.writer = CfdCaseWriterFoam.CfdCaseWriterFoam(self.analysis)

        self.initResiduals()

        self.residualPlot = None

    def check_prerequisites(self):
        return ""

    def initResiduals(self):
        self.UxResiduals = []
        self.UyResiduals = []
        self.UzResiduals = []
        self.pResiduals = []
        self.rhoResiduals = []
        self.EResiduals = []
        self.kResiduals = []
        self.omegaResiduals = []
        self.niter = 0

    def get_solver_cmd(self, case_dir):
        self.initResiduals()

        self.residualPlot = ResidualPlot()

        # Environment is sourced in run script, so no need to include in run command
        cmd = CfdTools.makeRunCommand('./Allrun', case_dir, source_env=False)
        FreeCAD.Console.PrintMessage("Solver run command: " + ' '.join(cmd) + "\n")
        return cmd

    def getRunEnvironment(self):
        return CfdTools.getRunEnvironment()

    def process_output(self, text):
        loglines = text.split('\n')
        for line in loglines:
            # print line,
            split = line.split()

            # Only store the first residual per timestep
            if line.startswith(u"Time = "):
                self.niter += 1

            # print split
            if "Ux," in split and self.niter-1 > len(self.UxResiduals):
                self.UxResiduals.append(float(split[7].split(',')[0]))
            if "Uy," in split and self.niter-1 > len(self.UyResiduals):
                self.UyResiduals.append(float(split[7].split(',')[0]))
            if "Uz," in split and self.niter-1 > len(self.UzResiduals):
                self.UzResiduals.append(float(split[7].split(',')[0]))
            if "p," in split and self.niter-1 > len(self.pResiduals):
                self.pResiduals.append(float(split[7].split(',')[0]))
            # HiSA coupled residuals
            if "Residual:" in split and self.niter-1 > len(self.rhoResiduals):
                self.rhoResiduals.append(float(split[4]))
                self.UxResiduals.append(float(split[5].lstrip('(')))
                self.UyResiduals.append(float(split[6]))
                self.UzResiduals.append(float(split[7].rstrip(')')))
                self.EResiduals.append(float(split[8]))
            if "k," in split and self.niter-1 > len(self.kResiduals):
                self.kResiduals.append(float(split[7].split(',')[0]))
            if "omega," in split and self.niter-1 > len(self.omegaResiduals):
                self.omegaResiduals.append(float(split[7].split(',')[0]))

        if self.niter > 1:
            self.residualPlot.updateResiduals(OrderedDict([
                ('$\\rho$', self.rhoResiduals),
                ('$U_x$', self.UxResiduals),
                ('$U_y$', self.UyResiduals),
                ('$U_z$', self.UzResiduals),
                ('$p$', self.pResiduals),
                ('$E$', self.EResiduals),
                ('$k$', self.kResiduals),
                ('$\\omega$', self.omegaResiduals)]))
