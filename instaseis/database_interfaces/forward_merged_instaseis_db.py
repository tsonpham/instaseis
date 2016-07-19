#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Python library to extract seismograms from a set of wavefields generated by
AxiSEM.

:copyright:
    Martin van Driel (Martin@vanDriel.de), 2014
    Lion Krischer (krischer@geophysik.uni-muenchen.de), 2014
:license:
    GNU Lesser General Public License, Version 3 [non-commercial/academic use]
    (http://www.gnu.org/copyleft/lgpl.html)
"""
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import collections
import numpy as np

from .base_netcdf_instaseis_db import BaseNetCDFInstaseisDB
from . import mesh
from .. import rotations, spectral_basis
from ..source import Source


class ForwardMergedInstaseisDB(BaseNetCDFInstaseisDB):
    """
    Merged forward Instaseis database.
    """
    def __init__(self, db_path, netcdf_file, buffer_size_in_mb=100,
                 read_on_demand=False, *args, **kwargs):
        """
        :param db_path: Path to the Instaseis Database.
        :type db_path: str
        :param netcdf_file: The path to the actual netcdf4 file.
        :type netcdf_file: str
        :param buffer_size_in_mb: Strain and displacement are buffered to
            avoid repeated disc access. Depending on the type of database
            and the number of components of the database, the total buffer
            memory can be up to four times this number. The optimal value is
            highly application and system dependent.
        :type buffer_size_in_mb: int, optional
        :param read_on_demand: Read several global fields on demand (faster
            initialization) or on initialization (slower
            initialization, faster in individual seismogram extraction,
            useful e.g. for finite sources, default).
        :type read_on_demand: bool, optional
        """
        BaseNetCDFInstaseisDB.__init__(
            self, db_path=db_path, buffer_size_in_mb=buffer_size_in_mb,
            read_on_demand=read_on_demand, *args, **kwargs)
        self._parse_mesh(netcdf_file)

    def _parse_mesh(self, filename):

        MeshCollection_merged = collections.namedtuple(
            "MeshCollection_merged", ["merged"])

        self.meshes = MeshCollection_merged(mesh.Mesh(
            filename, full_parse=True,
            strain_buffer_size_in_mb=self.buffer_size_in_mb,
            displ_buffer_size_in_mb=self.buffer_size_in_mb,
            read_on_demand=self.read_on_demand))
        self.parsed_mesh = self.meshes.merged

        self._is_reciprocal = False

    def _get_data(self, source, receiver, components, coordinates,
                  element_info):
        ei = element_info
        # Collect data arrays and mu in a dictionary.
        data = {}

        mesh = self.parsed_mesh.f["Mesh"]

        # Get mu.
        if not self.read_on_demand:
            mesh_mu = self.parsed_mesh.mesh_mu
        else:
            mesh_mu = mesh["mesh_mu"]

        npol = self.info.spatial_order
        data["mu"] = mesh_mu[ei.gll_point_ids[npol // 2, npol // 2]]

        if not isinstance(source, Source):
            raise NotImplementedError
        if self.info.dump_type != 'displ_only':
            raise NotImplementedError

        utemp = self.meshes.merged.f["MergedSnapshots"][ei.id_elem]

        # utemp is currently (nvars, jpol, ipol, npts)
        # 1. Roll to (npts, nvar, jpol, ipol)
        utemp = np.rollaxis(utemp, 3, 0)
        # 2. Roll to (npts, jpol, nvar, ipol)
        utemp = np.rollaxis(utemp, 2, 1)
        # 3. Roll to (npts, jpol, ipol, nvar)
        utemp = np.rollaxis(utemp, 3, 2)

        displ_1 = np.zeros((utemp.shape[0], 3), order="F")
        displ_2 = np.zeros((utemp.shape[0], 3), order="F")
        displ_3 = np.zeros((utemp.shape[0], 3), order="F")
        displ_4 = np.zeros((utemp.shape[0], 3), order="F")

        # Now just fill them all.
        # displ_1 is generated from MZZ which has only two displacement
        # components.
        displ_1[:, 0] = spectral_basis.lagrange_interpol_2D_td(
            points1=ei.col_points_xi, points2=ei.col_points_eta,
            coefficients=utemp[:, :, :, 0], x1=ei.xi, x2=ei.eta)
        displ_1[:, 2] = spectral_basis.lagrange_interpol_2D_td(
            points1=ei.col_points_xi, points2=ei.col_points_eta,
            coefficients=utemp[:, :, :, 1], x1=ei.xi, x2=ei.eta)
        # displ_2 is generated from MXX+MYY which has only two displacement
        # components.
        displ_2[:, 0] = spectral_basis.lagrange_interpol_2D_td(
            points1=ei.col_points_xi, points2=ei.col_points_eta,
            coefficients=utemp[:, :, :, 2], x1=ei.xi, x2=ei.eta)
        displ_2[:, 2] = spectral_basis.lagrange_interpol_2D_td(
            points1=ei.col_points_xi, points2=ei.col_points_eta,
            coefficients=utemp[:, :, :, 3], x1=ei.xi, x2=ei.eta)
        # displ_3 is generated from MXZ/MYZ which has three displacement
        # components.
        displ_3[:, 0] = spectral_basis.lagrange_interpol_2D_td(
            points1=ei.col_points_xi, points2=ei.col_points_eta,
            coefficients=utemp[:, :, :, 4], x1=ei.xi, x2=ei.eta)
        displ_3[:, 1] = spectral_basis.lagrange_interpol_2D_td(
            points1=ei.col_points_xi, points2=ei.col_points_eta,
            coefficients=utemp[:, :, :, 5], x1=ei.xi, x2=ei.eta)
        displ_3[:, 2] = spectral_basis.lagrange_interpol_2D_td(
            points1=ei.col_points_xi, points2=ei.col_points_eta,
            coefficients=utemp[:, :, :, 6], x1=ei.xi, x2=ei.eta)
        # displ_3 is generated from MXY/MXX-MYY which has three displacement
        # components.
        displ_4[:, 0] = spectral_basis.lagrange_interpol_2D_td(
            points1=ei.col_points_xi, points2=ei.col_points_eta,
            coefficients=utemp[:, :, :, 7], x1=ei.xi, x2=ei.eta)
        displ_4[:, 1] = spectral_basis.lagrange_interpol_2D_td(
            points1=ei.col_points_xi, points2=ei.col_points_eta,
            coefficients=utemp[:, :, :, 8], x1=ei.xi, x2=ei.eta)
        displ_4[:, 2] = spectral_basis.lagrange_interpol_2D_td(
            points1=ei.col_points_xi, points2=ei.col_points_eta,
            coefficients=utemp[:, :, :, 9], x1=ei.xi, x2=ei.eta)

        mij = source.tensor / self.parsed_mesh.amplitude
        # mij is [m_rr, m_tt, m_pp, m_rt, m_rp, m_tp]
        # final is in s, phi, z coordinates
        final = np.zeros((displ_1.shape[0], 3), dtype="float64")

        final[:, 0] += displ_1[:, 0] * mij[0]
        final[:, 2] += displ_1[:, 2] * mij[0]

        final[:, 0] += displ_2[:, 0] * (mij[1] + mij[2])
        final[:, 2] += displ_2[:, 2] * (mij[1] + mij[2])

        fac_1 = mij[3] * np.cos(coordinates.phi) + \
            mij[4] * np.sin(coordinates.phi)
        fac_2 = -mij[3] * np.sin(coordinates.phi) + \
            mij[4] * np.cos(coordinates.phi)

        final[:, 0] += displ_3[:, 0] * fac_1
        final[:, 1] += displ_3[:, 1] * fac_2
        final[:, 2] += displ_3[:, 2] * fac_1

        fac_1 = (mij[1] - mij[2]) * np.cos(2 * coordinates.phi) \
            + 2 * mij[5] * np.sin(2 * coordinates.phi)
        fac_2 = -(mij[1] - mij[2]) * np.sin(2 * coordinates.phi) \
            + 2 * mij[5] * np.cos(2 * coordinates.phi)

        final[:, 0] += displ_4[:, 0] * fac_1
        final[:, 1] += displ_4[:, 1] * fac_2
        final[:, 2] += displ_4[:, 2] * fac_1

        rotmesh_colat = np.arctan2(coordinates.s, coordinates.z)

        if "T" in components:
            # need the - for consistency with reciprocal mode,
            # need external verification still
            data["T"] = -final[:, 1]

        if "R" in components:
            data["R"] = final[:, 0] * np.cos(rotmesh_colat) \
                        - final[:, 2] * np.sin(rotmesh_colat)

        if "N" in components or "E" in components or "Z" in components:
            # transpose needed because rotations assume different slicing
            # (ugly)
            final = rotations.rotate_vector_src_to_NEZ(
                final.T, coordinates.phi,
                source.longitude_rad, source.colatitude_rad,
                receiver.longitude_rad, receiver.colatitude_rad).T

            if "N" in components:
                data["N"] = final[:, 0]
            if "E" in components:
                data["E"] = final[:, 1]
            if "Z" in components:
                data["Z"] = final[:, 2]

        return data
